# Source access investigation record
Revision 1. Prepared by Codex during the current evidence repair. No historical agent execution or owner acceptance is asserted.

## Inspected local baseline
Source: `apps/web/app/capabilities/data/role-profiles.json`.
SHA-256: `4a4e11341c2c69755abcce5e0a5bf273bb356aaec4eb1b5002cda7add17e1db3`.
The following URLs were read from the repository, not fetched from the remote services. This audit does not assert remote availability, latest revision or changed upstream content.

| Role | Recorded source |
| --- | --- |
| Product Strategist | https://github.com/garrytan/gstack/blob/a529769efd989ac5e83e4ee09f1ac7b199e686d3/plan-ceo-review/SKILL.md |
| Software Architect | https://github.com/cursor/plugins/blob/aaeb0ea3a0584995aa8f55ce44c6c5259414b896/pstack/skills/architect/SKILL.md |
| Engineering Lead | https://github.com/garrytan/gstack/blob/a529769efd989ac5e83e4ee09f1ac7b199e686d3/plan-eng-review/SKILL.md |
| Implementation Engineer | https://github.com/mattpocock/skills/blob/abeeaf95660ba9e8b7c753eb38f441ca707a8823/skills/engineering/implement/SKILL.md |
| Code Reviewer | https://github.com/mattpocock/skills/blob/abeeaf95660ba9e8b7c753eb38f441ca707a8823/skills/engineering/code-review/SKILL.md |
| Maintenance Engineer | https://github.com/cursor/plugins/blob/aaeb0ea3a0584995aa8f55ce44c6c5259414b896/pstack/skills/poteto-mode/playbooks/bug-fix.md |
| Release Engineer | https://github.com/garrytan/gstack/blob/a529769efd989ac5e83e4ee09f1ac7b199e686d3/ship/SKILL.md |
| Reliability Engineer | https://github.com/garrytan/gstack/blob/a529769efd989ac5e83e4ee09f1ac7b199e686d3/canary/SKILL.md |
| Security Engineer | https://github.com/garrytan/gstack/blob/a529769efd989ac5e83e4ee09f1ac7b199e686d3/cso/SKILL.md |
| Incident Commander | https://github.com/cursor/plugins/blob/aaeb0ea3a0584995aa8f55ce44c6c5259414b896/pstack/skills/poteto-mode/playbooks/runtime-forensics.md |
| Research Analyst | https://github.com/cursor/plugins/blob/aaeb0ea3a0584995aa8f55ce44c6c5259414b896/pstack/skills/how/SKILL.md |
| Refactoring Engineer | https://github.com/mattpocock/skills/blob/abeeaf95660ba9e8b7c753eb38f441ca707a8823/skills/engineering/improve-codebase-architecture/SKILL.md |
| QA Engineer | https://github.com/cursor/plugins/blob/aaeb0ea3a0584995aa8f55ce44c6c5259414b896/pstack/skills/create-verification-skill/SKILL.md |
| Adversarial Reviewer | https://github.com/cursor/plugins/blob/aaeb0ea3a0584995aa8f55ce44c6c5259414b896/pstack/skills/interrogate/SKILL.md |
| Research Scientist | https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md |

## Comparison protocol
For each role, retain its pinned URL/revision, request the candidate immutable revision, and compare the actual file contents. Report added/removed instructions, permission changes, renamed commands and impact on role responsibilities. Keep the current revision unchanged until an authorized reviewer accepts the exact proposed diff. If the upstream reference cannot be read, record the specific URL, timestamp, sanitized error and account scope; do not substitute a mirror or infer the contents.

## Current result and missing evidence
The inventory is complete for the 15 local role profiles. No remote comparison was performed. There is no captured remote failure response in the supplied SMART history; therefore the historical statement about missing repository access cannot be independently confirmed. No changed revision, approved source update or verified drift result is recorded.

## Handoff
Reliability Engineer is the proposed inventory owner. Repository owner must supply an approved snapshot or read access through the designated credential channel if needed. The receiving reviewer must name the exact old/new versions and affected roles. No such acknowledgement is present.

## Access request contents
Specify the exact failing source from the inventory, required read scope and intended comparison. Do not ask for broad repository write access. An access request has not been sent by this audit.

