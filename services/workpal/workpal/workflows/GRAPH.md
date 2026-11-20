# Workflow graph Interface

`compile_graph(definition) -> GraphSnapshot` is pure and performs no database reads,
Run dispatch, Issue transitions or runtime calls. `evaluate_condition(condition,
values, declared_fields) -> bool` reads complete literal string keys only.
Failures are DomainError invalid_graph/invalid_condition with status 400 and generic
messages that omit condition values. No app registration or settings are needed.

The closed root is `{nodes, edges, declared_fields}`. Nodes contain exactly
`id,type,config`; edges exactly `from,to,on,required,max_traversals`. Node IDs
match `[a-z][a-z0-9_]{0,63}`. There are 2–200 nodes, at most 1000 edges and
100 distinct nonempty declared field strings. Edge counters are integers 0–100;
booleans are rejected. Duplicate source/target/label edges are rejected even if
counter or required flags differ.

Types/config: start/end/parallel `{}`; join `{mode:'all_required'}`;
human_decision/delivery_review `{reviewer_roles:[owner|admin|member]}`;
agent_task `{agent_id:positive integer,input_refs:[strings]}`;
create_child `{title:nonblank string,description:string}`;
condition `{condition:{field,op,value}}`. Only exists may omit value.
Conditions support eq/ne/in/exists/gt/gte/lt/lte; exists value is a boolean,
default true. `in` accepts at most 100 values. JSON values must be finite,
with nesting limited to 32. Numeric ordered comparisons reject bool and
nonnumeric operands by returning false; invalid comparison constants are errors.
Equality is type-sensitive. Missing fields always return false except exists false.

Exactly one start, at least one end, forward and reverse reachability are
required. Remove every positively bounded edge: the remainder must be acyclic.
Condition branches have exactly true/false edges; review decisions require both
approved/rejected labels. Other nodes use always and only parallel may fan out.
Join requires a required incoming edge and preserves optional edges unchanged.

Snapshots are detached JSON objects with schema_version 1, normalized definition,
and SHA256 of UTF-8 canonical definition JSON (sorted keys, compact separators,
unescaped Unicode). Nodes sort by ID, edges by source/target/label, declared fields
and reviewer roles sort lexically. Lists whose ordering may carry content remain
ordered. Returned dictionaries are mutable but have no shared state across calls;
a caller modifying a snapshot must recompile before trusting its hash.

C2b immutable publication/version storage and C2c instance progression, selected
branches, optional joins, counter consumption and B dispatch are not connected.
This structural check does not prove execution completion or authorization.

Specification clarification: the parallel plan permits condition fan-out while
its later phrase allows multiple outputs “only parallel or above decision nodes”.
This implementation treats condition as a decision node, as required by its
mandatory true/false branches. The plan does not specify field-name length or in
array bound: fields remain literal nonempty strings and in is capped at 100.
Numeric JSON int/float equality is intentionally type-sensitive; integration
should ratify this choice before persisted definition compatibility is promised.

Review clarification: eq/ne/in compare JSON recursively. Booleans are distinct
from numbers; integer and float representations compare numerically. Arrays
retain order; object key order is irrelevant. Missing fields differ from null.
Hashing uses canonical JSON representation and does not promise equal hashes
for numerically equivalent integer/float representations. Decision nodes have
exactly one edge per outcome; parallel is required for fan-out. Invalid Unicode
and serialization failures return sanitized DomainError. No execution or
traversal-count consumption is implemented by this Module.

Graph persistence uses independent GraphDraft and GraphVersion tables. The six
`workflows.persistence` Interfaces create, update, publish, read, read_version and
list_drafts accept no idempotency key. Registry actions `workflow_graph.*` own
idempotency, auditing and outbox writes in the same transaction. Published JSON
and resolved input references are detached immutable facts; graph hashes come
only from compile_graph. Publishing advances draft revision and version pointer
atomically. Sources accumulate and current grants apply to historical reads and
cached action replay. Input references use `kind:id`, never executable strings.
No instance, Run, agent dispatch or execution is created by these Interfaces.

Graph instances now expose `instances.initialize(actor, SubjectRef('issue', id),
version_id, key)` through the Registry and `instances.read(actor, instance_id)`.
Initialization saves an immutable `initialized` fact with protected references,
exact requirements history, current admitted Agent configuration, frozen graph
version and input references, and a canonical SHA256 of the complete snapshot.
The Registry owns idempotency and the enclosing audit transaction. Replays check
current subject write, saved sources read and current initialization admission;
historical reads require only saved content read. No Run or node execution is
started. Listing, instance concurrency and migration upgrade matrix remain Task2b.

Historical instance listing: `list_instances(actor, cursor=0, limit=50)` and
`workflow_graph.instance.list` return only `{items, next_cursor}`. Each item has
`id`, `version_id`, `subject`, `state`, `sha256`, and `created_at`; use instance
read for the saved snapshot. Current membership and saved-source read access
are checked before pagination in ascending primary-key order. Only 403 candidates
are skipped; storage failures propagate. A nonzero cursor names the last returned
visible instance only when another visible item exists. Registry access audit
contains exactly the returned instances and their current source scope; Direct
listing writes nothing. Listing does not repeat execution admission or require
subject write access. Snapshot columns may be loaded for identity validation.
