"use client";

import localeResources from "@workpal/views/locales/es";
import type { LocaleBundleProps } from "../locale-bundle";

const resources = { "es": localeResources };

export default function Bundle({ children }: LocaleBundleProps) {
  return <>{children(resources)}</>;
}
