// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  customRuntimeDocsHref,
  daemonRuntimesDocsHref,
} from "./runtime-docs";

describe("runtime docs links", () => {
  it.each([
    ["en", "http://127.0.0.1:4000/docs/daemon-runtimes"],
    ["zh-Hans", "http://127.0.0.1:4000/docs/zh/daemon-runtimes"],
    ["zh-Hant", "http://127.0.0.1:4000/docs/zh-Hant/daemon-runtimes"],
    ["ja", "http://127.0.0.1:4000/docs/ja/daemon-runtimes"],
    ["ko", "http://127.0.0.1:4000/docs/ko/daemon-runtimes"],
    ["fr", "http://127.0.0.1:4000/docs/fr/daemon-runtimes"],
  ])("localizes the daemon guide for %s", (language, expected) => {
    expect(daemonRuntimesDocsHref(language)).toBe(expected);
  });

  it("adds the localized custom runtime section", () => {
    expect(customRuntimeDocsHref("zh-Hans")).toBe(
      `http://127.0.0.1:4000/docs/zh/daemon-runtimes#${encodeURIComponent("自定义运行时配置")}`,
    );
    expect(customRuntimeDocsHref("zh-Hant")).toBe(
      `http://127.0.0.1:4000/docs/zh-Hant/daemon-runtimes#${encodeURIComponent("自定義執行時配置")}`,
    );
    expect(customRuntimeDocsHref("fr")).toBe(
      `http://127.0.0.1:4000/docs/fr/daemon-runtimes#${encodeURIComponent("profils-de-runtime-personnalisés")}`,
    );
  });
});
