"use client";

import localeResources from "@workpal/views/locales/fr";
import type { LocaleBundleProps } from "../locale-bundle";

const resources = { "fr": localeResources };

export default function Bundle({ children }: LocaleBundleProps) {
  return <>{children(resources)}</>;
}
