# Agents Skills

A vendor-neutral library of agent skills, workflow routes, and generated plugin packages.

Skills use the [Agent Skills](https://agentskills.io/specification) layout at
`.agents/skills/<name>/SKILL.md`, the de-facto cross-client path. Packages use the
[Agent Plugins 1.0](https://agent-plugins.org) manifest and are generated from the skills, never
hand-edited.

## Layout

| Path | Role |
|---|---|
| `.agents/skills/<name>/` | Every skill, exactly one copy. Source of truth. |
| `.agents/plugins/<group>/` | Group definition (`package.json`) plus files shared by that group. No skill content. |
| `registry/skills.json` | Catalog metadata: ownership, invocation, dependencies, upstream pins. |
| `registry/workflows.json` | Maintained task routes across skills. |
| `dist/<group>/` | Generated Agent Plugins package. Gitignored; build it locally. |
| `.agents/skills/skill-maintainer/` | Repository-only tooling. Never shipped inside a package. |

## Use a skill

No vendor-neutral marketplace or registry format exists yet, so nothing here is installed by a
marketplace command. Pick the mechanism your client supports:

- **Client reads `.agents/skills/`** — clone this repository inside the project, or copy the skill
  directories you want. A client with a global convention reads `~/.agents/skills/`.
- **Client supports Agent Plugins** — build the packages and point the client at `dist/<group>/`.
- **Agent instructions** — [AGENTS.md](AGENTS.md) documents the repository's own rules.

```bash
git clone https://github.com/soralcf/agents-skills.git
python3 .agents/skills/skill-maintainer/scripts/skill_manager.py build
```

## Groups

| Group | Skills | Contents |
|---|---|---|
| `learn-anything` | 1 | Adaptive explanations, guided deep dives, and learning roadmaps. |
| `vendor-mattpocock` | 23 | Pinned MIT-licensed Matt Pocock skills in nine work stages, with unchanged skill content. See the [stage guide](.agents/plugins/vendor-mattpocock/README.md). |
| `workflow-hub` | 1 | Navigate and audit the skill library. See the generated [workflow catalog](.agents/skills/workflow-guide/references/catalog.md). |

## Maintain the repository

```bash
python3 .agents/skills/skill-maintainer/scripts/skill_manager.py inventory
python3 .agents/skills/skill-maintainer/scripts/skill_manager.py validate
python3 .agents/skills/skill-maintainer/scripts/skill_manager.py build --check
python3 .agents/skills/skill-maintainer/scripts/test_skill_manager.py
```

`validate` is the single gate: it checks the Agent Skills layout and frontmatter, the registries,
the workflow graph, every vendored tree against its lock, every group definition against the Agent
Plugins schema, and whether the generated catalog, stage guide, and packages are stale. Read
[skill-maintainer](.agents/skills/skill-maintainer/SKILL.md) before importing, syncing, or removing
anything.

## Vendoring policy

A vendored skill directory is a byte-identical copy of a pinned upstream commit, minus the upstream
`agents/openai.yaml` client overlay. That exclusion is declared in
`.agents/plugins/vendor-mattpocock/UPSTREAM.lock.json` alongside both the upstream and the shipped
tree digests, so either side is reproducible. Vendored `SKILL.md` files are never patched locally;
behavioral changes belong in a new, separately named original skill.
