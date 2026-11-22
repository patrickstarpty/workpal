import { describe, expect, it } from "vitest";
import {
  catalog,
  filterSkills,
  overviewSkills,
  roles,
  sharedSpecialists,
  skillHighlights,
  sourceOf,
  squads,
  stages,
} from "./data";

describe("capability catalog", () => {
  it("resolves every skill to its source, types and pinned upstream record", () => {
    const sourceIds = new Set(catalog.sources.map((source) => source.id));
    const typeIds = new Set(catalog.types.map((type) => type.id));

    expect(new Set(catalog.skills.map((skill) => skill.id)).size).toBe(
      catalog.skills.length,
    );
    for (const skill of catalog.skills) {
      const source = sourceOf(skill);
      expect(source, skill.id).toBeDefined();
      expect(skill.id).toBe(`${source?.id}:${skill.path}`);
      expect(skill.url).toContain(`/blob/${source?.commitSha}/${skill.path}`);
      expect(skill.blobSha).toMatch(/^[a-f0-9]{40}$/);
      expect(skill.types.length).toBeGreaterThan(0);
      expect(new Set(skill.types).size).toBe(skill.types.length);
      for (const id of skill.types) expect(typeIds.has(id), id).toBe(true);
    }
    for (const excluded of catalog.excluded) {
      expect(sourceIds.has(excluded.sourceId), excluded.path).toBe(true);
      expect(excluded.reason).not.toBe("");
    }
    for (const source of catalog.sources) {
      expect(source.commitSha).toMatch(/^[a-f0-9]{40}$/);
      expect(source.repositoryUrl).toMatch(/^https:\/\//);
      expect(source.licenseUrl).toMatch(/^https:\/\//);
      expect(source.licenseSummary).not.toBe("");
    }
  });

  it("resolves role, squad and stage relationships by stable IDs", () => {
    const skillIds = new Set(catalog.skills.map((skill) => skill.id));
    const roleIds = new Set(roles.map((role) => role.id));
    const squadIds = new Set(squads.map((squad) => squad.id));
    const assignedRoles = [...sharedSpecialists, ...squads.flatMap((squad) => squad.core)];

    expect(roleIds.size).toBe(roles.length);
    expect(squadIds.size).toBe(squads.length);
    expect(new Set(assignedRoles).size).toBe(assignedRoles.length);
    expect(new Set(assignedRoles)).toEqual(roleIds);
    for (const role of roles) {
      for (const id of role.skills) expect(skillIds.has(id), id).toBe(true);
      for (const id of role.collaborators) expect(roleIds.has(id), id).toBe(true);
    }
    for (const squad of squads) {
      for (const id of [...squad.core, ...squad.specialists]) {
        expect(roleIds.has(id), id).toBe(true);
      }
      for (const id of squad.specialists) expect(sharedSpecialists).toContain(id);
      for (const handoff of squad.handoffs) {
        expect(squadIds.has(handoff.squadId), handoff.squadId).toBe(true);
      }
    }
    expect(new Set(stages.map((stage) => stage.id)).size).toBe(stages.length);
    expect(new Set(stages.map((stage) => stage.name))).toEqual(new Set(Object.keys(overviewSkills)));
    for (const stage of stages) {
      expect(stage.skills.length, stage.name).toBeGreaterThan(0);
      expect(stage.agents.length, stage.name).toBeGreaterThan(0);
      for (const id of stage.skills) expect(skillIds.has(id), id).toBe(true);
      for (const id of stage.agents) expect(roleIds.has(id), id).toBe(true);
    }
    for (const id of Object.keys(skillHighlights)) expect(skillIds.has(id), id).toBe(true);
  });
});

describe("filterSkills", () => {
  it("includes a skill under every assigned type while intersecting its source", () => {
    const id = "superpowers:skills/test-driven-development/SKILL.md";

    for (const typeId of ["engineering", "quality"]) {
      expect(
        filterSkills({ sourceId: "superpowers", typeId, query: "test-driven-development" })
          .map((skill) => skill.id),
      ).toContain(id);
    }
    expect(filterSkills({ sourceId: "anthropic", query: "test-driven-development" })
      .map((skill) => skill.id)).not.toContain(id);
    expect(filterSkills({ sourceId: "superpowers", typeId: "documents" })).toEqual([]);
  });

  it("uses IDs for source and type filters, leaving labels available to text search", () => {
    expect(filterSkills({ sourceId: "Anthropic Skills" })).toEqual([]);
    expect(filterSkills({ typeId: "Testing & review" })).toEqual([]);
    expect(filterSkills({ sourceId: "superpowers", query: "  JESSE VINCENT  " }))
      .toHaveLength(15);
    expect(filterSkills({ sourceId: "anthropic", typeId: "quality", query: "webapp-testing" })
      .map((skill) => skill.id)).toEqual(["anthropic:skills/webapp-testing/SKILL.md"]);
  });

  it("returns the full catalog for empty filters and an empty result for unknown filters", () => {
    expect(filterSkills()).toHaveLength(203);
    expect(filterSkills({ query: "   " })).toHaveLength(203);
    expect(filterSkills({ sourceId: "missing-source" })).toEqual([]);
    expect(filterSkills({ typeId: "missing-type" })).toEqual([]);
    expect(filterSkills({ query: "no-such-capability-a596d0" })).toEqual([]);
  });

  it("searches the approved use descriptions and puts highlighted entries first", () => {
    expect(filterSkills({ query: "shape an idea" }).map((skill) => skill.id))
      .toEqual(["superpowers:skills/brainstorming/SKILL.md"]);
    expect(filterSkills().slice(0, 3).map((skill) => skill.id)).toEqual([
      "anthropic:skills/frontend-design/SKILL.md",
      "superpowers:skills/brainstorming/SKILL.md",
      "pstack:pstack/skills/poteto-mode/SKILL.md",
    ]);
  });
});
