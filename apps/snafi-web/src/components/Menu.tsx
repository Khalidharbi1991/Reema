"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { LANG_COOKIE, preferenceCookie, THEME_COOKIE, type Theme } from "@/core/preferences";
import { direction, type Lang } from "@/i18n/messages";

type Labels = {
  menu: string; closeMenu: string; theme: string; dark: string; light: string;
  language: string; signOut: string;
};

type Props = {
  labels: Labels;
  theme: Theme;
  lang: Lang;
  /** Server action for sign-out; omitted on the sign-in screen. */
  signOutAction?: () => Promise<void>;
  /** PC online/offline and the last backup, shown at the top of the menu. */
  statusLines?: string[];
};

/**
 * Three-line menu at the inline end of the top bar: top right in English,
 * mirrored to top left in Arabic.
 */
export function Menu({ labels, theme: initialTheme, lang, signOutAction, statusLines = [] }: Props) {
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const router = useRouter();
  const panelId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLElement>("button, [href]")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    const onClick = (e: MouseEvent) => {
      if (!panelRef.current?.contains(e.target as Node) && !buttonRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  const chooseTheme = (next: Theme) => {
    setTheme(next);
    document.documentElement.dataset.theme = next;
    document.cookie = preferenceCookie(THEME_COOKIE, next);
  };

  const chooseLang = (next: Lang) => {
    if (next === lang) return;
    document.cookie = preferenceCookie(LANG_COOKIE, next);
    document.documentElement.lang = next;
    document.documentElement.dir = direction(next);
    setOpen(false);
    router.refresh();
  };

  const option = (active: boolean) =>
    `min-h-11 flex-1 rounded-xl border px-3 text-sm transition-colors ${
      active ? "border-gold bg-gold/15 text-gold-ink" : "border-edge text-ink"
    }`;

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-label={open ? labels.closeMenu : labels.menu}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="flex h-11 w-11 flex-col items-center justify-center gap-[5px] rounded-full"
        data-testid="menu-button"
      >
        <span className="block h-px w-5 bg-ink" />
        <span className="block h-px w-5 bg-ink" />
        <span className="block h-px w-3.5 self-center bg-gold" />
      </button>
      {open && (
        <div
          ref={panelRef}
          id={panelId}
          role="dialog"
          aria-label={labels.menu}
          className="rise-in absolute end-0 top-12 z-50 w-72 rounded-2xl border border-edge bg-card p-4 shadow-2xl"
        >
          {statusLines.length > 0 && (
            <div className="mb-4 space-y-1 border-b border-edge pb-3 text-xs text-muted" data-testid="menu-status">
              {statusLines.map((line) => <p key={line}>{line}</p>)}
            </div>
          )}
          <p className="mb-2 text-xs uppercase tracking-[0.14em] text-muted">{labels.theme}</p>
          <div className="mb-4 flex gap-2" role="group" aria-label={labels.theme}>
            <button type="button" className={option(theme === "dark")} aria-pressed={theme === "dark"} onClick={() => chooseTheme("dark")}>
              {labels.dark}
            </button>
            <button type="button" className={option(theme === "light")} aria-pressed={theme === "light"} onClick={() => chooseTheme("light")}>
              {labels.light}
            </button>
          </div>
          <p className="mb-2 text-xs uppercase tracking-[0.14em] text-muted">{labels.language}</p>
          <div className="flex gap-2" role="group" aria-label={labels.language}>
            <button type="button" lang="en" className={option(lang === "en")} aria-pressed={lang === "en"} onClick={() => chooseLang("en")}>
              English
            </button>
            <button type="button" lang="ar" className={option(lang === "ar")} aria-pressed={lang === "ar"} onClick={() => chooseLang("ar")}>
              العربية
            </button>
          </div>
          {signOutAction && (
            <form action={signOutAction} className="mt-5 border-t border-edge pt-4">
              <button type="submit" className="min-h-11 w-full rounded-xl text-sm text-muted hover:text-ink">
                {labels.signOut}
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
