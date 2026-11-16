import { isOnline, type WorkerStatus } from "@/adapters/mailbox/types";
import { APP_SETTINGS } from "@/config/app";
import { dayMonthClock } from "@/core/clock";
import type { Messages } from "@/i18n/messages";
import { AttentionIcon } from "./Icons";

/** Lines for the menu: PC online/offline and the last backup's result. */
export function statusLines(status: WorkerStatus | null, now: Date, t: Messages, lang: "ar" | "en"): string[] {
  const online = isOnline(status, now);
  const lines = [online ? t.pcOnline : t.pcOffline];
  if (status?.lastBackupAt) {
    const when = dayMonthClock(new Date(status.lastBackupAt), lang, APP_SETTINGS.timeZone);
    lines.push(t.lastBackup(when, status.lastBackupOk === true));
  } else {
    lines.push(t.noBackup);
  }
  return lines;
}

/** Shown under the top bar on every screen while the PC worker's heartbeat is missing; messages wait in the queue. */
export function OfflineBanner({ status, now, t }: { status: WorkerStatus | null; now: Date; t: Messages }) {
  if (isOnline(status, now)) return null;
  return (
    <div className="gutter flex-none pb-2">
      <p role="status" data-testid="pc-offline" className="note note-attention">
        <AttentionIcon />
        <span className="wrap">{t.pcOffline}</span>
      </p>
    </div>
  );
}
