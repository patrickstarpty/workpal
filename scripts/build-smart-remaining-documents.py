"""Build concrete handoff/decision/source-audit documents from recorded evidence."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/handoffs/smart-deliverables'
OUT=BASE/'specifications'
items=json.loads((BASE/'published-verification.json').read_text())
by_number={int(x['issue_id'].rsplit('-',1)[1]):x for x in items}
header='Revision 1. Prepared by Codex during the current evidence repair. No historical agent execution or owner acceptance is asserted.\n\n'

def write(n,title,body):
 (OUT/f'SMART-{n}.md').write_text('# '+title+'\n'+header+body+'\n')

refs='\n'.join(f"- SMART-{n}: revision `{by_number[n]['revision_id']}`; producing Activity `{by_number[n]['activity_id']}`." for n in (7,8,10,13,16))
gates='''
## Evidence gates
| Gate | Required material | Actual state |
| --- | --- | --- |
| Scope | Reviewed recovery requirements, exact version | SMART-13 revision 1 exists; review outstanding |
| Interaction | Recovery state and keyboard specification | SMART-8 revision 1 exists; review outstanding |
| Implementation | Scoped code diff and review/fix/recheck | No verified recovery feature diff identified |
| Regression | Executed transfer-recovery matrix | SMART-10 has 15 passing local cleanup/HTTP tests; browser resume cases remain uncovered |
| External storage | Isolated adapter verification | SMART-16 protocol exists; external cases not run |
| Release | Named operator, target and owner decision | No actual approval or deployment record |

## Rollback prerequisites and procedure
Before any release, the authorized operator must identify the exact previous application/configuration version and a tested database backup. Record backup digest, schema compatibility and restoration owner. Quiesce writes before a database restore, retain the current database as an incident artifact, restore only with explicit authorization, and validate workspace membership, attachment associations and a known content digest before reopening writes. Never treat the backups created for evidence publication as a tested production rollback package.

Stop the release if any gate is absent, the rollback has not been verified, or ownership is unacknowledged. These instructions have not been executed.

## Responsibility and acceptance ledger
Proposed preparer: Release Engineer. Proposed rollback verifier: Reliability Engineer. Decision authority: workspace owner. These are role assignments for the proposed process, not proof that a person accepted the handoff. Actual reviewer: none recorded. Accepted version: none. Open issues: resume API/implementation, browser regression, external storage verification and release/rollback authorization.
'''
for n,title,purpose in [(5,'Attachment release checklist','Prepare the package without releasing it.'),(11,'Workspace release readiness review','Assess the actual evidence package; readiness is not release authorization.'),(17,'Upload recovery release handoff','Receive SMART-7 implementation and SMART-10 verification only after their actual acceptance.')]:
 write(n,title,'## Purpose\n'+purpose+'\n\n## Exact input versions\n'+refs+'\n'+gates)

roles=json.loads((ROOT/'apps/web/app/capabilities/data/role-profiles.json').read_text())
raw=(ROOT/'apps/web/app/capabilities/data/role-profiles.json').read_bytes()
table='| Role | Recorded source |\n| --- | --- |\n'+'\n'.join(f"| {r['name']} | {r['sourceUrl']} |" for r in roles)
source='''## Inspected local baseline
Source: `apps/web/app/capabilities/data/role-profiles.json`.
SHA-256: `'''+hashlib.sha256(raw).hexdigest()+'''`.
The following URLs were read from the repository, not fetched from the remote services. This audit does not assert remote availability, latest revision or changed upstream content.

'''+table+'''

## Comparison protocol
For each role, retain its pinned URL/revision, request the candidate immutable revision, and compare the actual file contents. Report added/removed instructions, permission changes, renamed commands and impact on role responsibilities. Keep the current revision unchanged until an authorized reviewer accepts the exact proposed diff. If the upstream reference cannot be read, record the specific URL, timestamp, sanitized error and account scope; do not substitute a mirror or infer the contents.

## Current result and missing evidence
The inventory is complete for the 15 local role profiles. No remote comparison was performed. There is no captured remote failure response in the supplied SMART history; therefore the historical statement about missing repository access cannot be independently confirmed. No changed revision, approved source update or verified drift result is recorded.

## Handoff
Reliability Engineer is the proposed inventory owner. Repository owner must supply an approved snapshot or read access through the designated credential channel if needed. The receiving reviewer must name the exact old/new versions and affected roles. No such acknowledgement is present.
'''
write(6,'Pinned source inventory and drift review protocol',source)
write(18,'Source access investigation record',source+'\n## Access request contents\nSpecify the exact failing source from the inventory, required read scope and intended comparison. Do not ask for broad repository write access. An access request has not been sent by this audit.\n')

choices={
19:('Automatic ticket splitting decision analysis','Automatically create a new ticket at every phase transition.','Independent outcome, owner and acceptance scope determine whether to split.','A single recovery outcome spans design, implementation and verification. Splitting at every transition loses the acceptance chain and creates duplicate coordination.','Keep one ticket while the outcome remains the same; split when a distinct deliverable can be independently owned and accepted. Link both directions and name the retained acceptance scope.'),
20:('Mandatory phase gates decision analysis','Require every ticket to begin at planning and pass all phases.','Work may begin with supplied inputs at any stage.','A test request with a fixed build and accepted specification already has its inputs. Forcing a planning ticket adds no evidence and can hide what verification actually needs.','Require the inputs relevant to the requested work, not a fixed phase history. A release request still requires specific implementation, test and authorization evidence.'),
21:('Automatic run closure decision analysis','Mark the ticket done whenever a Run completes.','Run termination and accepted ticket outcome are separate decisions.','A completed code-generation Run may contain defects, missing tests or an unresolved review. A successful test Run may cover only part of the acceptance criteria.','Record the Run outcome, then review the produced version against ticket criteria. Close only after an authorized decision identifies the accepted materials and remaining scope.')}
for n,(title,proposal,principle,risk,alternative) in choices.items():
 write(n,title,f'''## Proposal examined
{proposal}

## Decision criterion
{principle}

## Failure example
{risk}

## Recommended alternative
{alternative}

## Verification cases
Check a single outcome crossing phases, independently owned work that genuinely needs a separate ticket, a failed Run, a completed Run with missing evidence, and a partial acceptance with open follow-up. Record the concrete input revisions and the actual human decision in each case. No test of an automatic policy engine is asserted here.

## Historical decision and current authority
The existing ticket says the proposal was declined. That statement comes from authored history; this audit has not found a contemporaneous authenticated owner decision with reviewed material. This document supplies the rationale for review now. It does not forge an original rejection or reopen the cancelled ticket automatically.

## Implementation scope
No automatic splitting, phase-gating or closure implementation is requested by this decision record. Preserve ticket and Run history. If the owner revisits the proposal, create a new explicit decision linked to this version rather than silently altering the old record.
''')
print('Built eight concrete handoff, source and decision documents')
