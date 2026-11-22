import { i18n } from "./i18n";

export function switchLocalePath(pathname: string, target: string): string {
  // Next strips basePath before the router, so `pathname` starts at `/`
  // or `/<locale>/...`. Default-locale URLs are prefix-less.
  const segments = pathname.split("/").filter(Boolean);
  const first = segments[0];
  const hasLocalePrefix =
    first && i18n.languages.some((l) => l === first);

  const rest = hasLocalePrefix ? segments.slice(1) : segments;
  const prefixed =
    target === i18n.defaultLanguage ? rest : [target, ...rest];

  return "/" + prefixed.join("/");
}
