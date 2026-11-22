import {ArrowLeft} from '@workpal/ui/icons';
import { useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { Button } from "@workpal/ui/components/ui/button";
import { catalog, roles, sharedSpecialists, squadDefinition, squads, type AgentRole } from "./data";

type OpenProfile = (id: string, origin?: string) => void;
type RegisterTrigger = (id: string) => (element: HTMLButtonElement | null) => void;
type Selection = { squadId: string | null; roleId: string | null };

function rolesFor(ids: string[]) {
  return ids.map((id) => roles.find((role) => role.id === id)).filter((role): role is AgentRole => Boolean(role));
}

function initials(name: string) {
  return name.split(/[\s&-]+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

function TeamChart({ openSquad, openRole, registerTrigger }: {
  openSquad: OpenProfile;
  openRole: OpenProfile;
  registerTrigger: RegisterTrigger;
}) {
  const shared = rolesFor(sharedSpecialists);
  const coreCount = new Set(squads.flatMap((squad) => squad.core)).size;

  return (
    <figure className="cap-chart wp-team-chart" aria-labelledby="wp-team-chart-title" style={{ "--wp-team-chart-squad-count": squads.length } as CSSProperties}>
      <figcaption className="wp-team-chart-caption">
        <div><p className="wp-team-chart-eyebrow">Proposed lineup</p><h2 id="wp-team-chart-title">Your team, at a glance</h2></div>
        <p className="wp-team-chart-totals">
          <span><strong>{squads.length}</strong> squads</span>
          <span><strong>{coreCount}</strong> core roles</span>
          <span><strong>{shared.length}</strong> shared specialists</span>
        </p>
      </figcaption>
      <div className="wp-team-chart-direction">
        <div className="wp-team-chart-side-label">Direction</div>
        <div className="wp-team-chart-human"><strong>Human direction</strong><span>Goals, decisions &amp; approvals</span></div>
      </div>
      <div className="wp-team-chart-branches" aria-hidden="true"><span /></div>
      <div className="wp-team-chart-squad-row">
        <div className="wp-team-chart-side-label">Squad lineups<span>One lead per squad</span></div>
        <div className="wp-team-chart-lineups">
          {squads.map((squad, index) => (
            <article className="wp-team-chart-squad" key={squad.id}>
              <button type="button" className="wp-team-chart-squad-button" data-chart-squad={squad.id}
                aria-label={`Explore ${squad.name} squad`} ref={registerTrigger(`chart-squad-${squad.id}`)}
                onClick={() => openSquad(squad.id, `chart-squad-${squad.id}`)}>
                <span className="wp-team-chart-squad-number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span><strong>{squad.name}</strong>
              </button>
              <div className="wp-team-chart-lead"><span className="wp-team-chart-lead-dot" aria-hidden="true" /><span>{squad.lead}<small>Squad lead</small></span></div>
              <div className="wp-team-chart-core">
                <span>{squad.core.length} core {squad.core.length === 1 ? "role" : "roles"}</span>
                <div className="wp-team-chart-role-marks">
                  {rolesFor(squad.core).map((role) => (
                    <button type="button" className="wp-team-chart-role" key={role.id} data-chart-agent={role.id}
                      aria-label={`View ${role.name} role profile`} ref={registerTrigger(`chart-role-${squad.id}-${role.id}`)}
                      onClick={() => openRole(role.id, `chart-role-${squad.id}-${role.id}`)}>
                      <span className="wp-team-chart-mark" aria-hidden="true">{initials(role.name)}</span><span className="wp-team-chart-role-name">{role.name}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="wp-team-chart-mobile-support">
                <span>Shared support</span>
                <div>{rolesFor(squad.specialists).map((role) => (
                  <button type="button" key={role.id} data-chart-agent={role.id} aria-label={`View ${role.name} role profile`}
                    ref={registerTrigger(`chart-support-${squad.id}-${role.id}`)} onClick={() => openRole(role.id, `chart-support-${squad.id}-${role.id}`)}>
                    <span className="wp-team-chart-mark" aria-hidden="true">{initials(role.name)}</span>
                  </button>
                ))}</div>
              </div>
            </article>
          ))}
        </div>
      </div>
      <div className="wp-team-chart-pool-heading"><strong>Shared specialists</strong><span><span>On demand</span><span className="wp-team-chart-desktop-legend"> · <span className="wp-team-chart-legend-dot" aria-hidden="true" /> connected to squad</span></span></div>
      <div className="wp-team-chart-connections" role="table" aria-label="Shared specialist connections to squads">
        <div className="wp-team-chart-a11y" role="row"><span role="columnheader">Specialist</span>{squads.map((squad) => <span role="columnheader" key={squad.id}>{squad.name}</span>)}</div>
        {shared.map((role) => (
          <div className="wp-team-chart-connection-row" role="row" key={role.id}>
            <div className="wp-team-chart-specialist-cell" role="rowheader">
              <button type="button" className="wp-team-chart-specialist" data-chart-agent={role.id}
                ref={registerTrigger(`chart-specialist-${role.id}`)} onClick={() => openRole(role.id, `chart-specialist-${role.id}`)}>{role.name}</button>
            </div>
            {squads.map((squad) => {
              const connected = squad.specialists.includes(role.id);
              return <div className={`wp-team-chart-connection-cell${connected ? " is-connected" : ""}`} role="cell" key={squad.id}>
                <span className="wp-team-chart-connection-mark" aria-hidden="true" />
                <span className="wp-team-chart-a11y">{squad.name}: {connected ? "calls on " : "no proposed connection to "}{role.name}</span>
              </div>;
            })}
          </div>
        ))}
      </div>
      <div className="wp-team-chart-mobile-pool">
        {shared.map((role) => (
          <button type="button" key={role.id} data-chart-agent={role.id} ref={registerTrigger(`chart-pool-${role.id}`)}
            onClick={() => openRole(role.id, `chart-pool-${role.id}`)}>
            <span className="wp-team-chart-mark" aria-hidden="true">{initials(role.name)}</span><span>{role.name}</span>
          </button>
        ))}
      </div>
      <p className="wp-team-chart-note">Proposed roles, not headcount. Specialists are shared across squads.</p>
    </figure>
  );
}

function RoleButtons({ ids, origin, openRole, registerTrigger }: {
  ids: string[];
  origin: string;
  openRole: OpenProfile;
  registerTrigger: RegisterTrigger;
}) {
  return rolesFor(ids).map((role) => (
    <button type="button" className="role-item" key={role.id} data-agent={role.id}
      ref={registerTrigger(`${origin}-${role.id}`)} onClick={() => openRole(role.id, `${origin}-${role.id}`)}>
      <strong>{role.name}</strong>{" "}<span>{role.mission}</span>
    </button>
  ));
}

export function AgentTeam({ onOpenSkill }: { onOpenSkill: (id: string) => void }) {
  const [selection, setSelection] = useState<Selection>({ squadId: null, roleId: null });
  const titleRef = useRef<HTMLHeadingElement>(null);
  const triggers = useRef(new Map<string, HTMLButtonElement>());
  const squadOrigin = useRef<string | null>(null);
  const roleOrigin = useRef<string | null>(null);
  const pendingFocus = useRef<{ kind: "heading" } | { kind: "trigger"; id: string } | null>(null);
  const selectedSquad = squads.find((squad) => squad.id === selection.squadId);
  const selectedRole = roles.find((role) => role.id === selection.roleId);

  useLayoutEffect(() => {
    const pending = pendingFocus.current;
    if (!pending) return;
    const target = pending.kind === "heading" ? titleRef.current : triggers.current.get(pending.id);
    target?.focus({ preventScroll: true });
    target?.scrollIntoView?.({ block: pending.kind === "heading" ? "start" : "nearest" });
    pendingFocus.current = null;
  }, [selection]);

  const registerTrigger: RegisterTrigger = (id) => (element) => {
    if (element) triggers.current.set(id, element);
    else triggers.current.delete(id);
  };

  const openSquad: OpenProfile = (id, origin) => {
    if (origin) squadOrigin.current = origin;
    roleOrigin.current = null;
    pendingFocus.current = { kind: "heading" };
    setSelection({ squadId: id, roleId: null });
  };

  const openRole: OpenProfile = (id, origin) => {
    if (origin) roleOrigin.current = origin;
    pendingFocus.current = { kind: "heading" };
    setSelection((current) => ({ ...current, roleId: id }));
  };

  function backToSquads() {
    if (squadOrigin.current) pendingFocus.current = { kind: "trigger", id: squadOrigin.current };
    setSelection({ squadId: null, roleId: null });
  }

  function backFromRole() {
    const origin = selectedSquad ? squadOrigin.current : roleOrigin.current;
    if (origin) pendingFocus.current = { kind: "trigger", id: origin };
    setSelection({ squadId: null, roleId: null });
  }

  if (selectedRole) {
    const skillLinks = catalog.skills.filter((skill) => selectedRole.skills.includes(skill.id));
    return <section className="role-page">
      <Button type="button" variant="ghost" size="sm" className="link team-back" data-role-back="true" onClick={backFromRole}>
        <ArrowLeft aria-hidden="true"/>Back to Agent Team
      </Button>
      <section className="panel agent-profile" aria-labelledby="agent-title">
        <div><p className="eyebrow">Role profile · {selectedRole.mode}</p><h1 id="agent-title" tabIndex={-1} ref={titleRef}>{selectedRole.name}</h1><p className="section-description">{selectedRole.mission}</p></div>
        <div className="profile-pair"><div><span className="label">Engage when</span><p className="value">{selectedRole.trigger}</p></div><div><span className="label">Expected output</span><p className="value">{selectedRole.output}</p></div></div>
        <div><span className="label">Required context</span><p className="value">{selectedRole.input}</p></div>
        <div><span className="label">Proposed scope</span><p className="value">{selectedRole.scope}</p></div>
        <div><span className="label">Human decision / handoff</span><p className="value">{selectedRole.approval}</p></div>
        <div><span className="label">Suggested skills</span><div className="chips">
          {skillLinks.length ? skillLinks.map((skill) => <Button type="button" variant="outline" size="sm" className="chip skill-route" key={skill.id}
            data-open-skill={skill.id} onClick={() => onOpenSkill(skill.id)}>{skill.name}</Button>) : <span className="small">No dedicated skill mapped yet.</span>}
        </div></div>
        <div><span className="label">Works with</span><div className="chips">
          {rolesFor(selectedRole.collaborators).map((role) => <Button type="button" variant="outline" size="sm" className="chip" key={role.id}
            data-related-agent={role.id} onClick={() => openRole(role.id)}>{role.name}</Button>)}
        </div></div>
        <details className="profile-basis"><summary>Role definition</summary><p className="small">{selectedRole.basis}</p></details>
      </section>
    </section>;
  }

  if (selectedSquad) {
    return <section className="squad-detail">
      <Button type="button" variant="ghost" size="sm" className="link team-back" data-squad-back="true" onClick={backToSquads}><ArrowLeft aria-hidden="true"/>Back to Agent Team</Button>
      <div className="hero"><p className="eyebrow">Squad composition</p><h1 id="squad-title" tabIndex={-1} ref={titleRef}>{selectedSquad.name}</h1><p className="subtitle">{selectedSquad.mission}</p></div>
      <div className="panel squad-summary">
        <div><span className="label">Capabilities</span><ul className="squad-capabilities">{selectedSquad.capabilities.map((capability) => <li key={capability}>{capability}</li>)}</ul></div>
        <div><span className="label">Expected deliverables</span><p className="value">{selectedSquad.output}</p></div>
        <div><span className="label">Engage when</span><p className="value">{selectedSquad.trigger}</p></div>
        <div><span className="label">Human decision</span><p className="value">{selectedSquad.humanDecision}</p></div>
      </div>
      <section className="squad-section"><h2>Core lineup</h2><p className="small">Suggested composition · 1 lead + {selectedSquad.core.length} core {selectedSquad.core.length === 1 ? "role" : "roles"}</p>
        <div className="squad-members"><div className="squad-lead"><span className="label">Squad lead</span><strong>{selectedSquad.lead}</strong><p>Carries the task context, coordinates roles and brings decisions back to a person.</p></div>
          <RoleButtons ids={selectedSquad.core} origin={`squad-core-${selectedSquad.id}`} openRole={openRole} registerTrigger={registerTrigger} />
        </div>
      </section>
      <section className="squad-section"><h2>On-demand specialists</h2><p className="small">Drawn from the shared pool for a scoped task, with independent context where needed.</p>
        <div className="squad-members"><RoleButtons ids={selectedSquad.specialists} origin={`squad-specialist-${selectedSquad.id}`} openRole={openRole} registerTrigger={registerTrigger} /></div>
      </section>
      <section className="squad-section"><h2>Works with other squads</h2><p className="small">Exchange reviewable artifacts as the work needs them.</p>
        <div className="squad-handoffs">{selectedSquad.handoffs.map((handoff) => {
          const target = squads.find((squad) => squad.id === handoff.squadId);
          return target ? <button type="button" className="role-item" key={target.id} data-squad={target.id} onClick={() => openSquad(target.id)}><strong>{target.name}</strong>{" "}<span>{handoff.artifact}</span></button> : null;
        })}</div>
      </section>
    </section>;
  }

  return <>
    <TeamChart openSquad={openSquad} openRole={openRole} registerTrigger={registerTrigger} />
    <div className="hero"><p className="eyebrow">Agent Team</p><h1>Specialized squads. Shared expertise.</h1><p className="subtitle">Explore how agent teams combine their capabilities to design, deliver, verify and operate software.</p></div>
    <div className="human"><strong>Global squads</strong><span>Suggested lineups · Human-led decisions</span></div>
    <div className="squad-grid">{squads.map((squad) => <article className="squad-card" key={squad.id}>
      <div><p className="eyebrow">1 lead · {squad.core.length} core {squad.core.length === 1 ? "role" : "roles"}</p><h2>{squad.name}</h2><p className="mission">{squad.mission}</p></div>
      <div><span className="label">Core lineup</span><div className="lineup"><strong>{squad.lead} · Lead</strong>{rolesFor(squad.core).map((role) => <span key={role.id}>{role.name}</span>)}</div></div>
      <div><span className="label">Shared support</span><p className="value">{rolesFor(squad.specialists).map((role) => role.name).join(" · ")}</p></div>
      <div className="squad-output"><span className="label">Delivers</span><p className="value">{squad.output}</p></div>
      <Button type="button" variant="outline" size="sm" className="plain" data-squad={squad.id}
        ref={registerTrigger(`squad-card-${squad.id}`)} onClick={() => openSquad(squad.id, `squad-card-${squad.id}`)}>Explore squad</Button>
    </article>)}</div>
    <section className="shared-pool"><h2>Shared specialists</h2><p className="section-description">One shared pool, called on demand. Specialists contribute to multiple squads without becoming permanent members of each.</p>
      <div className="shared-grid"><RoleButtons ids={sharedSpecialists} origin="shared-pool" openRole={openRole} registerTrigger={registerTrigger} /></div>
    </section>
    <details className="team-definition"><summary>How these squads are defined</summary><p className="section-description">{squadDefinition}</p></details>
  </>;
}
