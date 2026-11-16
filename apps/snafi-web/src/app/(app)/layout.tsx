import type { WorkerStatus } from "@/adapters/mailbox/types";
import { needsAttention } from "@/adapters/today/types";
import { OfflineBanner, statusLines } from "@/components/PcStatus";
import { ShellProvider } from "@/components/ShellState";
import { AppTopBar } from "@/components/TopBar";
import { unreadIds } from "@/core/inbox";
import { mailboxFor } from "@/core/session";
import { loadToday } from "@/core/today-data";
import { messages } from "@/i18n/messages";
import { signOut } from "./actions";

/**
 * The frame of every signed-in screen: the top bar (with the bell and the menu), then the
 * PC-offline or preview banner, then the screen.
 */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const { session, theme, lang, now, today } = await loadToday();
  const t = messages(lang);
  let status: WorkerStatus | null = null;
  try {
    status = await mailboxFor(session).workerStatus();
  } catch {
    status = null; // unknown counts as offline; the queue still holds messages
  }
  // The bell shows no badge when either list could not be read.
  const unread = today.approvals && today.cards ? unreadIds(today.approvals, today.cards, now) : null;
  const attention = [today.google, today.yahoo, today.todoist].some(needsAttention);
  return (
    <ShellProvider>
      <div className="shell">
        <a href="#content" className="skip-link">{t.skipToContent}</a>
        <AppTopBar
          unreadIds={unread}
          theme={theme}
          lang={lang}
          labels={{ menu: t.menu, closeMenu: t.closeMenu, theme: t.theme, dark: t.dark, light: t.light, language: t.language,
            signOut: t.signOut, settings: t.settingsLink, about: t.aboutLink, needsAttention: t.settings.needsAttention }}
          signOutAction={session.preview ? undefined : signOut}
          statusLines={session.preview ? [] : statusLines(status, now, t, lang)}
          settingsAttention={attention}
        />
        {session.preview ? (
          <div className="gutter flex-none pb-2">
            <p role="note" className="note" data-testid="preview-banner"><span className="wrap">{t.previewBanner}</span></p>
          </div>
        ) : (
          <OfflineBanner status={status} now={now} t={t} />
        )}
        <main id="content" className="shell-main gutter screen-in">{children}</main>
      </div>
    </ShellProvider>
  );
}
