import { isOnline, type WorkerStatus } from "@/adapters/mailbox/types";
import { APP_SETTINGS } from "@/config/app";
import type { Messages } from "@/i18n/messages";

/** Lines for the menu: PC online/offline and the last backup's result. */
export function statusLines(status: WorkerStatus | null, now: Date, t: Messages, lang: "ar" | "en"): string[] {
  const online = isOnline(status, now);
  const lines = [online ? t.pcOnline : t.pcOffline];
  if (status?.lastBackupAt) {
    const when = new Intl.DateTimeFormat(lang === "ar" ? "ar-SA-u-ca-gregory-nu-latn" : "en-GB", {
      day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: APP_SETTINGS.timeZone,
    }).format(new Date(status.lastBackupAt));
    lines.push(t.lastBackup(when, status.lastBackupOk === true));
  } else {
    lines.push(t.noBackup);
  }
  return lines;
}

/** Shown on every screen while the PC worker's heartbeat is missing; messages wait in the queue. */
export function OfflineBanner({ status, now, t }: { status: WorkerStatus | null; now: Date; t: Messages }) {
  if (isOnline(status, now)) return null;
  return (
    <p role="status" data-testid="pc-offline"
      className="mx-5 mt-3 rounded-xl border border-gold/40 px-4 py-2 text-xs text-gold-ink">
      {t.pcOffline}
    </p>
  );
}
