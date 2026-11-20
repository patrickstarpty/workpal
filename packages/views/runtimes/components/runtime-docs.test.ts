// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  customRuntimeDocsHref,
  daemonRuntimesDocsHref,
} from "./runtime-docs";

describe("runtime docs links", () => {
  it.each([
    ["en", "https://workpal.invalid/docs/daemon-runtimes"],
    ["zh-Hans", "https://workpal.invalid/docs/zh/daemon-runtimes"],
    ["zh-Hant", "https://workpal.invalid/docs/zh-Hant/daemon-runtimes"],
    ["ja", "https://workpal.invalid/docs/ja/daemon-runtimes"],
    ["ko", "https://workpal.invalid/docs/ko/daemon-runtimes"],
    ["fr", "https://workpal.invalid/docs/fr/daemon-runtimes"],
  ])("localizes the daemon guide for %s", (language, expected) => {
    expect(daemonRuntimesDocsHref(language)).toBe(expected);
  });

  it("adds the localized custom runtime section", () => {
    expect(customRuntimeDocsHref("zh-Hans")).toBe(
      `https://workpal.invalid/docs/zh/daemon-runtimes#${encodeURIComponent("自定义运行时配置")}`,
    );
    expect(customRuntimeDocsHref("zh-Hant")).toBe(
      `https://workpal.invalid/docs/zh-Hant/daemon-runtimes#${encodeURIComponent("自定義執行時配置")}`,
    );
    expect(customRuntimeDocsHref("fr")).toBe(
      `https://workpal.invalid/docs/fr/daemon-runtimes#${encodeURIComponent("profils-de-runtime-personnalisés")}`,
    );
  });
});
