import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    setupFiles: ["@workpal/vitest-setup/web-storage"],
    include: ["**/*.test.{ts,tsx}"],
    passWithNoTests: true,
  },
});
