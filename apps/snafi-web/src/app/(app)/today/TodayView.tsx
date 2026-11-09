import { ApprovalCard } from "@/components/ApprovalCard";
import { Card, PlaceholderBadge } from "@/components/Card";
import { Orb } from "@/components/Orb";
import { PrayerRing } from "@/components/PrayerRing";
import { greetingFor } from "@/core/preferences";
import type { TodaySnapshot } from "@/adapters/today/types";
import { messages, type Lang } from "@/i18n/messages";

type Props = {
  lang: Lang;
  hour: number;
  today: TodaySnapshot;
  decide: (id: string, decision: "approved" | "rejected", argsHash: string) => Promise<{ ok: boolean; status?: string }>;
};

/** The Today screen. Pure view: all data comes in through props. */
export function TodayView({ lang, hour, today, decide }: Props) {
  const t = messages(lang);
  const sample = <PlaceholderBadge label={t.placeholder} />;
  const anySample = Object.values(today.samples).some(Boolean);
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

      {anySample && <p className="rise-in mt-3 text-xs text-muted" style={{ ["--i" as string]: 1 }}>{t.placeholderNote}</p>}

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {today.nextEvent && (
          <Card title={t.nextEvent} index={1} badge={today.samples.nextEvent ? sample : null}>
            <p className="text-base">{today.nextEvent.title}</p>
            <p className="mt-1 text-sm text-muted">
              <span dir="ltr" className="tabular-nums">{today.nextEvent.time}</span> · {today.nextEvent.place}
            </p>
          </Card>
        )}

        <Card title={t.topTasks} index={2} badge={today.samples.tasks ? sample : null}>
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
          <Card key={card.id} title={t.ahmadCards} index={3 + i} badge={today.samples.cards ? sample : null}>
            <p className="text-sm font-medium">{card.title}</p>
            <p className="mt-1 text-sm text-muted">{card.body}</p>
          </Card>
        ))}

        <Card title={t.approvals} index={4 + today.cards.length}>
          {today.approvals.length === 0 ? (
            <p className="text-sm text-muted">{t.approvalsEmpty}</p>
          ) : (
            <ul className="space-y-3">
              {today.approvals.map((card) => (
                <li key={card.id}>
                  <ApprovalCard card={card} decide={decide}
                    labels={{ approve: t.approve, reject: t.reject, status: t.cardStatus, failed: t.decideFailed, exactly: t.exactly, expires: t.expires }} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-40 flex justify-center pb-[max(env(safe-area-inset-bottom),1.25rem)]">
        <Orb href="/chat" label={t.openChat} />
      </div>
    </div>
  );
}
