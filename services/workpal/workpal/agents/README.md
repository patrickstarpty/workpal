# Agent configuration

Interface: `service.create(actor,name,provider_key='copilot_cli',model='')`,
`read(actor,agent_id)`, `update(actor,agent_id,revision,**changes)` return JSON AgentView.
Owner/admin manage; active workspace members read subject to current provenance.
Updates use positive revision CAS. Model is an explicit saved string; empty means no
model override, never an invented model choice. Configuration is not an installation,
authentication or runtime probe. Four extension providers are not_implemented.

Registry actions: agent.create/read/update, closed forms and output schema, existing
Registry idempotency/audit/current result authorization. Register AgentsConfig only
after integration approval; apply its generated migration. No network or CLI calls.
