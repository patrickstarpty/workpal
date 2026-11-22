 function roleProfile(selected){
 const skillLinks=selected.skills.map(id=>catalog.skills.find(s=>s.id===id)).filter(Boolean);
 return  '<section class="panel agent-profile" aria-live="polite"><div><p class="eyebrow">Role profile · '+esc(selected.mode)+'</p><h1 id="agent-title" tabindex="-1">'+esc(selected.name)+'</h1><p class="section-description">'+esc(selected.mission)+'</p></div>'+
 '<div class="profile-pair"><div><span class="label">Engage when</span><p class="value">'+esc(selected.trigger)+'</p></div><div><span class="label">Expected output</span><p class="value">'+esc(selected.output)+'</p></div></div>'+
 '<div><span class="label">Required context</span><p class="value">'+esc(selected.input)+'</p></div>'+
 '<div><span class="label">Proposed scope</span><p class="value">'+esc(selected.scope)+'</p></div>'+
 '<div><span class="label">Human decision / handoff</span><p class="value">'+esc(selected.approval)+'</p></div>'+
 '<div><span class="label">Suggested skills</span><div class="chips">'+(skillLinks.length?skillLinks.map(s=>'<button type="button" class="chip skill-route" data-open-skill="'+esc(s.id)+'">'+esc(s.name)+' ↗</button>').join(''):'<span class="small">No dedicated skill mapped yet.</span>')+'</div></div>'+
 '<div><span class="label">Works with</span><div class="chips">'+selected.collaborators.map(id=>roleProfiles.find(r=>r.id===id)).filter(Boolean).map(r=>'<button type="button" class="chip" data-related-agent="'+r.id+'">'+esc(r.name)+' →</button>').join('')+'</div></div>'+
 '<details class="profile-basis"><summary>Role definition</summary><p class="small">'+esc(selected.basis)+'</p></details></section>';
 }

 function roleButtons(ids){return ids.map(id=>{
 const r=roleProfiles.find(r=>r.id===id);
 return '<button type="button" class="role-item" data-agent="'+r.id+'"><strong>'+esc(r.name)+'</strong><span>'+esc(r.mission)+'</span></button>';
 }).join('');}
 function roleNames(ids){return ids.map(id=>esc(roleProfiles.find(r=>r.id===id).name)).join(' · ');}
 function squadPage(selected){
 return '<section class="squad-detail"><button type="button" class="link team-back" data-squad-back="true">← All squads</button>'+
 '<div class="hero"><p class="eyebrow">Squad composition</p><h1 id="squad-title" tabindex="-1">'+esc(selected.name)+'</h1><p class="subtitle">'+esc(selected.mission)+'</p></div>'+
 '<div class="panel squad-summary"><div><span class="label">Capabilities</span><ul class="squad-capabilities">'+selected.capabilities.map(c=>'<li>'+esc(c)+'</li>').join('')+'</ul></div><div><span class="label">Expected deliverables</span><p class="value">'+esc(selected.output)+'</p></div><div><span class="label">Engage when</span><p class="value">'+esc(selected.trigger)+'</p></div><div><span class="label">Human decision</span><p class="value">'+esc(selected.humanDecision)+'</p></div></div>'+
 '<section class="squad-section"><h2>Core lineup</h2><p class="small">Suggested composition · 1 lead + '+selected.core.length+' core '+(selected.core.length===1?'role':'roles')+'</p><div class="squad-members"><div class="squad-lead"><span class="label">Squad lead</span><strong>'+esc(selected.lead)+'</strong><p>Carries the task context, coordinates roles and brings decisions back to a person.</p></div>'+roleButtons(selected.core)+'</div></section>'+
 '<section class="squad-section"><h2>On-demand specialists</h2><p class="small">Drawn from the shared pool for a scoped task, with independent context where needed.</p><div class="squad-members">'+roleButtons(selected.specialists)+'</div></section>'+
 '<section class="squad-section"><h2>Works with other squads</h2><p class="small">Exchange reviewable artifacts as the work needs them.</p><div class="squad-handoffs">'+selected.handoffs.map(h=>{const target=squadCatalog.squads.find(s=>s.id===h.squadId);return '<button type="button" class="role-item" data-squad="'+target.id+'"><strong>'+esc(target.name)+' →</strong><span>'+esc(h.artifact)+'</span></button>';}).join('')+'</div></section></section>';
 }
 function teamPage(){
 const selectedSquad=squadCatalog.squads.find(s=>s.id===squad);
 const selectedRole=roleProfiles.find(r=>r.id===agent);
 if(selectedRole)return '<section class="role-page"><button type="button" class="link team-back" data-role-back="true">← '+(selectedSquad?'Back to '+esc(selectedSquad.name):'All squads')+'</button>'+roleProfile(selectedRole)+'</section>';
 if(selectedSquad)return squadPage(selectedSquad);
 return hero('Agent Team','Specialized squads. Shared expertise.','Explore how agent teams combine their capabilities to design, deliver, verify and operate software.')+
 '<div class="human"><strong>Global squads</strong><span>Suggested lineups · Human-led decisions</span></div>'+
 '<div class="squad-grid">'+squadCatalog.squads.map(s=>'<article class="squad-card"><div><p class="eyebrow">1 lead · '+s.core.length+' core '+(s.core.length===1?'role':'roles')+'</p><h2>'+esc(s.name)+'</h2><p class="mission">'+esc(s.mission)+'</p></div><div><span class="label">Core lineup</span><div class="lineup"><strong>'+esc(s.lead)+' · Lead</strong>'+s.core.map(id=>'<span>'+esc(roleProfiles.find(r=>r.id===id).name)+'</span>').join('')+'</div></div><div><span class="label">Shared support</span><p class="value">'+roleNames(s.specialists)+'</p></div><div class="squad-output"><span class="label">Delivers</span><p class="value">'+esc(s.output)+'</p></div><button type="button" class="plain" data-squad="'+s.id+'">Explore squad →</button></article>').join('')+'</div>'+
 '<section class="shared-pool"><h2>Shared specialists</h2><p class="section-description">One shared pool, called on demand. Specialists contribute to multiple squads without becoming permanent members of each.</p><div class="shared-grid">'+roleButtons(squadCatalog.sharedSpecialists)+'</div></section>'+
 '<details class="team-definition"><summary>How these squads are defined</summary><p class="section-description">'+esc(squadCatalog.definition)+'</p></details>';
 }
