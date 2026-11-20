import { describe, expect, it } from "vitest";
import { workspaceUrlHost } from "./workspace-url";

describe("workspaceUrlHost", () => {
  it("returns the host of a full app URL", () => {
    expect(workspaceUrlHost("https://workpal.example.com")).toBe(
      "workpal.example.com",
    );
  });

  it("ignores scheme, path, and trailing slash", () => {
    expect(workspaceUrlHost("https://workpal.example.com/")).toBe(
      "workpal.example.com",
    );
    expect(workspaceUrlHost("http://workpal.example.com/app/onboarding")).toBe(
      "workpal.example.com",
    );
  });

  it("preserves a non-default port", () => {
    expect(workspaceUrlHost("https://my.host:3000")).toBe("my.host:3000");
  });

  it("accepts a bare host without a scheme", () => {
    expect(workspaceUrlHost("workpal.example.com")).toBe("workpal.example.com");
    expect(workspaceUrlHost("workpal.example.com/path")).toBe(
      "workpal.example.com",
    );
  });

  it("falls back to the brand host when no app URL is configured", () => {
    expect(workspaceUrlHost("")).toBe("workpal.invalid");
    expect(workspaceUrlHost("   ")).toBe("workpal.invalid");
    expect(workspaceUrlHost(null)).toBe("workpal.invalid");
    expect(workspaceUrlHost(undefined)).toBe("workpal.invalid");
  });
});
