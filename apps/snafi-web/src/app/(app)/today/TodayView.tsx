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

      {(["google", "yahoo", "todoist"] as const).filter((source) => today[source] !== "ok").map((source) => (
        <p key={source} role="status" data-testid={`${source}-status`} data-state={today[source]}
          className="rise-in mt-3 rounded-xl border border-gold/40 px-3 py-2 text-xs text-gold-ink" style={{ ["--i" as string]: 1 }}>
          {t[source][today[source]]}
        </p>
      ))}

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Card title={t.nextEvent} index={1} badge={today.samples.nextEvent ? sample : null}>
          {today.nextEvent ? (
            <>
              <p className="text-base" dir="auto">{today.nextEvent.title}</p>
              <p className="mt-1 text-sm text-muted">
                <span dir="ltr" className="tabular-nums">{today.nextEvent.time}</span>
                {today.nextEvent.place && <> · <span dir="auto">{today.nextEvent.place}</span></>}
              </p>
            </>
          ) : (
            <p className="text-sm text-muted">{today.google === "ok" ? t.noEvents : "—"}</p>
          )}
        </Card>

        <Card title={t.importantEmail} index={2} badge={today.samples.emails ? sample : null}>
          {today.emails.length === 0 ? (
            <p className="text-sm text-muted">{today.google === "ok" || today.yahoo === "ok" ? t.noImportantEmail : "—"}</p>
          ) : (
            <ul className="space-y-3" data-testid="important-emails">
              {today.emails.map((m) => (
                <li key={m.id} className="flex items-start gap-3" data-account={m.account ?? "gmail"}>
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-gold" aria-hidden="true" />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium" dir="auto">{m.from}</span>
                      {!today.samples.emails && (
                        <span data-testid="email-account" dir="ltr"
                          className="shrink-0 rounded-full border border-gold/40 px-1.5 text-[10px] leading-4 text-gold-ink">
                          {t.accountLabel[m.account ?? "gmail"]}
                        </span>
                      )}
                    </span>
                    <span className="block truncate text-sm text-muted" dir="auto">{m.subject}</span>
                  </span>
                  <span dir="ltr" className="shrink-0 text-xs tabular-nums text-muted">{m.time}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title={t.topTasks} index={3} badge={today.samples.tasks ? sample : null}>
          {today.tasks.length === 0 ? (
            <p className="text-sm text-muted">{today.todoist === "ok" ? t.noTasks : "—"}</p>
          ) : (
            <ul className="space-y-3" data-testid="top-tasks">
              {today.tasks.map((task) => (
                <li key={task.id} className="flex items-start gap-3" data-overdue={task.overdue ? "true" : undefined}>
                  <span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${task.priority === 1 ? "bg-gold-ink" : "bg-gold"}`} aria-hidden="true" />
                  <span className="min-w-0 flex-1 text-sm" dir="auto">{task.title}</span>
                  <span className={`shrink-0 text-xs ${task.overdue ? "text-gold-ink" : "text-muted"}`}>{task.due}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {today.cards.map((card, i) => (
          <Card key={card.id} title={t.ahmadCards} index={4 + i} badge={today.samples.cards ? sample : null}>
            <p className="text-sm font-medium">{card.title}</p>
            <p className="mt-1 text-sm text-muted">{card.body}</p>
          </Card>
        ))}

        <Card title={t.approvals} index={5 + today.cards.length}>
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
