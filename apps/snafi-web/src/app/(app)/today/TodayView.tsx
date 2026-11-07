import { ApprovalButtons } from "@/components/ApprovalButtons";
import { Card, PlaceholderBadge } from "@/components/Card";
import { Orb } from "@/components/Orb";
import { PrayerRing } from "@/components/PrayerRing";
import { greetingFor } from "@/core/preferences";
import type { TodaySnapshot } from "@/adapters/today/types";
import { messages, type Lang } from "@/i18n/messages";

type Props = { lang: Lang; hour: number; today: TodaySnapshot };

/** The Today screen. Pure view: all data comes in through props. */
export function TodayView({ lang, hour, today }: Props) {
  const t = messages(lang);
  const badge = today.placeholder ? <PlaceholderBadge label={t.placeholder} /> : null;
  const prayerName = t.prayers[today.nextPrayer.key];
  const pct = Math.round(today.nextPrayer.progress * 100);

  return (
    <div className="pb-28">
      <section className="rise-in mt-4 flex items-center justify-between gap-4" style={{ ["--i" as string]: 0 }}>
        <div className="min-w-0">
          <h1 className="text-[2.1rem] leading-tight">
            {t.greeting[greetingFor(hour)]}{lang === "ar" ? "، " : ", "}<span className="text-gold-ink">{t.ownerName}</span>
          </h1>
          <p className="mt-1 text-sm text-muted">{today.gregorianDate}</p>
          <p className="text-sm text-muted">{today.hijriDate}</p>
        </div>
        <PrayerRing
          name={prayerName}
          time={today.nextPrayer.time}
          progress={today.nextPrayer.progress}
          label={t.prayerRingLabel(prayerName, today.nextPrayer.time, pct)}
        />
      </section>

      {today.placeholder && <p className="rise-in mt-3 text-xs text-muted" style={{ ["--i" as string]: 1 }}>{t.placeholderNote}</p>}

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {today.nextEvent && (
          <Card title={t.nextEvent} index={1} badge={badge}>
            <p className="text-base">{today.nextEvent.title}</p>
            <p className="mt-1 text-sm text-muted">
              <span dir="ltr" className="tabular-nums">{today.nextEvent.time}</span> · {today.nextEvent.place}
            </p>
          </Card>
        )}

        <Card title={t.topTasks} index={2} badge={badge}>
          <ul className="space-y-3">
            {today.tasks.map((task) => (
              <li key={task.id} className="flex items-start gap-3">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-gold" aria-hidden="true" />
                <span className="flex-1 text-sm">{task.title}</span>
                <span className="text-xs text-muted">{task.due}</span>
              </li>
            ))}
          </ul>
        </Card>

        {today.cards.map((card, i) => (
          <Card key={card.id} title={t.ahmadCards} index={3 + i} badge={badge}>
            <p className="text-sm font-medium">{card.title}</p>
            <p className="mt-1 text-sm text-muted">{card.body}</p>
          </Card>
        ))}

        {today.approvals.length > 0 && (
          <Card title={t.approvals} index={4 + today.cards.length} badge={badge}>
            <ul className="space-y-4">
              {today.approvals.map((a) => (
                <li key={a.id}>
                  <p className="text-sm">{a.title}</p>
                  <p className="text-xs text-muted">{a.detail}</p>
                  <ApprovalButtons approve={t.approve} reject={t.reject} disabledNote={t.approvalsDisabled} />
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      <div className="fixed inset-x-0 bottom-0 z-40 flex justify-center pb-[max(env(safe-area-inset-bottom),1.25rem)]">
        <Orb href="/chat" label={t.openChat} />
      </div>
    </div>
  );
}
