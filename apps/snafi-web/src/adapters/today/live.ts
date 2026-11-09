import type { ApprovalCard } from "@/adapters/mailbox/types";
import { APP_SETTINGS } from "@/config/app";
import type { Lang } from "@/i18n/messages";
import { gregorianDate, SAMPLE } from "./placeholder";
import { hijriDate, nextPrayer } from "./prayer";
import type { TodaySnapshot, TodaySource } from "./types";

/**
 * Step 2 Today: real prayer times and Hijri date for the configured city, real pending
 * approvals from the mailbox. Event, tasks and cards stay marked samples until steps 3-5.
 */
export class LiveTodaySource implements TodaySource {
  constructor(private readonly pendingApprovals: () => Promise<ApprovalCard[]>) {}

  async getToday(lang: Lang, now: Date): Promise<TodaySnapshot> {
    const city = APP_SETTINGS.city;
    const prayer = nextPrayer(city, now);
    const s = SAMPLE[lang];
    let approvals: ApprovalCard[] = [];
    try {
      approvals = await this.pendingApprovals();
    } catch {
      approvals = []; // the rest of Today still shows if the mailbox is unreachable
    }
    return {
      gregorianDate: gregorianDate(lang, now),
      hijriDate: hijriDate(now, lang, city.timeZone),
      nextPrayer: { key: prayer.key, time: prayer.time, progress: prayer.progress },
      nextEvent: { ...s.event },
      tasks: s.tasks.map((t) => ({ ...t })),
      cards: s.cards.map((c) => ({ ...c })),
      approvals,
      samples: { prayer: false, nextEvent: true, tasks: true, cards: true },
    };
  }
}
