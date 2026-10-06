---
name: skill-maintainer
description: Maintain this repository's skill catalog. Use when inventorying skills, validating workflows and dependencies, checking or syncing vendored upstream skills, adding a source selection, building plugin packages, or safely removing a skill.
---

# Skill Maintainer

Maintain the repository as two planes:

- The source plane is `.agents/skills/` plus `registry/`: every skill exists once, and the
  registries record ownership, invocation, dependencies, and upstream pins.
- The published plane is generated: `dist/<group>/` holds Agent Plugins packages, and
  `workflow-guide` carries the generated workflow catalog.

Group definitions live in `.agents/plugins/<group>/package.json`. They name the skills a group
publishes and carry no skill content. Do not put maintenance commands into a published group.

## Start here

Run from the repository root:

```bash
python3 .agents/skills/skill-maintainer/scripts/skill_manager.py inventory
python3 .agents/skills/skill-maintainer/scripts/skill_manager.py validate
```

Read [references/maintenance-policy.md](references/maintenance-policy.md) before importing,
syncing, or removing anything. Read [references/registry-schema.md](references/registry-schema.md)
when changing a registry or a group definition.

## Choose the operation

- **Inventory or audit:** use `inventory` and `validate`. These are read-only.
- **Build packages:** run `build`; add `--group <name>` to limit the scope. Verify with
  `build --check`, which is read-only and fails while `dist/` is stale.
- **Check project prerequisites:** run `doctor --project <path>` with either `--skill <name>` or
  `--workflow <id>`. Add `--spec <path>` for a local spec. It only checks local presence and never
  runs configured commands or contacts a tracker.
- **Refresh generated documents:** run `render-catalog`; add `--apply` only when the generated diff
  is intended. This rewrites the workflow catalog and the staged group's `README.md`.
- **Check upstream:** run `check-upstream --source <id>`. Add `--require-current` in scheduled
  automation so an available update produces a failing signal. This is read-only but needs network
  access.
- **Sync selected third-party skills:** first run `sync-vendor --source <id>` without `--apply`.
  Review the commit and changed skill list, then run again with `--apply` when the user requested
  the update.
- **Add a third-party skill:** verify its license, add one `ownership: vendored` registry entry with
  an exact upstream path and reviewed hard dependencies, add it to the owning group's `skills` list,
  then use `sync-vendor`. Never copy an unregistered directory into `.agents/skills/`.
- **Remove a vendored skill:** run `remove --skill <name>` first. Use `--apply` only after the user
  chose that exact skill and the command reports no workflow or dependency blockers.
- **Create an original replacement:** use `skill-creator` and give it a new name. Never modify a
  vendored directory and relabel it as original.

After every applied change, run `validate`, run `build` so `dist/` matches, and inspect `git diff`.
Commits, pushes, and removal of separately installed local copies are separate actions; perform
them only when requested.
