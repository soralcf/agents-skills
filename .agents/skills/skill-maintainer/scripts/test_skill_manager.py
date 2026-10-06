#!/usr/bin/env python3
"""Regression checks for catalog validation, package generation, and preservation guards."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import skill_manager
import transactions
from skill_manager import Catalog, DEFAULT_ROOT, validate, remove_skill
from project_doctor import inspect_project


MANAGED = transactions.MANAGED_PATHS


def snapshot(root):
    """Every byte an applied maintenance command is allowed to rewrite."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for base in MANAGED
        for path in (root / base).rglob('*') if path.is_file()
    }


class CatalogSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='agents-catalog-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for directory in MANAGED:
            shutil.copytree(DEFAULT_ROOT / directory, self.root / directory,
                            ignore=shutil.ignore_patterns('__pycache__'))
        self.catalog = Catalog(self.root)

    def check_validation(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = validate(self.catalog)
        return code, output.getvalue()

    def clear_workflows(self):
        self.catalog.workflows_doc['workflows'] = []
        self.catalog.workflows_path.write_text(json.dumps(self.catalog.workflows_doc))

    # -- layout and provenance --------------------------------------------

    def test_valid_catalog(self):
        self.assertEqual(self.check_validation()[0], 0)

    def test_upstream_edit_is_detected(self):
        path = self.root / self.catalog.skills['teach']['path'] / 'SKILL.md'
        path.write_text(path.read_text() + '\nUnexpected behavioral change.\n')
        code, errors = self.check_validation()
        self.assertEqual(code, 1)
        self.assertIn('teach: vendored content differs from lock', errors)

    def test_excluded_upstream_overlay_must_not_ship(self):
        overlay = self.root / self.catalog.skills['teach']['path'] / 'agents/openai.yaml'
        overlay.parent.mkdir(parents=True)
        overlay.write_text('name: teach\n')
        code, errors = self.check_validation()
        self.assertEqual(code, 1)
        self.assertIn('teach: vendored tree ships an excluded path (agents/openai.yaml)', errors)

    def test_path_must_match_skill_name(self):
        self.catalog.skills['teach']['path'] = '.agents/skills/00-learning/teach'
        code, errors = self.check_validation()
        self.assertEqual(code, 1)
        self.assertIn('teach: path must be .agents/skills/teach', errors)

    def test_unregistered_skill_directory_is_detected(self):
        extra = self.root / '.agents/skills/extra-skill'
        extra.mkdir()
        (extra / 'SKILL.md').write_text('---\nname: extra-skill\ndescription: x\n---\n')
        code, errors = self.check_validation()
        self.assertEqual(code, 1)
        self.assertIn('unregistered skill directory: .agents/skills/extra-skill', errors)

    def test_invocation_must_match_frontmatter(self):
        path = self.root / '.agents/skills/workflow-guide/SKILL.md'
        text = '\n'.join(line for line in path.read_text().splitlines()
                         if not line.startswith('disable-model-invocation:'))
        path.write_text(text + '\n')
        code, errors = self.check_validation()
        self.assertEqual(code, 1)
        self.assertIn(
            "workflow-guide: invocation 'user' disagrees with disable-model-invocation in SKILL.md",
            errors,
        )

    # -- group definitions and generated packages -------------------------

    def test_package_skills_must_match_registry(self):
        manifest = self.catalog.package('vendor-mattpocock')
        manifest['skills'] = [name for name in manifest['skills'] if name != 'teach']
        self.catalog.save_package('vendor-mattpocock', manifest)
        code, errors = self.check_validation()
        self.assertEqual(code, 1)
        self.assertIn(
            'vendor-mattpocock: package skills differ from registry (missing teach; stale none)',
            errors,
        )

    def test_package_rejects_fields_outside_the_plugin_schema(self):
        manifest = self.catalog.package('workflow-hub')
        manifest['interface'] = {'displayName': 'Workflow Hub'}
        self.catalog.save_package('workflow-hub', manifest)
        code, errors = self.check_validation()
        self.assertEqual(code, 1)
        self.assertIn(
            'workflow-hub: package.json has fields outside the plugin schema: interface',
            errors,
        )

    def test_build_writes_schema_shaped_package(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(skill_manager.build(self.catalog, None, False), 0)
            self.assertEqual(skill_manager.build(self.catalog, None, True), 0)
        built = self.root / 'dist/vendor-mattpocock'
        manifest = json.loads((built / 'plugin.json').read_text())
        expected = skill_manager.plugin_manifest(self.catalog, 'vendor-mattpocock')
        self.assertEqual(manifest, expected)
        self.assertEqual(manifest['$schema'], skill_manager.PLUGIN_SCHEMA)
        self.assertLessEqual(set(manifest), skill_manager.PLUGIN_KEYS)
        self.assertNotIn('package.json', {p.name for p in built.iterdir()})
        self.assertNotIn('UPSTREAM.lock.json', {p.name for p in built.iterdir()})
        self.assertEqual(
            sorted(path.name for path in (built / 'skills').iterdir()),
            sorted(item['name'] for item in self.catalog.group_skills('vendor-mattpocock')),
        )
        self.assertEqual(self.check_validation()[0], 0)

    def test_stale_built_package_is_detected(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(skill_manager.build(self.catalog, None, False), 0)
        path = self.root / '.agents/skills/workflow-guide/SKILL.md'
        path.write_text(path.read_text() + '\nExtra guidance.\n')
        code, errors = self.check_validation()
        self.assertEqual(code, 1)
        self.assertIn('workflow-hub: dist/workflow-hub/plugin.json is stale; run build', errors)

    # -- removal guards ----------------------------------------------------

    def test_dependency_blocks_removal(self):
        # Remove workflow edges to exercise skill dependency protection alone.
        self.clear_workflows()
        with contextlib.redirect_stdout(io.StringIO()):
            result = remove_skill(self.catalog, 'code-review', True)
        self.assertEqual(result, 1)
        self.assertTrue((self.root / self.catalog.skills['code-review']['path']).is_dir())

    def test_removal_updates_every_managed_record(self):
        self.clear_workflows()
        before = skill_manager.plugin_manifest(self.catalog, 'vendor-mattpocock')['version']
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(remove_skill(self.catalog, 'teach', True), 0)
        self.assertFalse((self.root / '.agents/skills/teach').exists())
        self.assertNotIn('teach', self.catalog.package('vendor-mattpocock')['skills'])
        lock = json.loads((self.root / self.catalog.source('mattpocock')['lockPath']).read_text())
        self.assertNotIn('teach', [item['name'] for item in lock['skills']])
        # The derived cachebuster must move so an installed copy cannot stay stale.
        self.assertNotEqual(before, skill_manager.plugin_manifest(self.catalog, 'vendor-mattpocock')['version'])
        self.assertEqual(self.check_validation()[0], 0)

    def test_failed_removal_restores_all_managed_files(self):
        self.clear_workflows()
        with contextlib.redirect_stdout(io.StringIO()):
            skill_manager.write_catalog(self.catalog, True)
        before = snapshot(self.root)
        with mock.patch.object(skill_manager, 'write_catalog', side_effect=RuntimeError('injected failure')):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, 'injected failure'):
                    remove_skill(self.catalog, 'teach', True)
        self.assertEqual(before, snapshot(self.root))
        self.assertEqual(self.check_validation()[0], 0)

    def test_failed_sync_restores_all_managed_files(self):
        before = snapshot(self.root)

        def local_checkout(source, ref, destination):
            """Stand in for a clone: reproduce the pinned upstream selection."""
            destination.mkdir()
            for item in self.catalog.selected('mattpocock'):
                shutil.copytree(self.root / item['path'], destination / item['origin']['path'])
            shutil.copy2(self.root / '.agents/plugins/vendor-mattpocock/LICENSE',
                         destination / source['licensePath'])
            lock = json.loads((self.root / source['lockPath']).read_text())
            return lock['commit'], lock['committedAt']

        with mock.patch.object(skill_manager, 'checkout_source', side_effect=local_checkout), \
             mock.patch.object(skill_manager, 'write_catalog', side_effect=RuntimeError('injected sync failure')):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, 'injected sync failure'):
                    skill_manager.sync_vendor(self.catalog, 'mattpocock', 'local-ref', True)
        self.assertEqual(before, snapshot(self.root))
        self.assertEqual(self.check_validation()[0], 0)

    # -- workflows, prerequisites, upstream --------------------------------

    def test_workflow_branch_without_condition_is_rejected(self):
        workflow = next(w for w in self.catalog.workflows_doc['workflows'] if w['id'] == 'matt-learning')
        workflow['relations'][0].pop('when')
        code, errors = self.check_validation()
        self.assertEqual(code, 1)
        self.assertIn('matt-learning: conditional relation needs when', errors)

    def test_project_doctor_expands_dependencies_without_writing(self):
        project = self.root / 'project'
        project.mkdir()
        before = list(project.iterdir())
        report = inspect_project(self.catalog, project, skill='implement')
        self.assertEqual(before, list(project.iterdir()))
        self.assertIn('code-review', report['skills'])
        self.assertIn('tdd', report['skills'])
        self.assertGreater(report['missing'], 0)

    def test_require_current_signals_an_upstream_update(self):
        lock = json.loads((self.root / self.catalog.source('mattpocock')['lockPath']).read_text())
        with mock.patch.object(skill_manager, 'remote_head', return_value='f' * 40), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(skill_manager.check_upstream(self.catalog, 'mattpocock', True), 1)
        with mock.patch.object(skill_manager, 'remote_head', return_value=lock['commit']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(skill_manager.check_upstream(self.catalog, 'mattpocock', True), 0)


if __name__ == '__main__':
    unittest.main()
