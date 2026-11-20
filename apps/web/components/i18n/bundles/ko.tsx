"use client";

import localeResources from "@workpal/views/locales/ko";
import type { LocaleBundleProps } from "../locale-bundle";

const resources = { "ko": localeResources };

export default function Bundle({ children }: LocaleBundleProps) {
  return <>{children(resources)}</>;
}
