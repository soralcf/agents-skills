#!/usr/bin/env python3
"""Validate the .agents skill catalog and build vendor-neutral plugin packages.

Source of truth:
  .agents/skills/<name>/SKILL.md   every skill, exactly one copy, Agent Skills layout
  .agents/plugins/<group>/         group definition (package.json) plus shared files
  registry/skills.json             catalog metadata, ownership, upstream pins
  registry/workflows.json          maintained task routes

Generated:
  dist/<group>/                    Agent Plugins 1.0 package (gitignored)
  .agents/skills/workflow-guide/references/catalog.md
  .agents/plugins/<group>/README.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

from transactions import transactional


DEFAULT_ROOT = Path(__file__).resolve().parents[4]

SKILLS_DIR = ".agents/skills"
GROUPS_DIR = ".agents/plugins"
DIST_DIR = "dist"
CATALOG_PATH = Path(SKILLS_DIR) / "workflow-guide/references/catalog.md"

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PLUGIN_NAME = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAMESPACE = re.compile(r"^[a-z0-9]+(?:\.[a-z0-9-]+)+$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

PLUGIN_KEYS = frozenset({
    "$schema", "name", "version", "description", "author", "homepage",
    "repository", "license", "keywords", "extensions",
})
AUTHOR_KEYS = frozenset({"name", "email", "url"})
OWNERSHIPS = frozenset({"original", "vendored"})
SCOPES = frozenset({"plugin", "repository"})
INVOCATIONS = frozenset({"user", "model"})
RELATION_TYPES = frozenset({"sequence", "optional", "calls", "choice", "alongside"})
RELATION_LABELS = {
    "sequence": "下一步", "optional": "按需进入", "calls": "内部调用",
    "choice": "替代入口", "alongside": "同时配合",
}

# Upstream ships its own Codex overlay; vendored trees are pinned without it.
VENDOR_EXCLUDED_PATHS = ("agents/openai.yaml",)
# Maintenance-only files that never ship inside a generated package.
PACKAGE_EXCLUDED_NAMES = frozenset({"package.json", "UPSTREAM.lock.json"})


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def tree_digest(directory: Path, exclude: tuple[str, ...] = ()) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        relative = path.relative_to(directory).as_posix()
        if relative in exclude:
            continue
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def unpack_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        if value[0] == '"':
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner.replace("''", "'")
    return value


def parse_frontmatter(skill_file: Path) -> dict:
    """Parse the flat YAML subset used by Agent Skills frontmatter."""
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    fields: dict[str, str] = {}
    key: str | None = None
    literal = False
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[0] in " \t":
            if key and fields[key]:
                fields[key] += ("\n" if literal else " ") + raw.strip()
            elif key:
                fields[key] = raw.strip()
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", raw)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if value in ("", ">", ">-", ">+", "|", "|-", "|+"):
            literal = value.startswith("|")
            fields[key] = ""
        else:
            literal = False
            fields[key] = unpack_scalar(value)
    return fields


def frontmatter_name(directory: Path) -> str | None:
    skill_file = directory / "SKILL.md"
    if not skill_file.is_file():
        return None
    return parse_frontmatter(skill_file).get("name")


def run(command: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"command failed: {' '.join(command)}\n{detail}")
    return completed.stdout.strip()


class Catalog:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.skills_path = self.root / "registry/skills.json"
        self.workflows_path = self.root / "registry/workflows.json"
        self.skills_doc = load_json(self.skills_path)
        self.workflows_doc = load_json(self.workflows_path)
        self.skills = {item["name"]: item for item in self.skills_doc["skills"]}

    def source(self, source_id: str):
        try:
            return self.skills_doc["sources"][source_id]
        except KeyError as error:
            raise ValueError(f"unknown source: {source_id}") from error

    def selected(self, source_id: str):
        return [
            item for item in self.skills_doc["skills"]
            if item.get("origin", {}).get("source") == source_id
        ]

    def save_skills(self) -> None:
        atomic_json(self.skills_path, self.skills_doc)

    # -- groups -----------------------------------------------------------
    def group_names(self) -> list[str]:
        base = self.root / GROUPS_DIR
        if not base.is_dir():
            return []
        return sorted(path.name for path in base.iterdir() if path.is_dir())

    def package_path(self, group: str) -> Path:
        return self.root / GROUPS_DIR / group / "package.json"

    def package(self, group: str) -> dict:
        return load_json(self.package_path(group))

    def save_package(self, group: str, manifest: dict) -> None:
        atomic_json(self.package_path(group), manifest)

    def group_skills(self, group: str) -> list[dict]:
        return [item for item in self.skills_doc["skills"] if item.get("plugin") == group]

    def plugins(self) -> dict[str, dict]:
        return {name: self.package(name) for name in self.group_names()}


def packaged_digest(catalog: Catalog, group: str) -> str:
    """Content digest of a group's skills, independent of the manifest itself."""
    digest = hashlib.sha256()
    for item in sorted(catalog.group_skills(group), key=lambda value: value["name"]):
        digest.update(item["name"].encode())
        digest.update(b"\0")
        digest.update(tree_digest(catalog.root / item["path"]).encode())
        digest.update(b"\0")
    return digest.hexdigest()


def plugin_manifest(catalog: Catalog, group: str) -> dict:
    """Derive the Agent Plugins 1.0 plugin.json for a group."""
    manifest = catalog.package(group)
    base = str(manifest.get("version", "0.0.0")).split("+")[0]
    plugin = {
        "$schema": PLUGIN_SCHEMA,
        "name": group,
        "version": f"{base}+content.{packaged_digest(catalog, group)[:16]}",
    }
    for key, value in manifest.items():
        if key in ("name", "version", "skills"):
            continue
        plugin[key] = value
    return plugin


def stage_guide_target(catalog: Catalog) -> Path | None:
    owners = {item["plugin"] for item in catalog.skills_doc["skills"] if item.get("stage")}
    if not owners:
        return None
    if len(owners) != 1:
        raise ValueError("staged skills span several groups: " + ", ".join(sorted(owners)))
    return catalog.root / GROUPS_DIR / owners.pop() / "README.md"


# -- rendering ------------------------------------------------------------

def render_catalog(catalog: Catalog) -> str:
    source_locks = {}
    for source_id, source in catalog.skills_doc.get("sources", {}).items():
        lock_path = catalog.root / source["lockPath"]
        source_locks[source_id] = load_json(lock_path) if lock_path.is_file() else None

    lines = [
        "# Maintained workflow catalog",
        "",
        "> Generated from `registry/skills.json` and `registry/workflows.json`.",
        "> Do not edit this file directly.",
        "",
        "## Workflows",
        "",
    ]
    for workflow in catalog.workflows_doc["workflows"]:
        lines.extend([
            f"### {workflow['title']}",
            "",
            f"- ID: `{workflow['id']}`",
            "- Entry: " + " / ".join(f"`${name}`" for name in workflow.get("entries", [workflow["entry"]])),
            f"- Outcome: {workflow['outcome']}",
        ])
        for relation in workflow.get("relations", []):
            condition = f"（{relation['when']}）" if relation.get("when") else ""
            label = RELATION_LABELS.get(relation["type"], relation["type"])
            lines.append(f"- `{relation['from']}` — {label}{condition}：`{relation['to']}`")
        lines.append("")

    lines.extend([
        "## Packages",
        "",
        "Every skill lives once under `.agents/skills/`. A group only names the skills it",
        "publishes; `skill_manager.py build` emits the Agent Plugins package into `dist/`.",
        "",
        "| Group | Version | Skills |",
        "|---|---|---|",
    ])
    for group in catalog.group_names():
        manifest = catalog.package(group)
        members = ", ".join(f"`{item['name']}`" for item in sorted(catalog.group_skills(group), key=lambda value: value["name"]))
        lines.append(f"| `{group}` | {manifest.get('version', '?')} | {members} |")
    lines.append("")

    lines.extend([
        "## Stage navigation",
        "",
        "Stage numbers are navigation, not mandatory execution order."
        " See the staged group's README.md and PROJECT-SETUP.md for routes and project prerequisites.",
        "",
    ])
    for stage in catalog.skills_doc.get("stages", []):
        members = [item for item in catalog.skills_doc["skills"] if item.get("stage") == stage["id"]]
        lines.append(f"- **{stage['id']} — {stage['title']}**: " + ", ".join(f"`{item['name']}`" for item in members))

    lines.extend(["", "## Skills", "", "| Skill | Group | Invocation | Ownership | Source |", "|---|---|---|---|---|"])
    for item in sorted(catalog.skills_doc["skills"], key=lambda value: value["name"]):
        origin = item.get("origin")
        if origin:
            lock = source_locks.get(origin["source"])
            commit = lock["commit"][:7] if lock else "unlocked"
            source_text = f"{origin['source']}@{commit}"
        else:
            source_text = "this repository"
        lines.append(
            f"| `{item['name']}` | `{item.get('plugin') or '—'}` | {item['invocation']} |"
            f" {item['ownership']} | {source_text} |"
        )

    exclusions = []
    for source_id, source in catalog.skills_doc.get("sources", {}).items():
        for item in source.get("exclusions", []):
            exclusions.append((source_id, item))
    if exclusions:
        lines.extend(["", "## Deliberate upstream exclusions", ""])
        for source_id, item in sorted(exclusions, key=lambda value: value[1]["name"]):
            lines.append(f"- `{item['name']}` ({source_id}): {item['reason']}")

    referenced = {
        name for workflow in catalog.workflows_doc["workflows"] for name in workflow["skills"]
    }
    unreferenced = sorted(set(catalog.skills) - referenced)
    lines.extend(["", "## Static audit", ""])
    if unreferenced:
        lines.append("- Unreferenced skills: " + ", ".join(f"`{name}`" for name in unreferenced))
    else:
        lines.append("- Every registered skill appears in at least one maintained workflow.")
    lines.extend([
        "- Unreferenced does not mean unused; real usage requires user evidence or telemetry.",
        "- Responsibility overlap still requires semantic review by the user.",
        "",
    ])
    return "\n".join(lines)


def render_stage_guide(catalog: Catalog) -> str:
    lines = [
        "# Matt Pocock Skills：按工作阶段选择",
        "",
        "> 从 registry/skills.json 生成。编号表示常用阶段，不是必须依次执行的步骤。",
        "",
        "每个 skill 只有一份，位于 `.agents/skills/<name>/`；学习、领域建模、测试、交接可以在任何阶段按需进入。",
        "",
        "先看 [常用路线](WORKFLOWS.md)，需要 tracker 的项目先看 [项目接入](PROJECT-SETUP.md)。",
        "",
        "上游文件保持原样，只移除上游自带的 Codex 专用 `agents/openai.yaml`。",
        "上游整树摘要与打包树摘要分别记录在 UPSTREAM.lock.json，可逐项复核。",
        "",
    ]
    for stage in catalog.skills_doc.get("stages", []):
        lines += [f"## {stage['id']} · {stage['title']}", "", "| Skill | 任务类型 | 调用方式 |", "|---|---|---|"]
        for item in catalog.selected("mattpocock"):
            if item.get("stage") != stage["id"]:
                continue
            mode = "显式调用" if item["invocation"] == "user" else "自动匹配或显式调用"
            lines.append(f"| [{item['name']}](../../skills/{item['name']}/SKILL.md) | {item.get('summary', '—')} | {mode} |")
        lines.append("")
    lines += [
        "## 技能依赖与项目先决条件",
        "",
        "这些是运行时调用依赖，不代表用户需要提前手动执行。分支使用的技能列入依赖，以便安装和移除检查保证流程完整。",
        "",
        "| Skill | 调用依赖 | 项目前提 |",
        "|---|---|---|",
    ]
    for item in catalog.selected("mattpocock"):
        if item.get("requires") or item.get("prerequisites"):
            requires = ", ".join("`" + name + "`" for name in item.get("requires", [])) or "—"
            prerequisites = "; ".join(item.get("prerequisites", [])) or "—"
            lines.append(f"| `{item['name']}` | {requires} | {prerequisites} |")
    lines += [
        "",
        "依赖 setup-matt-pocock-skills 的配置要求由项目接入文档说明；该 setup skill 未安装。",
        "这些前置条件必须写进项目配置，skill 文件本身不改变上游发布、提交或教学产物行为。",
        "",
    ]
    return "\n".join(lines)


@transactional
def write_catalog(catalog: Catalog, apply: bool) -> int:
    outputs = [(catalog.root / CATALOG_PATH, render_catalog(catalog))]
    stage_target = stage_guide_target(catalog)
    if stage_target is not None:
        outputs.append((stage_target, render_stage_guide(catalog)))
    if not apply:
        print(outputs[0][1])
        return 0
    for target, text in outputs:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(f"updated {target.relative_to(catalog.root)}")
    return 0


# -- validation -----------------------------------------------------------

def validate_skills(catalog: Catalog, errors: list[str]) -> None:
    entries = catalog.skills_doc.get("skills", [])
    names = [item.get("name") for item in entries]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        errors.append("duplicate registry names: " + ", ".join(duplicates))
    stages = {stage["id"] for stage in catalog.skills_doc.get("stages", [])}
    groups = set(catalog.group_names())

    for item in entries:
        name = item.get("name") or "<unnamed>"
        if not SKILL_NAME.match(name) or len(name) > 64:
            errors.append(f"{name}: name must match {SKILL_NAME.pattern} and be at most 64 characters")
        if item.get("ownership") not in OWNERSHIPS:
            errors.append(f"{name}: unknown ownership {item.get('ownership')!r}")
        if item.get("scope") not in SCOPES:
            errors.append(f"{name}: unknown scope {item.get('scope')!r}")
        if item.get("invocation") not in INVOCATIONS:
            errors.append(f"{name}: unknown invocation {item.get('invocation')!r}")
        if item.get("stage") and item["stage"] not in stages:
            errors.append(f"{name}: unknown stage")
        expected_path = f"{SKILLS_DIR}/{name}"
        if item.get("path") != expected_path:
            errors.append(f"{name}: path must be {expected_path}")
        plugin = item.get("plugin")
        if plugin is not None and plugin not in groups:
            errors.append(f"{name}: unknown group {plugin}")
        for dependency in item.get("requires", []):
            if dependency not in catalog.skills:
                errors.append(f"{name}: missing dependency {dependency}")
        if item.get("ownership") == "vendored":
            origin = item.get("origin") or {}
            if not origin.get("source") or not origin.get("path"):
                errors.append(f"{name}: vendored entry needs origin.source and origin.path")
            elif origin["source"] not in catalog.skills_doc.get("sources", {}):
                errors.append(f"{name}: unknown origin source {origin['source']}")

        directory = catalog.root / item.get("path", "")
        if not directory.is_dir():
            errors.append(f"{name}: missing directory {item.get('path')}")
            continue
        if not (directory / "SKILL.md").is_file():
            errors.append(f"{name}: missing SKILL.md")
            continue
        fields = parse_frontmatter(directory / "SKILL.md")
        if not fields:
            errors.append(f"{name}: SKILL.md has no YAML frontmatter")
            continue
        if fields.get("name") != name:
            errors.append(f"{name}: SKILL.md declares {fields.get('name')!r}")
        description = fields.get("description") or ""
        if not description:
            errors.append(f"{name}: SKILL.md needs a description")
        elif len(description) > 1024:
            errors.append(f"{name}: description is {len(description)} characters; the limit is 1024")
        compatibility = fields.get("compatibility")
        if compatibility is not None and len(compatibility) > 500:
            errors.append(f"{name}: compatibility must be at most 500 characters")
        declares_user_only = (fields.get("disable-model-invocation") or "").strip().lower() == "true"
        if declares_user_only != (item.get("invocation") == "user"):
            errors.append(
                f"{name}: invocation {item.get('invocation')!r} disagrees with"
                " disable-model-invocation in SKILL.md"
            )


def validate_workflows(catalog: Catalog, errors: list[str]) -> None:
    for workflow in catalog.workflows_doc.get("workflows", []):
        if workflow.get("entry") not in workflow.get("skills", []):
            errors.append(f"workflow {workflow.get('id')}: entry is not in skills")
        for name in workflow.get("skills", []):
            if name not in catalog.skills:
                errors.append(f"workflow {workflow.get('id')}: unknown skill {name}")
        members = set(workflow.get("skills", []))
        workflow_entries = set(workflow.get("entries", [workflow.get("entry")]))
        if not workflow_entries or not workflow_entries.issubset(members) or workflow.get("entry") not in workflow_entries:
            errors.append(f"workflow {workflow['id']}: invalid entries")
        covered = set(workflow_entries)
        graph = {name: [] for name in members}
        for relation in workflow.get("relations", []):
            start, end, kind = relation.get("from"), relation.get("to"), relation.get("type")
            if start not in members or end not in members or start == end:
                errors.append(f"workflow {workflow['id']}: invalid relation endpoints")
                continue
            covered.update((start, end))
            if kind not in RELATION_TYPES:
                errors.append(f"workflow {workflow['id']}: invalid relation type")
            if kind in {"choice", "optional"} and not relation.get("when"):
                errors.append(f"workflow {workflow['id']}: conditional relation needs when")
            if kind == "sequence":
                graph[start].append(end)
        if covered != members:
            errors.append(f"workflow {workflow['id']}: skills missing relationships")
        visiting, visited = set(), set()

        def cyclic(node):
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            if any(cyclic(child) for child in graph[node]):
                return True
            visiting.remove(node)
            visited.add(node)
            return False

        if any(cyclic(node) for node in graph):
            errors.append(f"workflow {workflow['id']}: sequence cycle")


def validate_discovery(catalog: Catalog, errors: list[str]) -> None:
    discovered = {
        skill_file.parent.relative_to(catalog.root).as_posix()
        for skill_file in catalog.root.glob(f"{SKILLS_DIR}/*/SKILL.md")
    }
    registered = {item["path"] for item in catalog.skills_doc["skills"]}
    for path in sorted(discovered - registered):
        errors.append(f"unregistered skill directory: {path}")
    for path in sorted(registered - discovered):
        errors.append(f"registered path is not discoverable: {path}")


def validate_sources(catalog: Catalog, errors: list[str]) -> None:
    for source_id, source in catalog.skills_doc.get("sources", {}).items():
        excluded_names = [item.get("name") for item in source.get("exclusions", [])]
        duplicate_exclusions = sorted({name for name in excluded_names if excluded_names.count(name) > 1})
        if duplicate_exclusions:
            errors.append(f"{source_id}: duplicate exclusions: {', '.join(duplicate_exclusions)}")
        selected = catalog.selected(source_id)
        overlap = sorted({item["name"] for item in selected}.intersection(excluded_names))
        if overlap:
            errors.append(f"{source_id}: selected and excluded: {', '.join(overlap)}")
        group = source.get("plugin")
        if group not in catalog.group_names():
            errors.append(f"{source_id}: unknown group {group}")
        lock_path = catalog.root / source["lockPath"]
        if not lock_path.is_file():
            errors.append(f"{source_id}: missing lock {source['lockPath']}")
            continue
        lock = load_json(lock_path)
        locked = {item["name"]: item for item in lock.get("skills", [])}
        if set(locked) != {item["name"] for item in selected}:
            errors.append(f"{source_id}: lock selection differs from registry")
        excluded_paths = tuple(lock.get("excludedPaths", VENDOR_EXCLUDED_PATHS))
        for item in selected:
            lock_item = locked.get(item["name"])
            local = catalog.root / item["path"]
            if not local.is_dir() or not lock_item:
                continue
            if lock_item.get("path") != item["path"]:
                errors.append(f"{item['name']}: locked path differs from registry")
            if lock_item.get("sourcePath") != (item.get("origin") or {}).get("path"):
                errors.append(f"{item['name']}: locked sourcePath differs from registry")
            if tree_digest(local, excluded_paths) != lock_item.get("treeSha256"):
                errors.append(f"{item['name']}: vendored content differs from lock")
            for relative in excluded_paths:
                if (local / relative).exists():
                    errors.append(f"{item['name']}: vendored tree ships an excluded path ({relative})")
        if group in catalog.group_names():
            group_root = catalog.root / GROUPS_DIR / group
            if not (group_root / source["licensePath"]).is_file():
                errors.append(f"{source_id}: preserved license is missing")
            if not (group_root / "THIRD_PARTY_NOTICES.md").is_file():
                errors.append(f"{source_id}: third-party notice is missing")


def validate_groups(catalog: Catalog, errors: list[str]) -> None:
    names = catalog.group_names()
    if not names:
        errors.append(f"no group definitions found under {GROUPS_DIR}")
    for group in names:
        if not PLUGIN_NAME.match(group) or len(group) > 64:
            errors.append(f"{group}: group name does not satisfy {PLUGIN_NAME.pattern}")
        manifest_path = catalog.package_path(group)
        if not manifest_path.is_file():
            errors.append(f"{group}: missing package.json")
            continue
        manifest = catalog.package(group)
        if manifest.get("name") != group:
            errors.append(f"{group}: package.json name mismatch")
        base = str(manifest.get("version", ""))
        if not SEMVER.match(base.split("+")[0]):
            errors.append(f"{group}: version must start with a semantic x.y.z release")
        if not manifest.get("description"):
            errors.append(f"{group}: package.json needs a description")
        extra = sorted(set(manifest) - PLUGIN_KEYS - {"skills"})
        if extra:
            errors.append(f"{group}: package.json has fields outside the plugin schema: {', '.join(extra)}")
        author = manifest.get("author")
        if author is not None:
            if not isinstance(author, dict) or set(author) - AUTHOR_KEYS or not author.get("name"):
                errors.append(f"{group}: author must be an object with a name")
        skills = manifest.get("skills")
        if not isinstance(skills, list) or len(skills) != len(set(skills)):
            errors.append(f"{group}: skills must be a duplicate-free list")
        else:
            declared, registered = set(skills), {item["name"] for item in catalog.group_skills(group)}
            if declared != registered:
                missing = ", ".join(sorted(registered - declared)) or "none"
                stale = ", ".join(sorted(declared - registered)) or "none"
                errors.append(f"{group}: package skills differ from registry (missing {missing}; stale {stale})")
        extensions = manifest.get("extensions")
        if extensions is not None:
            if not isinstance(extensions, dict):
                errors.append(f"{group}: extensions must be an object")
            else:
                for namespace, payload in extensions.items():
                    if not NAMESPACE.match(namespace):
                        errors.append(f"{group}: extension key {namespace!r} is not a reverse-domain namespace")
                    if not isinstance(payload, dict):
                        errors.append(f"{group}: extension {namespace!r} must be an object")
                    elif isinstance(payload, dict) and isinstance(payload.get("icon"), str):
                        if not (catalog.root / GROUPS_DIR / group / payload["icon"]).is_file():
                            errors.append(f"{group}: extension icon {payload['icon']} is missing")
        plugin = plugin_manifest(catalog, group)
        if plugin["version"] != f"{base}+content.{packaged_digest(catalog, group)[:16]}":
            errors.append(f"{group}: derived version is inconsistent")
        built = catalog.root / DIST_DIR / group / "plugin.json"
        if built.is_file() and load_json(built) != plugin:
            errors.append(f"{group}: dist/{group}/plugin.json is stale; run build")


def validate_generated(catalog: Catalog, errors: list[str]) -> None:
    catalog_path = catalog.root / CATALOG_PATH
    if not catalog_path.is_file() or catalog_path.read_text(encoding="utf-8") != render_catalog(catalog):
        errors.append("generated workflow catalog is stale; run render-catalog --apply")
    stage_target = stage_guide_target(catalog)
    if stage_target is not None:
        if not stage_target.is_file() or stage_target.read_text(encoding="utf-8") != render_stage_guide(catalog):
            errors.append("generated stage guide is stale; run render-catalog --apply")


def validate(catalog: Catalog) -> int:
    errors: list[str] = []
    validate_skills(catalog, errors)
    validate_workflows(catalog, errors)
    validate_discovery(catalog, errors)
    validate_sources(catalog, errors)
    validate_groups(catalog, errors)
    validate_generated(catalog, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {len(catalog.skills_doc.get('skills', []))} skills and"
          f" {len(catalog.workflows_doc['workflows'])} workflows validated")
    return 0


# -- inventory and upstream maintenance -----------------------------------

def inventory(catalog: Catalog, as_json: bool) -> int:
    if as_json:
        print(json.dumps(catalog.skills_doc["skills"], indent=2, ensure_ascii=False))
        return 0
    print(f"{'SKILL':32} {'GROUP':18} {'OWNER':9} {'CALL':6} LOCATION")
    for item in sorted(catalog.skills_doc["skills"], key=lambda value: value["name"]):
        print(f"{item['name']:32} {item.get('plugin') or '—':18} {item['ownership']:9}"
              f" {item['invocation']:6} {item['path']}")
    return 0


def remote_head(source: dict) -> str:
    output = run(["git", "ls-remote", source["repository"], f"refs/heads/{source['branch']}"])
    if not output:
        raise RuntimeError(f"branch not found: {source['branch']}")
    return output.split()[0]


def check_upstream(catalog: Catalog, source_id: str, require_current: bool = False) -> int:
    source = catalog.source(source_id)
    head = remote_head(source)
    lock_path = catalog.root / source["lockPath"]
    locked = load_json(lock_path).get("commit") if lock_path.is_file() else None
    print(f"source:  {source_id}")
    print(f"locked:  {locked or 'none'}")
    print(f"upstream:{head}")
    current = locked == head
    print("status:  " + ("current" if current else "update available"))
    return 1 if require_current and not current else 0


def checkout_source(source: dict, ref: str, destination: Path) -> tuple[str, str]:
    run(["git", "clone", "--quiet", source["repository"], str(destination)])
    run(["git", "checkout", "--quiet", ref], cwd=destination)
    commit = run(["git", "rev-parse", "HEAD"], cwd=destination)
    committed_at = run(["git", "show", "-s", "--format=%cI", "HEAD"], cwd=destination)
    return commit, committed_at


def swap_directory(staging: Path, target: Path, backup: Path) -> None:
    try:
        if target.exists():
            os.replace(target, backup)
        os.replace(staging, target)
    except Exception:
        if target.exists():
            shutil.rmtree(target)
        if backup.exists():
            os.replace(backup, target)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)


@transactional
def sync_vendor(catalog: Catalog, source_id: str, ref: str | None, apply: bool) -> int:
    source = catalog.source(source_id)
    selected = catalog.selected(source_id)
    if not selected:
        raise ValueError(f"no skills selected for source: {source_id}")
    requested_ref = ref or remote_head(source)
    with tempfile.TemporaryDirectory(prefix=f"skill-sync-{source_id}-") as temporary:
        checkout = Path(temporary) / "upstream"
        commit, committed_at = checkout_source(source, requested_ref, checkout)
        stage = Path(temporary) / "skills"
        stage.mkdir()
        excluded_paths = tuple(source.get("excludedPaths", VENDOR_EXCLUDED_PATHS))
        lock_skills, changed = [], []
        for item in sorted(selected, key=lambda value: value["name"]):
            source_path = checkout / item["origin"]["path"]
            if not source_path.is_dir():
                raise RuntimeError(f"upstream path missing: {item['origin']['path']}")
            if frontmatter_name(source_path) != item["name"]:
                raise RuntimeError(f"upstream name mismatch for {item['name']}")
            destination = stage / item["name"]
            shutil.copytree(source_path, destination)
            upstream_digest = tree_digest(destination)
            removed = []
            for relative in excluded_paths:
                target = destination / relative
                if target.is_file():
                    target.unlink()
                    removed.append(relative)
            for directory in sorted((p for p in destination.rglob("*") if p.is_dir()),
                                    key=lambda p: len(p.parts), reverse=True):
                if not any(directory.iterdir()):
                    directory.rmdir()
            digest = tree_digest(destination)
            local = catalog.root / item["path"]
            if not local.is_dir() or tree_digest(local, excluded_paths) != digest:
                changed.append(item["name"])
            lock_skills.append({
                "name": item["name"],
                "sourcePath": item["origin"]["path"],
                "path": item["path"],
                "treeSha256": digest,
                "upstreamTreeSha256": upstream_digest,
                "excludedPaths": list(excluded_paths),
            })
            if removed != list(excluded_paths):
                print(f"note: {item['name']} upstream excluded paths removed: {removed}")

        license_source = checkout / source["licensePath"]
        if not license_source.is_file():
            raise RuntimeError(f"upstream license missing: {source['licensePath']}")
        print(f"source:  {source_id}")
        print(f"commit:  {commit}")
        print("changed: " + (", ".join(changed) if changed else "none"))
        if not apply:
            print("dry run; pass --apply to replace the selected vendored skills")
            return 0

        skills_root = catalog.root / SKILLS_DIR
        for item in sorted(selected, key=lambda value: value["name"]):
            staging = skills_root / f".{item['name']}.{uuid.uuid4().hex}.staging"
            backup = skills_root / f".{item['name']}.{uuid.uuid4().hex}.backup"
            shutil.copytree(stage / item["name"], staging)
            swap_directory(staging, skills_root / item["name"], backup)

        group_root = catalog.root / GROUPS_DIR / source["plugin"]
        shutil.copy2(license_source, group_root / source["licensePath"])
        lock = {
            "schemaVersion": 2,
            "source": source_id,
            "repository": source["repository"],
            "branch": source["branch"],
            "commit": commit,
            "committedAt": committed_at,
            "license": source["license"],
            "licensePath": source["licensePath"],
            "excludedPaths": list(excluded_paths),
            "skills": lock_skills,
        }
        atomic_json(catalog.root / source["lockPath"], lock)

        write_catalog(catalog, True)
        print("sync applied")
        return 0


@transactional
def remove_skill(catalog: Catalog, name: str, apply: bool) -> int:
    item = catalog.skills.get(name)
    if not item:
        raise ValueError(f"unknown skill: {name}")
    if item.get("ownership") != "vendored":
        raise ValueError("remove only automates vendored skills; review original skills manually")
    dependency_blockers = sorted(
        other["name"] for other in catalog.skills_doc["skills"] if name in other.get("requires", [])
    )
    workflow_blockers = sorted(
        workflow["id"] for workflow in catalog.workflows_doc["workflows"] if name in workflow["skills"]
    )
    if dependency_blockers or workflow_blockers:
        if dependency_blockers:
            print("blocked by skill dependencies: " + ", ".join(dependency_blockers))
        if workflow_blockers:
            print("blocked by workflows: " + ", ".join(workflow_blockers))
        return 1
    print(f"ready to remove complete directory: {item['path']}")
    if not apply:
        print("dry run; pass --apply after the exact removal is approved")
        return 0

    target = (catalog.root / item["path"]).resolve()
    expected_parent = (catalog.root / SKILLS_DIR).resolve()
    if not target.is_relative_to(expected_parent) or target == expected_parent or target.name != name:
        raise RuntimeError("refusing removal outside the shared skills directory")
    shutil.rmtree(target)

    catalog.skills_doc["skills"] = [entry for entry in catalog.skills_doc["skills"] if entry["name"] != name]
    del catalog.skills[name]
    catalog.save_skills()

    group = item.get("plugin")
    if group and catalog.package_path(group).is_file():
        manifest = catalog.package(group)
        manifest["skills"] = [entry for entry in manifest.get("skills", []) if entry != name]
        catalog.save_package(group, manifest)

    source = catalog.source(item["origin"]["source"])
    lock_path = catalog.root / source["lockPath"]
    lock = load_json(lock_path)
    lock["skills"] = [entry for entry in lock["skills"] if entry["name"] != name]
    atomic_json(lock_path, lock)

    write_catalog(catalog, True)
    print("removed; tracked content remains recoverable from Git")
    return 0


# -- package build --------------------------------------------------------

def package_stale(catalog: Catalog, group: str) -> bool:
    root = catalog.root / DIST_DIR / group
    manifest = root / "plugin.json"
    if not manifest.is_file() or load_json(manifest) != plugin_manifest(catalog, group):
        return True
    for item in catalog.group_skills(group):
        built = root / "skills" / item["name"]
        if not built.is_dir() or tree_digest(built) != tree_digest(catalog.root / item["path"]):
            return True
    return False


def build(catalog: Catalog, group: str | None, check: bool) -> int:
    names = [group] if group else catalog.group_names()
    for name in names:
        if name not in catalog.group_names():
            raise ValueError(f"unknown group: {name}")
    stale = [name for name in names if package_stale(catalog, name)]
    if check:
        if stale:
            print("stale packages: " + ", ".join(stale))
            print("run: skill_manager.py build")
            return 1
        print(f"OK: {len(names)} package(s) up to date")
        return 0

    destination = catalog.root / DIST_DIR
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        staging = destination / f".{name}.{uuid.uuid4().hex}.staging"
        backup = destination / f".{name}.{uuid.uuid4().hex}.backup"
        shutil.copytree(
            catalog.root / GROUPS_DIR / name, staging,
            ignore=shutil.ignore_patterns(*PACKAGE_EXCLUDED_NAMES),
        )
        skills_root = staging / "skills"
        skills_root.mkdir()
        for item in catalog.group_skills(name):
            shutil.copytree(catalog.root / item["path"], skills_root / item["name"])
        atomic_json(staging / "plugin.json", plugin_manifest(catalog, name))
        swap_directory(staging, destination / name, backup)
        print(f"built {DIST_DIR}/{name}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    root.add_argument("--repo", type=Path, default=DEFAULT_ROOT)
    commands = root.add_subparsers(dest="command", required=True)
    inventory_parser = commands.add_parser("inventory")
    inventory_parser.add_argument("--json", action="store_true")
    commands.add_parser("validate")
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--group")
    build_parser.add_argument("--check", action="store_true")
    doctor_parser = commands.add_parser("doctor")
    doctor_parser.add_argument("--project", type=Path, required=True)
    selection = doctor_parser.add_mutually_exclusive_group()
    selection.add_argument("--skill")
    selection.add_argument("--workflow")
    doctor_parser.add_argument("--spec")
    doctor_parser.add_argument("--json", action="store_true")
    render_parser = commands.add_parser("render-catalog")
    render_parser.add_argument("--apply", action="store_true")
    check_parser = commands.add_parser("check-upstream")
    check_parser.add_argument("--source", required=True)
    check_parser.add_argument("--require-current", action="store_true")
    sync_parser = commands.add_parser("sync-vendor")
    sync_parser.add_argument("--source", required=True)
    sync_parser.add_argument("--ref")
    sync_parser.add_argument("--apply", action="store_true")
    remove_parser = commands.add_parser("remove")
    remove_parser.add_argument("--skill", required=True)
    remove_parser.add_argument("--apply", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        catalog = Catalog(args.repo)
        if args.command == "inventory":
            return inventory(catalog, args.json)
        if args.command == "validate":
            return validate(catalog)
        if args.command == "build":
            return build(catalog, args.group, args.check)
        if args.command == "doctor":
            from project_doctor import doctor
            return doctor(catalog, args.project, args.skill, args.workflow, args.spec, args.json)
        if args.command == "render-catalog":
            return write_catalog(catalog, args.apply)
        if args.command == "check-upstream":
            return check_upstream(catalog, args.source, args.require_current)
        if args.command == "sync-vendor":
            return sync_vendor(catalog, args.source, args.ref, args.apply)
        if args.command == "remove":
            return remove_skill(catalog, args.skill, args.apply)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
