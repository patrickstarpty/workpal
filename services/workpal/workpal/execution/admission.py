"""Current configuration facts only; callers must reauthorize future execution.

Use within the transaction saving the initial fact. No permission is cached and
no Runtime installation or authentication is asserted by this Interface.
"""
from copy import deepcopy
from dataclasses import dataclass, field

from workpal.contracts import Actor, DomainError, ObjectRef
from workpal.identity.service import require_member
from workpal.access.service import authorize, derive_scope
from workpal.agents import service as agents
from workpal.work.issues import integer, validate_text


@dataclass(frozen=True)
class AgentInitializationAdmission:
    agent: dict
    source_refs: tuple[ObjectRef, ...]
    purpose: str = field(default='initialized', init=False)
    execution_authorized: bool = field(default=False, init=False)


def admit_initialization(actor: Actor, agent_id: int) -> AgentInitializationAdmission:
    integer(agent_id)
    require_member(actor, actor.workspace_id)
    agent = agents.read(actor, agent_id)
    refs = (agents.ref(agent_id),)
    scope = derive_scope(refs)
    authorize(actor, 'read', refs)
    validate_text(agent.get('name'), 200, True)
    validate_text(agent.get('model'), 200)
    provider = agent.get('provider_key')
    if type(provider) is not str or provider not in agents.PROVIDERS:
        raise DomainError('invalid_input', 'Unknown provider.')
    if provider != 'copilot_cli':
        raise DomainError('capability_unavailable', 'Provider initialization unavailable.', status=409)
    return AgentInitializationAdmission(
        deepcopy(agent), tuple(sorted(scope.source_refs, key=lambda ref: (ref.kind, ref.id))))
