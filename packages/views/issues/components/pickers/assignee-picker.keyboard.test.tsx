// Keyboard behaviour of the assignee picker's search box. Uses the REAL
// PropertyPicker / Base UI Popover — the regression under test lives in
// PropertyPicker's highlight bookkeeping, so mocking it would test nothing.
//
// Regression: the "Unassigned" row is pinned as the picker's first row, which
// also makes it the first `data-picker-item`. PropertyPicker used to reset the
// highlight to index 0 on every keystroke, so typing a name and pressing Enter
// unassigned the issue instead of assigning it to the person being searched
// for. The empty row is now excluded from the search-result Enter default while
// staying reachable by arrow key.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nProvider } from "@workpal/core/i18n/react";
import enIssues from "../../../locales/en/issues.json";
import { AssigneePicker } from "./assignee-picker";

import {configStore} from "@workpal/core/config";
const choices = vi.hoisted(() => ({agents: [] as any[], squads: [] as any[], bound: true, allowed: true}));
beforeEach(() => {choices.agents=[];choices.squads=[];choices.bound=true;choices.allowed=true;configStore.getState().setFeatureFlags({});});

const MEMBERS = [
  { user_id: "user-1", name: "Ada Lovelace", role: "member" },
  { user_id: "user-2", name: "Grace Hopper", role: "member" },
];

vi.mock("@tanstack/react-query", () => ({
  useQuery: ({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "members") return { data: MEMBERS };
    if (queryKey[0] === "agents") return {data: choices.agents};
    if (queryKey[0] === "squads") return {data: choices.squads};
    return { data: [] };
  },
}));

vi.mock("@workpal/core/hooks", () => ({ useWorkspaceId: () => "workspace-1" }));
vi.mock("@workpal/core/auth", () => ({ useAuthStore: () => ({ id: "user-1" }) }));
vi.mock("@workpal/core/agents", () => ({ isAgentRuntimeBound: () => choices.bound }));
vi.mock("@workpal/core/permissions", () => ({
  canAssignAgentToIssue: () => ({ allowed: choices.allowed, message: "Not allowed" }),
}));
vi.mock("@workpal/core/workspace/hooks", () => ({
  useActorName: () => ({ getActorName: () => "Ada Lovelace" }),
}));
vi.mock("@workpal/core/workspace/queries", () => ({
  memberListOptions: () => ({ queryKey: ["members"] }),
  agentListOptions: () => ({ queryKey: ["agents"] }),
  squadListOptions: () => ({ queryKey: ["squads"] }),
  assigneeFrequencyOptions: () => ({ queryKey: ["frequency"] }),
}));
vi.mock("../../../common/actor-avatar", () => ({
  ActorAvatar: () => <span data-testid="actor-avatar" />,
}));

const SEARCH_PLACEHOLDER = "Assign to...";

function renderPicker(onUpdate: () => void) {
  return render(
    <I18nProvider locale="en" resources={{ en: { issues: enIssues } }}>
      {/* Controlled open: the picker is the subject, its trigger is not. */}
      <AssigneePicker
        assigneeType={null}
        assigneeId={null}
        onUpdate={onUpdate}
        open
        onOpenChange={() => {}}
      />
    </I18nProvider>,
  );
}

describe("AssigneePicker search keyboard defaults", () => {
  it("assigns the first match on Enter instead of unassigning", async () => {
    const user = userEvent.setup();
    const onUpdate = vi.fn();

    renderPicker(onUpdate);

    await user.type(await screen.findByPlaceholderText(SEARCH_PLACEHOLDER), "grace");
    await user.keyboard("{Enter}");

    expect(onUpdate).toHaveBeenCalledWith({
      assignee_type: "member",
      assignee_id: "user-2",
    });
  });

  it("leaves Enter inert when the query matches nobody", async () => {
    const user = userEvent.setup();
    const onUpdate = vi.fn();

    renderPicker(onUpdate);

    await user.type(await screen.findByPlaceholderText(SEARCH_PLACEHOLDER), "zzzznomatch");
    await user.keyboard("{Enter}");

    expect(onUpdate).not.toHaveBeenCalled();
  });
});

describe("assignment without execution", () => {
  beforeEach(() => {choices.bound=false;choices.agents=[{id:"engineer",name:"Engineer"}];choices.squads=[{id:"team",name:"Delivery squad",leader_id:"engineer"}];});
  it("allows a squad or agent when the backend supports assignment without a runtime", async () => {
    configStore.getState().setFeatureFlags({issue_assignment_without_runtime:true});
    const update=vi.fn();renderPicker(update);
    await userEvent.click(await screen.findByRole("button",{name:"Engineer"}));
    expect(update).toHaveBeenCalledWith({assignee_type:"agent",assignee_id:"engineer"});
    await userEvent.click(screen.getByRole("button",{name:"Delivery squad"}));
    expect(update).toHaveBeenCalledWith({assignee_type:"squad",assignee_id:"team"});
  });
  it("retains the runtime requirement when the capability is absent", async () => {
    renderPicker(vi.fn());
    expect(await screen.findByRole("button",{name:"Engineer"})).toBeDisabled();
    expect(screen.getByRole("button",{name:"Delivery squad"})).toBeDisabled();
  });
  it("still enforces agent permissions", async () => {
    choices.allowed=false;configStore.getState().setFeatureFlags({issue_assignment_without_runtime:true});renderPicker(vi.fn());
    expect(await screen.findByRole("button",{name:"Engineer"})).toBeDisabled();
  });
});
