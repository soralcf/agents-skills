# Repository instructions

This repository is a vendor-neutral agent skill library. Skills are plain
[Agent Skills](https://agentskills.io/specification) directories; plugin packages are generated
from them.

## Non-negotiables

- Every skill exists exactly once, at `.agents/skills/<name>/SKILL.md`, and the directory name must
  equal the frontmatter `name`.
- `.agents/skills/` and `registry/` are the only sources of truth. Everything under `dist/`, plus
  the generated `catalog.md` and each group's `README.md`, is build output.
- Never hand-edit generated files: `dist/**`,
  `.agents/skills/workflow-guide/references/catalog.md`, and
  `.agents/plugins/<group>/README.md`. Change the registries or the generator instead.
- Never modify the content of a vendored skill. `registry/skills.json` marks them
  `ownership: vendored`, and each tree must keep matching
  `.agents/plugins/vendor-mattpocock/UPSTREAM.lock.json`. Behavioral changes belong in a new,
  separately named original skill.
- Vendored trees never contain `agents/openai.yaml`. That upstream overlay is excluded and recorded
  in the lock as `excludedPaths`; `validate` fails if one reappears.
- A group's `.agents/plugins/<group>/package.json` is publishing metadata only. It carries no skill
  content and no keys outside the Agent Plugins 1.0 manifest plus `skills`.
- `dist/` is gitignored and must not be committed.

## Layout

| Path | Role |
|---|---|
| `.agents/skills/<name>/` | One skill: `SKILL.md` plus optional `scripts/`, `references/`, `assets/`. |
| `.agents/plugins/<group>/` | Group definition and group-level files such as a license or notice. |
| `registry/skills.json` | Catalog metadata. Source of truth for ownership, invocation, and pins. |
| `registry/workflows.json` | Maintained task routes. |
| `dist/<group>/` | Generated package. |

## Frontmatter rules

Keep only portable fields: `name`, `description`, `license`, `compatibility`, `metadata`,
`allowed-tools`. `name` must match the parent directory and `description` must stay under 1024
characters. Set `disable-model-invocation: true` exactly when the registry says
`invocation: user`; `validate` enforces the equivalence.

## Making a change

1. Edit the skill directory and/or the registries.
2. Run `python3 .agents/skills/skill-maintainer/scripts/skill_manager.py validate`.
3. Regenerate what you touched: `render-catalog --apply` for registry changes, `build` for
   packages.
4. Run `python3 .agents/skills/skill-maintainer/scripts/test_skill_manager.py`.
5. Read `.agents/skills/skill-maintainer/SKILL.md` before importing, syncing, or removing anything.
