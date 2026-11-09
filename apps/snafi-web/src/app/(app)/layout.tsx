import type { WorkerStatus } from "@/adapters/mailbox/types";
import { OfflineBanner, statusLines } from "@/components/PcStatus";
import { TopBar } from "@/components/TopBar";
import { getPreferences } from "@/core/server-preferences";
import { mailboxFor, requireSession } from "@/core/session";
import { messages } from "@/i18n/messages";
import { signOut } from "./actions";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await requireSession();
  const { theme, lang } = await getPreferences();
  const t = messages(lang);
  let status: WorkerStatus | null = null;
  try {
    status = await mailboxFor(session).workerStatus();
  } catch {
    status = null; // unknown counts as offline; the queue still holds messages
  }
  const now = new Date();
  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col">
      {session.preview ? (
        <p role="note" className="mx-5 mt-3 rounded-xl border border-edge px-4 py-2 text-xs text-muted" data-testid="preview-banner">
          {t.previewBanner}
        </p>
      ) : (
        <OfflineBanner status={status} now={now} t={t} />
      )}
      <TopBar
        appName={t.appName}
        theme={theme}
        lang={lang}
        labels={{ menu: t.menu, closeMenu: t.closeMenu, theme: t.theme, dark: t.dark, light: t.light, language: t.language, signOut: t.signOut }}
        signOutAction={session.preview ? undefined : signOut}
        statusLines={session.preview ? [] : statusLines(status, now, t, lang)}
      />
      <main className="screen-in flex-1 px-5 pb-[max(env(safe-area-inset-bottom),1.5rem)]">{children}</main>
    </div>
  );
}
