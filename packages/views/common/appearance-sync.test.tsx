import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, waitFor } from "@testing-library/react";
import {
  APPEARANCE_STORAGE_KEY,
  DEFAULT_APPEARANCE,
  INSTALLED_THEMES_STORAGE_KEY,
  useAppearanceStore,
  useInstalledThemesStore,
  useThemeFolderStatus,
  useThemeSafeMode,
} from "@workpal/core/appearance";
import { AppearanceSync } from "./appearance-sync";

const html = () => document.documentElement;
const sheet = () => document.getElementById("workpal-appearance");
const themeCss = () => document.getElementById("workpal-theme-css");

const PAPER = {
  apiVersion: 1,
  id: "paper",
  name: "Paper",
  css: '.theme-light { --page-canvas: #f6efdf; }\n[data-mc="content"] p { hyphens: auto; }',
} as const;

describe("AppearanceSync", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    useAppearanceStore.setState(DEFAULT_APPEARANCE);
    useInstalledThemesStore.setState({ themes: [] });
    useThemeSafeMode.setState({ active: false });
  });
  afterEach(cleanup);

  it("applies FWD on the initial render", () => {
    render(<AppearanceSync />);
    expect(html().getAttribute("data-theme")).toBe("fwd");
    expect(themeCss()?.textContent).toContain("--button-primary:");
  });

  it("leaves <html> untouched for an explicit Default selection", () => {
    useAppearanceStore.getState().set({ theme: "default" });
    render(<AppearanceSync />);
    expect(html().hasAttribute("data-theme")).toBe(false);
    expect(html().getAttribute("style") ?? "").toBe("");
    expect(sheet()).toBeNull();
    expect(themeCss()).toBeNull();
  });

  it("marks the mode on <html> for theme CSS, following the dark class", async () => {
    const { unmount } = render(<AppearanceSync />);
    expect(html().classList.contains("theme-light")).toBe(true);
    html().classList.add("dark");
    await act(async () => {});
    expect(html().classList.contains("theme-dark")).toBe(true);
    expect(html().classList.contains("theme-light")).toBe(false);
    html().classList.remove("dark");
    await act(async () => {});
    expect(html().classList.contains("theme-light")).toBe(true);
    unmount();
    expect(html().classList.contains("theme-light")).toBe(false);
  });

  it("marks the platform and window focus on <html>", () => {
    const { unmount } = render(<AppearanceSync />);
    expect(html().classList.contains("is-web")).toBe(true);
    act(() => {
      vi.spyOn(document, "hasFocus").mockReturnValue(false);
      window.dispatchEvent(new Event("blur"));
    });
    expect(html().classList.contains("is-focused")).toBe(false);
    act(() => {
      vi.spyOn(document, "hasFocus").mockReturnValue(true);
      window.dispatchEvent(new Event("focus"));
    });
    expect(html().classList.contains("is-focused")).toBe(true);
    unmount();
    expect(html().classList.contains("is-web")).toBe(false);
    expect(html().classList.contains("is-focused")).toBe(false);
  });

  it("mirrors the selected theme, type and density without applying retired options", () => {
    render(<AppearanceSync />);
    act(() => {
      const { set, setThemeOption } = useAppearanceStore.getState();
      set({ theme: "fwd", highContrast: true, uiFont: "serif", fontSize: 15, contentCjkFont: "serif", density: "comfortable" });
      setThemeOption("pop", "status-blocks", false);
    });
    expect(html().getAttribute("data-theme")).toBe("fwd");
    expect(html().hasAttribute("data-theme-option-signal")).toBe(false);
    expect(html().hasAttribute("data-theme-option-status-blocks")).toBe(false);
    expect(html().hasAttribute("data-theme-option-outlined-chips")).toBe(false);
    expect(html().style.getPropertyValue("--font-ui")).toBe("var(--font-ui-serif)");
    expect(html().style.getPropertyValue("--font-content-cjk")).toBe("var(--font-cjk-serif)");
    expect(html().style.getPropertyValue("--font-scale")).toBe(String(15 / 14));
    expect(html().style.getPropertyValue("--issue-row-height")).toBe("42px");
    expect(html().style.getPropertyValue("--nav-item-height")).toBe("2.25rem");
    expect(themeCss()?.textContent).toContain("--button-primary:");
    expect(themeCss()?.textContent).toContain('[data-mc="page"]');
    expect(sheet()?.textContent).toContain("--muted-foreground: color-mix(");

    act(() => useAppearanceStore.getState().set({ theme: "default" }));
    expect(html().hasAttribute("data-theme")).toBe(false);
    expect(themeCss()).toBeNull();
    expect(sheet()).not.toBeNull();

    act(() => useAppearanceStore.getState().reset());
    expect(html().getAttribute("data-theme")).toBe("fwd");
    expect(html().style.getPropertyValue("--font-ui")).toBe("");
    expect(sheet()).toBeNull();
    expect(themeCss()).not.toBeNull();
  });

  it("keeps the adjustments after a theme stylesheet created later", () => {
    useAppearanceStore.setState({ theme: "default", highContrast: true });
    render(<AppearanceSync />);
    act(() => useAppearanceStore.getState().set({ theme: "fwd" }));
    expect(themeCss()!.compareDocumentPosition(sheet()!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("keeps custom CSS inactive and temporarily uses Default in safe mode", () => {
    useInstalledThemesStore.setState({ themes: [PAPER] });
    useAppearanceStore.setState({ theme: "paper" });
    render(<AppearanceSync />);
    expect(html().getAttribute("data-theme")).toBe("fwd");
    expect(themeCss()?.textContent).not.toContain("hyphens: auto");
    expect(useInstalledThemesStore.getState().themes).toEqual([PAPER]);

    act(() => useThemeSafeMode.getState().enter());
    expect(html().hasAttribute("data-theme")).toBe(false);
    expect(themeCss()).toBeNull();
    expect(useAppearanceStore.getState().theme).toBe("paper");

    act(() => useThemeSafeMode.getState().exit());
    expect(html().getAttribute("data-theme")).toBe("fwd");
  });

  it("clears everything when the product UI unmounts", () => {
    useAppearanceStore.setState({ theme: "fwd", highContrast: true, codeFont: "system" });
    const { unmount } = render(<AppearanceSync />);
    expect(html().getAttribute("data-theme")).toBe("fwd");
    expect(sheet()).not.toBeNull();
    unmount();
    expect(html().hasAttribute("data-theme")).toBe(false);
    expect(html().hasAttribute("data-theme-option-signal")).toBe(false);
    expect(html().style.getPropertyValue("--font-mono")).toBe("");
    expect(sheet()).toBeNull();
    expect(themeCss()).toBeNull();
  });

  it("migrates retired selections saved by another window and retains the package", async () => {
    render(<AppearanceSync />);
    localStorage.setItem(
      INSTALLED_THEMES_STORAGE_KEY,
      JSON.stringify({ state: { themes: [PAPER] }, version: 0 }),
    );
    localStorage.setItem(
      APPEARANCE_STORAGE_KEY,
      JSON.stringify({ state: { theme: "paper" }, version: 0 }),
    );
    await act(async () => {
      window.dispatchEvent(new StorageEvent("storage", { key: INSTALLED_THEMES_STORAGE_KEY }));
      window.dispatchEvent(new StorageEvent("storage", { key: APPEARANCE_STORAGE_KEY }));
    });
    expect(html().getAttribute("data-theme")).toBe("fwd");
    expect(useAppearanceStore.getState().theme).toBe("fwd");
    expect(useInstalledThemesStore.getState().themes).toEqual([PAPER]);
  });

  describe("on Desktop", () => {
    const encode = (text: string) => new TextEncoder().encode(text);
    const folder = (css: string, id = "paper") => [
      { path: "manifest.json", data: encode(JSON.stringify({ apiVersion: 1, id, name: id })) },
      { path: "theme.css", data: encode(css) },
    ];
    let onChange: () => void = () => {};
    const desktop = {
      readThemeFolder: vi.fn(),
      onThemeFolderChange: vi.fn((callback: () => void) => {
        onChange = callback;
        return () => {};
      }),
      openThemeFolder: vi.fn(),
      writeThemeFolder: vi.fn(),
    };
    beforeEach(() => {
      useInstalledThemesStore.setState({ folders: {} });
      useThemeFolderStatus.setState({ path: null, problems: [] });
      (window as unknown as { desktopAPI: unknown }).desktopAPI = desktop;
    });
    afterEach(() => {
      delete (window as unknown as { desktopAPI?: unknown }).desktopAPI;
    });

    it("retains folder themes and re-reads them without activating custom CSS", async () => {
      desktop.readThemeFolder.mockResolvedValue({
        path: "/data/themes",
        entries: [
          { folder: "paper", files: folder(".theme-light { --page-canvas: #fffdf8; }") },
          { folder: "huge", error: "A theme can be at most 1024 KB and 64 files" },
        ],
      });
      useAppearanceStore.setState({ theme: "paper" });
      render(<AppearanceSync />);
      await waitFor(() => expect(useInstalledThemesStore.getState().folders).toEqual({ paper: "paper" }));
      expect(html().getAttribute("data-theme")).toBe("fwd");
      expect(themeCss()?.textContent).not.toContain("#fffdf8");
      expect(useInstalledThemesStore.getState().folders).toEqual({ paper: "paper" });
      expect(useThemeFolderStatus.getState()).toEqual({
        path: "/data/themes",
        problems: [{ folder: "huge", errors: ["A theme can be at most 1024 KB and 64 files"] }],
      });

      desktop.readThemeFolder.mockResolvedValue({
        path: "/data/themes",
        entries: [{ folder: "paper", files: folder(".theme-light { --page-canvas: #f0f0ff; }") }],
      });
      await act(async () => onChange());
      await waitFor(() => expect(useInstalledThemesStore.getState().themes.find((theme) => theme.id === "paper")?.css).toContain("#f0f0ff"));
      expect(themeCss()?.textContent).not.toContain("#f0f0ff");
      expect(useThemeFolderStatus.getState().problems).toEqual([]);

      desktop.readThemeFolder.mockResolvedValue({ path: "/data/themes", entries: [] });
      await act(async () => onChange());
      await waitFor(() => expect(useInstalledThemesStore.getState().themes).toEqual([]));
      expect(html().getAttribute("data-theme")).toBe("fwd");
    });

    it("refreshes saved folder themes without switching away from the selected theme", async () => {
      const paper = (canvas: string) => ({ folder: "paper", files: folder(`.theme-light { --page-canvas: ${canvas}; }`) });
      const dusk = { folder: "dusk", files: folder(".theme-light { --page-canvas: #2a2438; }", "dusk") };
      desktop.readThemeFolder.mockResolvedValue({ path: "/data/themes", entries: [paper("#fffdf8")] });
      useAppearanceStore.getState().set({ theme: "fwd" });
      render(<AppearanceSync />);
      await waitFor(() => expect(useInstalledThemesStore.getState().themes[0]?.css).toContain("#fffdf8"));

      desktop.readThemeFolder.mockResolvedValue({ path: "/data/themes", entries: [paper("#fffdf8"), dusk] });
      await act(async () => onChange());
      await waitFor(() => expect(useInstalledThemesStore.getState().folders).toHaveProperty("dusk"));
      expect(useAppearanceStore.getState().theme).toBe("fwd");
      expect(html().getAttribute("data-theme")).toBe("fwd");

      desktop.readThemeFolder.mockResolvedValue({ path: "/data/themes", entries: [paper("#f0f0ff"), dusk] });
      await act(async () => onChange());
      await waitFor(() => expect(useInstalledThemesStore.getState().themes.find((theme) => theme.id === "paper")?.css).toContain("#f0f0ff"));
      expect(themeCss()?.textContent).not.toContain("#f0f0ff");
      expect(html().getAttribute("data-theme")).toBe("fwd");
    });
  });
});
