# Registry schema

`registry/skills.json` is the source of truth for availability and provenance.

Each skill entry contains:

- `name`: unique Skill frontmatter name; it must equal the directory name.
- `summary`: one-line human description used by the generated navigation.
- `plugin`: owning group, or `null` for a repository-only Skill.
- `ownership`: `original` or `vendored`.
- `scope`: `plugin` or `repository`.
- `invocation`: `user` or `model`; it must agree with `disable-model-invocation` in `SKILL.md`.
- `status`: lifecycle state; currently `active`.
- `path`: repository-relative directory containing `SKILL.md`; always `.agents/skills/<name>`.
- `stage`: optional navigation stage id from top-level `stages`.
- `origin`: required for vendored entries; contains a source id and upstream directory path.
- `requires`: hard Skill dependencies that must be present. Optional or contextual relationships do
  not belong here.
- `prerequisites`: project configuration and input artifacts, not installable dependencies.

Top-level `sources` defines the upstream repository, branch, license, group, and lock path. Its
`exclusions` array records stable upstream Skill paths that were deliberately not selected and the
current reason. Move or remove an exclusion when the decision changes; never leave one name in both
the selected Skill list and exclusions.

`registry/workflows.json` contains named compositions. Each workflow has an `id`, human title,
primary `entry`, optional `entries`, member `skills`, typed `relations`, and desired `outcome`.
Relations use `sequence`, `optional`, `calls`, `choice`, or `alongside`; conditional choices and
optional edges include `when`. Every member is an entry or participates in a relation. Sequence
edges must be acyclic. The member list records coverage and does not imply an execution order.

The generated `workflow-guide/references/catalog.md` is a distribution artifact, not a source of
truth. Regenerate it from both JSON registries.

## Group definitions

`.agents/plugins/<group>/package.json` is the group source of truth. Its keys are the Agent Plugins
1.0 manifest fields plus `skills`:

- `name`, `version` (a semantic `x.y.z` base), and `description` are required.
- `$schema`, `author`, `homepage`, `repository`, `license`, and `keywords` are optional manifest
  fields.
- `extensions` is keyed by reverse-domain namespace. Client-specific presentation metadata lives
  under `org.soralcf.presentation`, because no portable manifest field carries it.
- `skills` lists exactly the registry entries whose `plugin` is this group.

`build` derives `dist/<group>/plugin.json` from this file, adds the schema URL, and computes the
published version as `<base>+content.<digest>`, where the digest covers every packaged skill tree.
Any content change therefore invalidates an installed copy. `package.json` and
`UPSTREAM.lock.json` never ship inside a package.

## Stage navigation and vendored locks

- Top-level `stages` lists ordered ids and titles. Numbers aid navigation, not mandatory execution.
- `stage` places a skill in that navigation only; it is not part of `path`.
- The lock records, per skill, `path`, `sourcePath`, `treeSha256` for the shipped tree,
  `upstreamTreeSha256` for the tree before exclusions, and `excludedPaths`. A vendored tree must
  match `treeSha256` with `excludedPaths` applied, and must not contain an excluded path.

`render-catalog --apply` also generates the staged group's `README.md` stage/dependency index.
WORKFLOWS.md and PROJECT-SETUP.md are maintained packaging documentation.
