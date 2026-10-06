# Skill maintenance policy

## Ownership classes

- `vendored`: a directory from a pinned upstream source. Preserve every upstream file. The upstream
  `agents/openai.yaml` client overlay is declared in the source's `excludedPaths` and is not part of
  the shipped tree; the lock keeps both the pre-exclusion and shipped digests so the omission stays
  auditable.
- `original`: maintained in this repository. It may learn from general ideas elsewhere, but must
  not silently preserve copied third-party text or assets.

If a vendored skill needs behavioral changes, remove it from the selection and design a new,
separately named original skill.

## Import requirements

Before selecting a third-party skill:

1. Verify the current upstream repository and exact source path.
2. Read the governing license and preserve every required notice.
3. Classify it as user-invoked or model-invoked from its unchanged metadata.
4. Record hard dependencies in `registry/skills.json` and select their transitive closure.
5. Check for overlap with original skills and platform-native behavior.
6. Pin one upstream commit in the source lock.

Do not import draft, deprecated, personal, or repository-specific routing/setup skills by default.
For the Matt package, retain original frontmatter even when a bundled static validator rejects it.
Report static-validator incompatibilities, and treat `validate` plus a reviewed `git diff` as the
gate. Never use directory omissions as validation evidence. Runtime failures remain blockers;
client metadata does not replace project prerequisites.

## Sync requirements

- Fetch into a temporary checkout.
- Copy only registered upstream paths, into `.agents/skills/<name>`.
- Remove every path listed in the source's `excludedPaths` and prune the directories it empties.
  Record the upstream digest before removal and the shipped digest after it.
- Replace each selected skill directory as a whole, not individual files.
- Refresh content hashes, the upstream commit, the preserved license, and the generated documents in
  the same operation.
- Derive the published package version from the packaged-content digest, so changing the selection
  at the same commit cannot reuse a stale installed cache.
- Review the upstream diff before applying a new commit.
- Serialize applied maintenance per repository. Snapshot `.agents/skills`, `.agents/plugins`, and
  `registry/` before mutation, reject stale in-memory registries, and restore the snapshot when any
  later write fails.

## Removal requirements

- Resolve the exact registry name.
- Refuse removal while another skill declares it in `requires` or a workflow references it.
- Remove the whole skill directory, its registry entry, its group membership, and its lock entry
  together.
- Do not claim a skill is unused without usage evidence. Static analysis can prove only that it is
  unreferenced or has overlapping responsibilities.

Tracked files remain recoverable from Git. The manager does not delete separately installed user
copies or caches.
