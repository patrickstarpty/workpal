"use client";

import localeResources from "@workpal/views/locales/zh-Hant";
import type { LocaleBundleProps } from "../locale-bundle";

const resources = { "zh-Hant": localeResources };

export default function Bundle({ children }: LocaleBundleProps) {
  return <>{children(resources)}</>;
}
