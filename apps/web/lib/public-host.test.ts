// @vitest-environment node
import { describe, expect, it } from "vitest";

import { isOfficialMarketingHost } from "./public-host";

describe("isOfficialMarketingHost", () => {
  it.each(["workpal.invalid", "workpal.invalid", "workpal.invalid", "workpal.invalid."])(
    "recognizes %s as an official marketing host",
    (host) => {
      expect(isOfficialMarketingHost(host)).toBe(true);
    },
  );

  it.each(["workpal.invalid", "workpal.invalid", "localhost", "workpal.test"])(
    "does not treat %s as the public marketing host",
    (host) => {
      expect(isOfficialMarketingHost(host)).toBe(false);
    },
  );
});
