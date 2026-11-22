import {WorkflowTickets} from './workflow-tickets';
import {useState} from 'react';
import {Button} from '@workpal/ui/components/ui/button';
import {catalog, roles, stages} from './data';
import {DeliveryChart} from './capability-charts';

export function Overview({onOpenSkill, onStartStage}: {onStartStage: (stage: number) => void; onOpenSkill: (id: string) => void; onNavigate: (view: 'skills' | 'team') => void}) {
  const [stageIndex, setStageIndex] = useState(0);
  const stage = stages[stageIndex]!;
  const selectStage = (index: number) => setStageIndex(index);
  return <>
    <DeliveryChart stage={stageIndex} onSelect={selectStage} onStart={onStartStage}/>
    <div className="hero"><p className="eyebrow">AI-native software development</p><h1>From intent to working software.</h1><p className="subtitle">People set direction. Agents carry context through planning, implementation and verification. Skills make good methods reusable.</p></div>
    <div className="scenario"><h2>One request, across the lifecycle</h2><span className="tag">Recover an interrupted document upload</span></div>
    <div className="stages" aria-label="Delivery stages">{stages.map((item, index) => <button className="stage" type="button" key={item.id} aria-pressed={stageIndex === index} onClick={() => selectStage(index)}>{String(index + 1).padStart(2, '0')} {item.name}</button>)}</div>
    <p className="feedback">Start at any stage. Keep one ticket across delivery or split work when it needs its own outcome.</p>
    <WorkflowTickets stage={stage.id}/>
    <section className="panel stage-detail" aria-labelledby="stage-detail-title">
      <div><p className="eyebrow">{stage.name}</p><h2 id="stage-detail-title">{stage.focus}</h2><p className="section-description">{stage.summary}</p>
        <div className="facts"><div><span className="label">Input</span><p className="value">{stage.input}</p></div>
          <div><span className="label">Relevant skills</span><div className="chips">{stage.skills.map(id => <Button variant="secondary" size="sm" className="chip" key={id} onClick={() => onOpenSkill(id)}>{catalog.skills.find(skill => skill.id === id)!.name}</Button>)}</div></div>
          <div><span className="label">Agent roles</span><p className="value">{stage.agents.map(id => roles.find(role => role.id === id)!.name).join(' · ')}</p></div>
        </div>
      </div>
      <div className="paper"><span className="label">Expected deliverable</span><h3 className="filename">{stage.outputs.join(' · ')}</h3><div className="artifact-outline">{stage.outline.map(([name, description]) => <div key={name}><h3>{name}</h3><p>{description}</p></div>)}</div></div>
    </section>
    <div className="decision"><span className="label">Human decision</span><p className="value">{stage.human}</p></div>
    <details className="concepts"><summary>The ideas behind this workflow</summary><div className="definitions"><div><h3>Skills</h3><p>Reusable instructions and resources that guide how a task is done.</p></div><div><h3>Subagents</h3><p>Scoped helpers that investigate, simplify or verify with focused context.</p></div><div><h3>Parallel sessions</h3><p>Separate tasks can progress independently while people steer the work.</p></div><div><h3>Human decisions</h3><p>People own intent, tradeoffs and release authorization.</p></div></div><p className="source-line"><a href="https://claude.com/resources/articles/the-ai-native-sdlc-playbook" target="_blank" rel="noopener noreferrer">The AI-native SDLC playbook</a></p></details>
  </>;
}
