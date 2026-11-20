import reactConfig from "@workpal/eslint-config/react";
import { NO_ROUND_CONTROLS } from "@workpal/eslint-config/control-shape";

export default [
  { ignores: ["storybook-static/**"] },
  ...reactConfig,
  {
    files: ["**/*.tsx"],
    rules: {
      "no-restricted-syntax": ["error", NO_ROUND_CONTROLS],
    },
  },
];
