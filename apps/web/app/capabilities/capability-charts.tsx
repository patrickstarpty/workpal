import {catalog, stages} from './data';
import {Button} from '@workpal/ui/components/ui/button';
const actions = ['plan', 'design', 'build', 'test', 'deploy', 'improve'];

export function DeliveryChart({stage, onSelect, onStart}: {onStart: (stage: number) => void; stage: number; onSelect: (stage: number) => void}) {
  return <figure className="cap-chart" aria-labelledby="delivery-chart-title">
    <figcaption className="chart-heading"><div><p className="eyebrow">Overview · Delivery loop</p><h2 id="delivery-chart-title">One goal. A complete lifecycle.</h2></div><span className="chart-note">Select a stage</span></figcaption>
    <div className="delivery-loop">
      <span className="delivery-bridge delivery-bridge-start" aria-hidden="true"/>
      <span className="delivery-bridge delivery-bridge-end" aria-hidden="true"/>
      <div className="delivery-control">Human direction <span>Goals · judgment · decisions</span></div>
      {stages.map((item, index) => <div key={item.id} className="delivery-node" style={{gridArea: `phase${index}`}} data-chart-stage={index} data-selected={index === stage}><button type="button" className="delivery-select" aria-pressed={index === stage} aria-label={`${item.name}: ${item.chartVerb}; expected artifact ${item.chartArtifact}`} onClick={() => onSelect(index)}>
        <span className="delivery-step"><span className="delivery-index">{String(index + 1).padStart(2, '0')}</span><span>{item.name}</span></span><strong>{item.chartVerb}</strong><span className="delivery-artifact">{item.chartArtifact}</span>
      </button><div className="delivery-action">{index === stage && <Button size="sm" onClick={()=>onStart(index)}>Let’s {actions[index]}</Button>}</div></div>)}
    </div>
    <p className="chart-note chart-footnote">Feedback can return to any stage. People own the critical decisions.</p>
  </figure>;
}

const coverage = catalog.types.map(type => {
  const parts = catalog.sources.map(source => ({source, count: catalog.skills.filter(skill => skill.id.startsWith(`${source.id}:`) && skill.types.includes(type.id)).length}));
  return {...type, parts, total: parts.reduce((total, part) => total + part.count, 0)};
}).sort((a, b) => b.total - a.total || a.label.localeCompare(b.label));
const maximum = Math.ceil(Math.max(...coverage.map(row => row.total)) / 10) * 10;

export function SkillCoverageChart({typeId, onSelect}: {typeId: string; onSelect: (typeId: string) => void}) {
  return <figure className="cap-chart coverage-chart" aria-labelledby="coverage-chart-title">
    <figcaption className="coverage-heading"><div><p className="eyebrow">Skill Hub · Capability coverage</p><h2 id="coverage-chart-title"><strong>{catalog.skills.length}</strong><span>catalog entries</span></h2></div><p className="chart-note">{catalog.types.length} types<br/>{catalog.sources.length} sources</p></figcaption>
    <div className="coverage-legend">{catalog.sources.map((source, index) => <span key={source.id}><i className={`source-swatch source-${index}`} aria-hidden="true"/>{source.label}</span>)}</div>
    <div className="coverage-axis" aria-hidden="true"><span>Entries tagged per type</span><div><span>0</span><span>{maximum / 2}</span><span>{maximum}</span></div><span/></div>
    <div className="coverage-rows">{coverage.map(row => <button key={row.id} type="button" className="coverage-row" data-chart-type={row.id} aria-pressed={typeId === row.id} aria-label={`Browse ${row.label}, ${row.total} entries. ${row.parts.filter(part => part.count).map(part => `${part.source.label}: ${part.count}`).join('; ')}`} onClick={() => onSelect(row.id)}>
      <span className="coverage-label">{row.label}</span><span className="coverage-track" aria-hidden="true">{row.parts.map((part, index) => <span key={part.source.id} className={`coverage-segment source-${index}`} style={{width: `${part.count / maximum * 100}%`}}/>)}</span><strong className="coverage-total">{row.total}</strong>
    </button>)}</div>
    <p className="chart-note chart-footnote">Full catalog · Entries can have several types. Select a bar to browse that type.</p>
  </figure>;
}
