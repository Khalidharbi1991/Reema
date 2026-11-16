"use client";

import type { ComponentProps } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { messages } from "@/i18n/messages";
import { Bell } from "./Bell";
import { BackIcon } from "./Icons";
import { Menu } from "./Menu";
import { Orb } from "./Orb";
import { useShell } from "./ShellState";

export type Screen = "today" | "inbox" | "chat" | "settings" | "about" | "sign-in";

type Props = {
  screen: Screen;
  /** Unread ids for the bell; null when unknown. Not used on Sign-in, which has no bell. */
  unreadIds?: string[] | null;
} & ComponentProps<typeof Menu>;

/**
 * The top bar (docs/UI.md 3.1). Inline start: the wordmark on Today; a back arrow and the screen's
 * name (the page's h1) on Inbox, Chat and Settings. Inline end: the bell, then the menu, which
 * stays outermost. Sign-in has the menu only. Everything mirrors in Arabic.
 */
export function TopBar({ screen, unreadIds = null, ...menu }: Props) {
  const t = messages(menu.lang);
  const { thinking } = useShell();
  const title = screen === "inbox" ? t.inbox.title : screen === "chat" ? t.chatTitle : screen === "settings" ? t.settings.title
    : screen === "about" ? t.about.title : "";
  return (
    <header className="topbar gutter" data-screen-bar={screen}>
      <div className="flex min-w-0 flex-1 items-center gap-2">
        {screen === "today" && <span className="t-wordmark" data-testid="wordmark">{t.appName}</span>}
        {title && (
          <>
            <Link href="/today" aria-label={t.inbox.back} className="icon-btn -ms-2.5" data-testid="back"><BackIcon /></Link>
            {screen === "chat" && <Orb label="" size={32} state={thinking ? "thinking" : "still"} />}
            <div className="min-w-0 flex-1">
              <h1 className="t-heading truncate">{title}</h1>
              {screen === "chat" && thinking && <p className="t-caption truncate text-muted">{t.thinking}</p>}
            </div>
          </>
        )}
      </div>
      <div className="flex flex-none items-center gap-1">
        {screen !== "sign-in" && <Bell lang={menu.lang} unreadIds={unreadIds} current={screen === "inbox"} />}
        <div className="-me-3"><Menu {...menu} /></div>
      </div>
    </header>
  );
}

const SCREENS: Record<string, Screen> = { "/inbox": "inbox", "/chat": "chat", "/settings": "settings", "/about": "about" };

/** The signed-in screens' bar: it reads the address to know which screen it is on. */
export function AppTopBar(props: Omit<Props, "screen">) {
  const path = usePathname() ?? "";
  return <TopBar {...props} screen={SCREENS[path] ?? "today"} />;
}
