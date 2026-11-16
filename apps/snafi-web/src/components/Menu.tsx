"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LANG_COOKIE, preferenceCookie, THEME_COOKIE, type Theme } from "@/core/preferences";
import { direction, type Lang } from "@/i18n/messages";
import { AttentionIcon } from "./Icons";

type Labels = {
  menu: string; closeMenu: string; theme: string; dark: string; light: string;
  language: string; signOut: string; settings?: string;
  /** Hidden text for the mark on Settings when a connection needs attention. */
  needsAttention?: string;
};

type Props = {
  labels: Labels;
  theme: Theme;
  lang: Lang;
  /** Server action for sign-out; omitted on the sign-in screen. */
  signOutAction?: () => Promise<void>;
  /** PC online/offline and the last backup, shown at the top of the menu. */
  statusLines?: string[];
  /** A connection (Google, Yahoo or Todoist) is broken: the Settings item carries a small mark. */
  settingsAttention?: boolean;
};

/**
 * Three-line menu at the inline end of the top bar: top right in English,
 * mirrored to top left in Arabic.
 */
export function Menu({ labels, theme: initialTheme, lang, signOutAction, statusLines = [], settingsAttention = false }: Props) {
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

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-label={open ? labels.closeMenu : labels.menu}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="icon-btn flex-col gap-[5px]"
        data-testid="menu-button"
      >
        <span className="block h-px w-5 bg-ink" />
        <span className="block h-px w-5 bg-ink" />
        <span className="block h-px w-3.5 self-center bg-gold-ink" />
      </button>
      {open && (
        <div
          ref={panelRef}
          id={panelId}
          role="dialog"
          aria-label={labels.menu}
          className="absolute end-3 top-12 z-50 rounded-2xl border border-edge bg-raised p-4"
          style={{ inlineSize: "min(18rem, calc(100vw - 2 * var(--gutter)))", boxShadow: "var(--shadow-float)" }}
        >
          {statusLines.length > 0 && (
            <div className="t-small wrap mb-4 space-y-1 border-b border-edge pb-3 text-muted" data-testid="menu-status">
              {statusLines.map((line) => <p key={line}>{line}</p>)}
            </div>
          )}
          <p className="t-small mb-2 text-muted">{labels.theme}</p>
          <div className="mb-4 flex gap-2" role="group" aria-label={labels.theme}>
            <button type="button" className="option" aria-pressed={theme === "dark"} onClick={() => chooseTheme("dark")}>
              {labels.dark}
            </button>
            <button type="button" className="option" aria-pressed={theme === "light"} onClick={() => chooseTheme("light")}>
              {labels.light}
            </button>
          </div>
          <p className="t-small mb-2 text-muted">{labels.language}</p>
          <div className="flex gap-2" role="group" aria-label={labels.language}>
            <button type="button" lang="en" className="option" aria-pressed={lang === "en"} onClick={() => chooseLang("en")}>
              English
            </button>
            <button type="button" lang="ar" className="option" aria-pressed={lang === "ar"} onClick={() => chooseLang("ar")}>
              العربية
            </button>
          </div>
          {signOutAction && labels.settings && (
            <Link href="/settings" onClick={() => setOpen(false)} data-testid="menu-settings"
              className="btn btn-secondary mt-5 w-full gap-2">
              {labels.settings}
              {settingsAttention && (
                <span className="flex items-center text-gold-ink" data-testid="settings-attention">
                  <AttentionIcon /><span className="sr-only">{labels.needsAttention ?? ""}</span>
                </span>
              )}
            </Link>
          )}
          {signOutAction && (
            <form action={signOutAction} className="mt-5 border-t border-edge pt-4">
              <button type="submit" className="btn btn-quiet w-full">
                {labels.signOut}
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
