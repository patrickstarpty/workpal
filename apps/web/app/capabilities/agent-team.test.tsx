import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AgentTeam } from "./agent-team";

afterEach(cleanup);

describe("Agent Team navigation", () => {
  it("returns from related role profiles to the role and chart that opened them", async () => {
    const user = userEvent.setup();
    render(<AgentTeam onOpenSkill={() => {}} />);

    await user.click(screen.getByRole("button", { name: "Explore Discovery & design squad" }));
    expect(screen.getByRole("heading", { level: 1, name: "Discovery & design" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: /Product Strategist Turn a business request/ }));
    expect(screen.getByRole("heading", { level: 1, name: "Product Strategist" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Software Architect" }));
    expect(screen.getByRole("heading", { level: 1, name: "Software Architect" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Back to Agent Team" }));
    expect(screen.getByRole("button", { name: "Explore Discovery & design squad" })).toHaveFocus();
  });

  it("returns to the originating squad card after a handoff", async () => {
    const user = userEvent.setup();
    render(<AgentTeam onOpenSkill={() => {}} />);

    const card = screen.getByRole("heading", { level: 2, name: "Engineering delivery" }).closest("article");
    expect(card).not.toBeNull();
    await user.click(within(card!).getByRole("button", { name: "Explore squad" }));
    await user.click(screen.getByRole("button", { name: /Verification & review Change, intended behavior/ }));
    expect(screen.getByRole("heading", { level: 1, name: "Verification & review" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Back to Agent Team" }));
    const restoredCard = screen.getByRole("heading", { level: 2, name: "Engineering delivery" }).closest("article");
    expect(within(restoredCard!).getByRole("button", { name: "Explore squad" })).toHaveFocus();
  });

  it("opens a shared role from its connection matrix and hands off the real mapped skill", async () => {
    const user = userEvent.setup();
    const onOpenSkill = vi.fn();
    render(<AgentTeam onOpenSkill={onOpenSkill} />);

    const matrix = screen.getByRole("table", { name: "Shared specialist connections to squads" });
    expect(within(matrix).getByRole("cell", { name: "Engineering delivery: calls on QA Engineer" })).toBeInTheDocument();
    expect(within(matrix).getByRole("cell", { name: "Discovery & design: no proposed connection to QA Engineer" })).toBeInTheDocument();
    await user.click(within(matrix).getByRole("button", { name: "QA Engineer" }));
    expect(screen.getByRole("heading", { level: 1, name: "QA Engineer" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "qa-only" }));
    expect(onOpenSkill).toHaveBeenCalledExactlyOnceWith("gstack:qa-only/SKILL.md");

    await user.click(screen.getByRole("button", { name: "Back to Agent Team" }));
    expect(within(screen.getByRole("table", { name: "Shared specialist connections to squads" })).getByRole("button", { name: "QA Engineer" })).toHaveFocus();
  });

  it("keeps a shared-pool role as the return target after collaborator navigation", async () => {
    const user = userEvent.setup();
    render(<AgentTeam onOpenSkill={() => {}} />);

    await user.click(screen.getByRole("button", { name: /Refactoring Engineer Reduce unnecessary complexity/ }));
    await user.click(screen.getByRole("button", { name: "Implementation Engineer" }));
    expect(screen.getByRole("heading", { level: 1, name: "Implementation Engineer" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Back to Agent Team" }));
    expect(screen.getByRole("button", { name: /Refactoring Engineer Reduce unnecessary complexity/ })).toHaveFocus();
  });
});
