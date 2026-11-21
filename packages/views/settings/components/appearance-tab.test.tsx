import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider } from "@workpal/core/i18n/react";
import { configStore } from "@workpal/core/config";
import {
  DEFAULT_APPEARANCE,
  useAppearanceStore,
  useInstalledThemesStore,
  useThemeFolderStatus,
} from "@workpal/core/appearance";
import enCommon from "../../locales/en/common.json";
import enSettings from "../../locales/en/settings.json";

const themeState = vi.hoisted(() => ({
  theme: "light",
  resolvedTheme: "light",
  setTheme: vi.fn(),
}));
vi.mock("@workpal/ui/components/common/theme-provider", () => ({
  useTheme: () => themeState,
}));
const api = vi.hoisted(() => ({
  listStoreThemes: vi.fn(),
  getStoreThemePackage: vi.fn(),
  getStoreThemeScreenshot: vi.fn(),
}));
vi.mock("@workpal/core/api", () => ({ api }));

import { AppearanceTab } from "./appearance-tab";

const TEST_RESOURCES = { en: { common: enCommon, settings: enSettings } };

let queryClient: QueryClient;

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider locale="en" resources={TEST_RESOURCES}>
        {children}
      </I18nProvider>
    </QueryClientProvider>
  );
}

const group = (name: string) => screen.getByRole("group", { name });
const state = () => useAppearanceStore.getState();
const themeSelect = () => screen.getByRole("combobox", { name: "Theme" });

const PAPER = {
  apiVersion: 1 as const,
  id: "paper",
  name: "Paper",
  author: "Someone",
  version: "1.0.0",
};
const PAPER_CSS = '.theme-light { --page-canvas: #f6efdf; }\n[data-mc="content"] p { hyphens: auto; }';

describe("AppearanceTab", () => {
  beforeEach(() => {
    themeState.theme = "light";
    themeState.resolvedTheme = "light";
    themeState.setTheme.mockClear();
    localStorage.clear();
    useAppearanceStore.setState(DEFAULT_APPEARANCE);
    useInstalledThemesStore.setState({ themes: [], folders: {}, fromStore: {} });
    useThemeFolderStatus.setState({ path: null, problems: [] });
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    configStore.getState().setThemeStoreEnabled(false);
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
  });

  it("switches the mode on this device", async () => {
    const user = userEvent.setup();
    render(<AppearanceTab />, { wrapper: Wrapper });

    expect(screen.getByText("This device only")).toBeInTheDocument();
    expect(within(group("Mode")).getByRole("button", { name: "Light" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.click(within(group("Mode")).getByRole("button", { name: "Dark" }));

    expect(themeState.setTheme).toHaveBeenCalledWith("dark");
  });

  it("offers only FWD and Default even with saved custom themes and the store enabled", async () => {
    useInstalledThemesStore.setState({
      themes: [{ ...PAPER, css: PAPER_CSS }],
      folders: { paper: "paper" },
      fromStore: { paper: "1.0.0" },
    });
    configStore.getState().setThemeStoreEnabled(true);
    const user = userEvent.setup();
    render(<AppearanceTab />, { wrapper: Wrapper });

    expect(themeSelect()).toHaveTextContent("FWD");
    expect(screen.queryByRole("button", { name: "Import theme" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Manage" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Check for updates" })).not.toBeInTheDocument();
    await user.click(themeSelect());
    expect((await screen.findAllByRole("option")).map((option) => option.textContent)).toEqual(["FWD", "Default"]);
    await user.click(screen.getByRole("option", { name: "Default" }));
    expect(state().theme).toBe("default");
    expect(useInstalledThemesStore.getState().themes).toHaveLength(1);
    await act(async () => useAppearanceStore.persist.rehydrate());
    expect(themeSelect()).toHaveTextContent("Default");
  });

  it("draws both themes in the applied mode and saves the pick", async () => {
    themeState.theme = "system";
    themeState.resolvedTheme = "dark";
    const user = userEvent.setup();
    render(<AppearanceTab />, { wrapper: Wrapper });

    await user.click(themeSelect());
    const options = await screen.findAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual(["FWD", "Default"]);
    expect(options[1]!.querySelector("[data-theme-swatch]")).toHaveAttribute("data-swatch-mode", "dark");
    await user.click(options[1]!);

    expect(state().theme).toBe("default");
    expect(themeSelect()).toHaveTextContent("Default");
  });

  it("sets interface and content type separately", async () => {
    const user = userEvent.setup();
    render(<AppearanceTab />, { wrapper: Wrapper });

    const [uiLatin, contentLatin] = screen.getAllByRole("combobox", { name: "Latin font" });
    const [, contentCjk] = screen.getAllByRole("combobox", { name: "CJK font" });
    await user.click(uiLatin!);
    await user.click(await screen.findByRole("option", { name: /^Source Serif 4/ }));
    await user.click(contentLatin!);
    await user.click(await screen.findByRole("option", { name: /^Geist Mono/ }));
    await user.click(contentCjk!);
    await user.click(await screen.findByRole("option", { name: /^Kai/ }));
    await user.click(within(group("Line height")).getByRole("button", { name: "Relaxed" }));

    expect(state()).toMatchObject({
      uiFont: "serif",
      uiCjkFont: "sans",
      contentFont: "mono",
      contentCjkFont: "kai",
      contentLeading: "relaxed",
    });
    expect(contentLatin).toHaveTextContent("Geist Mono");
  });

  describe("content font size", () => {
    const sizeSliders = () => screen.getAllByRole("slider", { name: "Font size" });
    const follow = () => screen.getByRole("switch", { name: "Match interface size" });
    const press = async (slider: HTMLElement, key: string) => {
      act(() => slider.focus());
      await userEvent.setup().keyboard(key);
    };
    // Base UI keeps edge-aligned thumbs visibility: hidden until a microtask has measured them.
    const renderTab = async () => {
      render(<AppearanceTab />, { wrapper: Wrapper });
      await screen.findAllByRole("slider", { name: "Font size" });
    };

    it("follows the interface by default, with the same slider", async () => {
      useAppearanceStore.setState({ fontSize: 15 });
      await renderTab();

      const [, content] = sizeSliders();
      expect(content).toHaveValue("15");
      expect(follow()).toBeChecked();
      expect(screen.getByText("15 px · Default")).toBeInTheDocument();
    });

    it("keeps a size equal to the interface independent of later interface changes", async () => {
      useAppearanceStore.setState({ fontSize: 14, contentSize: 15 });
      await renderTab();
      expect(follow()).not.toBeChecked();

      await press(sizeSliders()[1]!, "{ArrowLeft}");
      expect(state().contentSize).toBe(14);
      expect(follow()).not.toBeChecked();

      await press(sizeSliders()[0]!, "{ArrowRight}");
      expect(state()).toMatchObject({ fontSize: 15, contentSize: 14 });
      expect(sizeSliders()[1]).toHaveValue("14");
    });

    it("pins the current size when following is turned off, and follows again only when turned on", async () => {
      const user = userEvent.setup();
      useAppearanceStore.setState({ fontSize: 13 });
      await renderTab();

      await user.click(follow());
      expect(state().contentSize).toBe(13);

      await user.click(follow());
      expect(state().contentSize).toBe("ui");
      await press(sizeSliders()[0]!, "{ArrowRight}");
      expect(sizeSliders()[1]).toHaveValue("14");

      await press(sizeSliders()[1]!, "{ArrowRight}");
      expect(state().contentSize).toBe(15);
      expect(follow()).not.toBeChecked();
    });
  });

  it.each(["fwd", "default"])("keeps Inter and the existing code font in %s", async (theme) => {
    useAppearanceStore.getState().set({ theme });
    render(<AppearanceTab />, { wrapper: Wrapper });
    await screen.findAllByRole("slider", { name: "Font size" });
    expect(screen.getAllByRole("combobox", { name: "Latin font" })[0]).toHaveTextContent("Inter");
    expect(screen.getByRole("combobox", { name: "Code font" })).toHaveTextContent("Geist Mono");
  });

  it("picks the density and contrast, and has no accent colour of its own", async () => {
    const user = userEvent.setup();
    render(<AppearanceTab />, { wrapper: Wrapper });
    expect(screen.queryByRole("radiogroup", { name: "Accent color" })).not.toBeInTheDocument();

    await user.click(within(group("Density")).getByRole("button", { name: "Compact" }));
    await user.click(screen.getByRole("switch", { name: "Increase contrast" }));

    expect(state()).toMatchObject({ density: "compact", highContrast: true });
  });

  it("resets to the defaults, and only once something changed", async () => {
    const user = userEvent.setup();
    render(<AppearanceTab />, { wrapper: Wrapper });
    const reset = screen.getByRole("button", { name: "Reset to defaults" });
    expect(reset).toBeDisabled();

    await user.click(within(group("Density")).getByRole("button", { name: "Comfortable" }));
    expect(reset).toBeEnabled();
    await user.click(reset);

    expect(state().density).toBe("default");
    expect(reset).toBeDisabled();
  });
});
