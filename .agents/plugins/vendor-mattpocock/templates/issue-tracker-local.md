# Local Markdown issue tracker

Copy and tailor this document as docs/agents/issue-tracker.md in a project using the local tracker.

## Storage and identity

Use one feature directory under .scratch/<feature-slug>/. Store implementation tickets at issues/<NN>-<slug>.md in dependency order. The identity is the full feature-relative path, not a bare number across features. Read the complete ticket and its linked context before changing it.

Each implementation ticket records its title, end-to-end behavior, acceptance criteria, Blocked by, category, status, and assignee. Use the project's triage-labels.md mapping. Store discussion and verification evidence beneath the ticket in dated sections. Closed status and triage status are distinct: record Closed: true/false explicitly.

Query by reading ticket metadata. Resolve an explicitly supplied path directly; when a bare number is ambiguous, ask which feature it belongs to. External PR discovery is disabled.

## Blocking and frontier

Blocked by lists full relative ticket paths, or None. A ticket can be taken when it is open, unassigned, and every blocker is closed with evidence of completion. Check dependencies for cycles. Before starting, record the assignee; concurrent workers need a serialized claim mechanism or separate coordinated assignments because plain files do not provide atomic distributed claims.

## Wayfinding operations

Store one map at .scratch/<feature-slug>/map.md. Store its decision tickets under decisions/<NN>-<slug>.md. The map contains Destination, Notes, Decisions so far, Not yet specified, and Out of scope. Each decision ticket records its question, parent map, wayfinder type (research/prototype/grilling/task), Blocked by, assignee, and Closed flag.

Query open children to find pending decisions. Claim before work. Resolve by appending the answer and evidence to the decision ticket, mark it closed, and add a named link with a one-line gist to the map. Keep decision details in the ticket rather than duplicating them in the map. Unspecified in-scope questions remain in the map until they can become concrete tickets.

## Publishing and updates

Publishing means creating a local file. Updating means editing the existing canonical file, preserving prior decisions and evidence. Closing means setting Closed: true, not deleting the file. Parent tickets are not closed automatically when children are published. Follow the selected skill's required review points and the user's authorized scope.
