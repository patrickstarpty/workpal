import {useLayoutEffect, useMemo, useRef, useState} from 'react';
import {Button} from '@workpal/ui/components/ui/button';
import {Input} from '@workpal/ui/components/ui/input';
import {catalog, filterSkills, skillHighlights, sourceOf, typeLabel, type Skill} from './data';
import {SkillCoverageChart} from './capability-charts';
import {reveal} from './focus';
import {ArrowLeft} from '@workpal/ui/icons';

function TypeTags({skill}: {skill: Skill}) {
  return <div className="type-tags">{skill.types.map(id => <span className="type-tag" key={id}>{typeLabel(id)}</span>)}</div>;
}

export function SkillHub({initialSkillId}: {initialSkillId?: string | null}) {
  const [query, setQuery] = useState('');
  const [committedQuery, setCommittedQuery] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [typeId, setTypeId] = useState('');
  const [limit, setLimit] = useState(12);
  const [selectedId, setSelectedId] = useState(initialSkillId ?? null);
  const composing = useRef(false);
  const pendingReturn = useRef<string | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const typeSelect = useRef<HTMLSelectElement>(null);
  const cards = useRef(new Map<string, HTMLButtonElement>());
  const matches = useMemo(() => filterSkills({query: committedQuery, sourceId, typeId}), [committedQuery, sourceId, typeId]);
  const selected = catalog.skills.find(skill => skill.id === selectedId);
  const source = selected ? sourceOf(selected) : undefined;

  useLayoutEffect(() => {
    if (selectedId) reveal(heading.current);
    else if (pendingReturn.current) {
      reveal(cards.current.get(pendingReturn.current));
      pendingReturn.current = null;
    }
  }, [selectedId]);

  const reset = () => {setQuery(''); setCommittedQuery(''); setSourceId(''); setTypeId(''); setLimit(12);};
  const close = () => {
    const index = matches.findIndex(skill => skill.id === selectedId);
    if (index < 0) {reset(); setLimit(Math.max(12, filterSkills().findIndex(skill => skill.id === selectedId) + 1));}
    else setLimit(Math.max(limit, index + 1));
    pendingReturn.current = selectedId;
    setSelectedId(null);
  };
  if (selected && source) return (
    <section className="panel selection" aria-label="Skill details">
      <Button variant="ghost" size="sm" onClick={close}><ArrowLeft aria-hidden="true"/>Back to Skill Hub</Button>
      <h1 ref={heading} tabIndex={-1}>{selected.name}</h1>
      <div className="source-line"><span>{source.label} · {source.author}</span><span>{selected.scope}</span><span>{source.commitSha.slice(0, 7)}</span></div>
      <TypeTags skill={selected}/><p className="full-description">{selected.description}</p>
      <div className="source-line"><a href={selected.url} target="_blank" rel="noopener noreferrer">Read SKILL.md</a><a href={source.licenseUrl || source.repositoryUrl} target="_blank" rel="noopener noreferrer">Source & license</a></div>
    </section>
  );
  return <>
    <SkillCoverageChart typeId={typeId} onSelect={id => {reset(); setTypeId(id); reveal(typeSelect.current);}}/>
    <div className="hero"><p className="eyebrow">Skill Hub</p><h1>Reusable expertise. Ready to explore.</h1><p className="subtitle">Discover what AI can help with, then inspect the skills behind each capability.</p></div>
    <div className="filters" aria-label="Skill sources"><Button variant="outline" size="sm" aria-pressed={!sourceId} onClick={() => {setSourceId(''); setLimit(12);}}>All sources</Button>{catalog.sources.map(source => <Button key={source.id} variant="outline" size="sm" aria-pressed={sourceId === source.id} onClick={() => {setSourceId(source.id); setLimit(12);}}>{source.label}</Button>)}</div>
    <div className="catalog-controls">
      <label htmlFor="skill-type">Skill type<select id="skill-type" ref={typeSelect} value={typeId} onChange={event => {setTypeId(event.target.value); setLimit(12);}}><option value="">All types</option>{catalog.types.map(type => <option key={type.id} value={type.id}>{type.label}</option>)}</select></label>
      <label htmlFor="skill-search">Search skills<Input id="skill-search" type="search" placeholder="Search capabilities, names or descriptions" value={query}
        onCompositionStart={() => {composing.current = true;}}
        onCompositionEnd={event => {composing.current = false; setCommittedQuery(event.currentTarget.value); setQuery(event.currentTarget.value); setLimit(12);}}
        onChange={event => {setQuery(event.target.value); if (!composing.current) {setCommittedQuery(event.target.value); setLimit(12);}}}/></label>
    </div>
    <div className="catalog-status"><span role="status" aria-live="polite" className="catalog-count">{matches.length} of {catalog.skills.length} entries</span>{(query || sourceId || typeId) && <Button variant="ghost" size="sm" onClick={reset}>Clear filters</Button>}</div>
    <div className="skill-grid">{matches.slice(0, limit).map(skill => <button type="button" className="skill-card" key={skill.id} data-skill={skill.id} aria-label={`View skill: ${skill.name}`} aria-pressed={selectedId === skill.id} ref={node => {if (node) cards.current.set(skill.id, node); else cards.current.delete(skill.id);}} onClick={() => {if (selectedId === skill.id) reveal(heading.current); else setSelectedId(skill.id);}}>
      <span className="skill-name">{sourceOf(skill)?.label} · {skill.scope}</span><h3>{skillHighlights[skill.id]?.[0] || skill.name}</h3><p className="excerpt">{skillHighlights[skill.id]?.[1] || skill.description}</p><TypeTags skill={skill}/><span className="link">{skill.name}</span>
    </button>)}</div>
    {!matches.length && <p className="small">No skills match this search.</p>}
    <div className="catalog-footer"><span className="small">Source-linked catalog · Entries retain their original identity</span>{matches.length > limit && <Button variant="outline" size="sm" onClick={() => setLimit(limit + 12)}>Show more</Button>}</div>
    <details className="concepts"><summary>About this catalog</summary><p className="section-description">Types describe each skill’s purpose independently of its source. Entries link to their original definitions and licenses; browsing does not install or run a skill.</p></details>
  </>;
}
