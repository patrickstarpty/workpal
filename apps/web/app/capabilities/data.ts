import catalogData from "./data/catalog.json";
import roleData from "./data/role-profiles.json";
import overviewSkillsData from "./data/overview-skills.json";
import squadData from "./data/squads.json";
import stageData from "./data/stages.json";

export interface SkillType {
  id: string;
  label: string;
}

export interface SkillSource {
  id: string;
  label: string;
  author: string;
  repo: string;
  commitSha: string;
  repositoryUrl: string;
  retrievedAt: string;
  licenseUrl: string;
  licenseSummary: string;
}

export interface Skill {
  id: string;
  name: string;
  description: string;
  path: string;
  url: string;
  blobSha: string;
  scope: string;
  categoryHint?: string;
  types: string[];
}

export interface SkillCatalog {
  retrievedAt: string;
  classificationOrigin: string;
  types: SkillType[];
  sources: SkillSource[];
  skills: Skill[];
  excluded: { path: string; reason: string; sourceId: string }[];
}

export interface AgentRole {
  id: string;
  name: string;
  mode: string;
  mission: string;
  trigger: string;
  input: string;
  output: string;
  scope: string;
  approval: string;
  collaborators: string[];
  skills: string[];
  basis: string;
}

export interface Squad {
  id: string;
  name: string;
  mission: string;
  lead: string;
  capabilities: string[];
  core: string[];
  specialists: string[];
  output: string;
  trigger: string;
  humanDecision: string;
  handoffs: { squadId: string; artifact: string }[];
}

export interface Stage {
  id: string;
  name: string;
  focus: string;
  summary: string;
  input: string;
  outputs: string[];
  outline: string[][];
  human: string;
  skills: string[];
  agents: string[];
  chartVerb: string;
  chartArtifact: string;
}

// These checked-in snapshots retain upstream identities, pinned revisions and
// provenance. They describe available methods and roles, not executing agents.
export const catalog: SkillCatalog = catalogData;
export const skills = catalog.skills;
export const roles: AgentRole[] = roleData;
export const squads: Squad[] = squadData.squads;
export const sharedSpecialists: string[] = squadData.sharedSpecialists;
export const squadDefinition = squadData.definition;
export const overviewSkills: Record<string, string[]> = overviewSkillsData;
export const stages: Stage[] = stageData.map((stage) => ({
  ...stage,
  skills: overviewSkills[stage.name] ?? [],
}));

export const skillHighlights: Record<string, [string, string]> = {
  "anthropic:skills/frontend-design/SKILL.md": ["Design a frontend", "Create interfaces from design goals."],
  "superpowers:skills/brainstorming/SKILL.md": ["Shape an idea", "Clarify intent, requirements and design."],
  "pstack:pstack/skills/poteto-mode/SKILL.md": ["Coordinate engineering work", "Choose a playbook for the task."],
  "matt-pocock:skills/productivity/grill-me/SKILL.md": ["Pressure-test a plan", "Work through decisions and open questions."],
  "gstack:plan-ceo-review/SKILL.md": ["Review product direction", "Examine scope and the product approach."],
  "anthropic:skills/pptx/SKILL.md": ["Create a presentation", "Read, edit and create slide decks."],
  "superpowers:skills/test-driven-development/SKILL.md": ["Build with regression coverage", "Develop changes through tests."],
  "pstack:pstack/skills/architect/SKILL.md": ["Examine the architecture", "Work through engineering design choices."],
  "matt-pocock:skills/engineering/code-review/SKILL.md": ["Review a code change", "Assess the change against standards and intent."],
  "gstack:ship/SKILL.md": ["Prepare work for shipping", "Follow the repository shipping workflow."],
  "anthropic:skills/docx/SKILL.md": ["Work with Word documents", "Create, read and edit documents."],
  "anthropic:skills/xlsx/SKILL.md": ["Work with spreadsheets", "Create and edit spreadsheet files."],
};

export function sourceOf(skill: Pick<Skill, "id">): SkillSource | undefined {
  const sourceId = skill.id.split(":", 1)[0];
  return catalog.sources.find((source) => source.id === sourceId);
}

export function typeLabel(id: string): string {
  return catalog.types.find((type) => type.id === id)?.label ?? id;
}

export interface SkillFilters {
  query?: string;
  sourceId?: string;
  typeId?: string;
}

const highlightOrder = new Map(
  Object.keys(skillHighlights).map((id, index) => [id, index]),
);

export function filterSkills({ query = "", sourceId, typeId }: SkillFilters = {}): Skill[] {
  const search = query.trim().toLowerCase();

  return catalog.skills.filter((skill) => {
    const source = sourceOf(skill);
    if (sourceId && source?.id !== sourceId) return false;
    if (typeId && !skill.types.includes(typeId)) return false;
    if (!search) return true;

    return [
      skill.name,
      skill.description,
      ...(skillHighlights[skill.id] ?? []),
      ...skill.types.map(typeLabel),
      source?.label,
      source?.author,
    ].join(" ").toLowerCase().includes(search);
  }).sort((left, right) =>
    (highlightOrder.get(left.id) ?? Infinity) - (highlightOrder.get(right.id) ?? Infinity)
    || left.name.localeCompare(right.name)
    || left.id.localeCompare(right.id),
  );
}
