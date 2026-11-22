"use client";

import localeResources from "@workpal/views/locales/ru";
import type { LocaleBundleProps } from "../locale-bundle";

const resources = { "ru": localeResources };

export default function Bundle({ children }: LocaleBundleProps) {
  return <>{children(resources)}</>;
}
