"use client";

import { Monitor, Moon, Sun } from "@workpal/ui/icons";
import { useTheme } from "next-themes";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@workpal/ui/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@workpal/ui/components/ui/dropdown-menu";
import { cn } from "@workpal/ui/lib/utils";
import { i18n } from "@/lib/i18n";
import { switchLocalePath } from "@/lib/switch-locale";
import { localeLabels } from "@/lib/translations";

// Sidebar-footer chrome: a language switch on the left and a theme switch
// on the right. Replaces Fumadocs's default icon-only row, which buried
// the language option behind a tiny globe. Each control shows the current
// value as a label so the affordance is obvious at a glance.

const BASE_PATH = "/docs";


const THEME_OPTIONS: { value: string; label: string; icon: ReactNode }[] = [
  { value: "light", label: "Light", icon: <Sun className="size-4" /> },
  { value: "dark", label: "Dark", icon: <Moon className="size-4" /> },
  { value: "system", label: "System", icon: <Monitor className="size-4" /> },
];

export function DocsSettings({ locale }: { locale: string }) {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();

  // Gate theme reads until mount — next-themes is SSR-incompatible and
  // would otherwise cause a hydration flash of the wrong icon.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const activeTheme = mounted ? (theme ?? "system") : "system";
  const activeThemeOption =
    THEME_OPTIONS.find((o) => o.value === activeTheme) ?? THEME_OPTIONS[2]!;

  const internal = pathname === BASE_PATH || pathname.startsWith(BASE_PATH + "/")
    ? pathname.slice(BASE_PATH.length) || "/"
    : pathname;

  return (
    <div className="flex w-full items-center justify-end gap-2">
      {/* Language — left pill. Shows current language name. */}
      {/* Native disclosure + document links also work before client hydration.
          Locale changes replace the root html language and translated page tree. */}
      <details className="group relative">
        <summary aria-label="Switch language" className="cursor-pointer list-none rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
          {localeLabels[locale as keyof typeof localeLabels] ?? locale}
        </summary>
        <nav aria-label="Documentation languages" className="absolute bottom-full right-0 z-50 mb-2 min-w-36 rounded-lg border bg-popover p-1.5 text-popover-foreground shadow-md">
          {i18n.languages.map(lang => <a key={lang} href={`${BASE_PATH}${switchLocalePath(internal, lang)}`} hrefLang={lang} lang={lang} aria-current={lang === locale ? "page" : undefined} className={cn("block rounded-md px-2 py-1.5 text-sm hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring", lang === locale && "bg-accent")}>
            {localeLabels[lang as keyof typeof localeLabels]}
          </a>)}
        </nav>
      </details>

      {/* Theme — right icon button. Matched height to the sm pill via
          the icon-sm size token; without this the icon variant defaults
          to 32px while size="sm" is 28px, misaligning them. */}
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon-sm"
              className="shrink-0 text-muted-foreground"
              aria-label="Switch theme"
            >
              {activeThemeOption.icon}
            </Button>
          }
        />
        <DropdownMenuContent align="end" side="top" className="min-w-[140px]">
          {THEME_OPTIONS.map((opt) => (
            <DropdownMenuItem
              key={opt.value}
              onClick={() => setTheme(opt.value)}
              className={cn(
                "gap-2",
                opt.value === activeTheme && "bg-accent",
              )}
            >
              {opt.icon}
              {opt.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
