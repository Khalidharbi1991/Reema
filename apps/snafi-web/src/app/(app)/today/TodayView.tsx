import Link from "next/link";
import type { TodaySnapshot } from "@/adapters/today/types";
import { ChevronForwardIcon, TaskCircleIcon } from "@/components/Icons";
import { NowCard } from "@/components/NowCard";
import { Orb } from "@/components/Orb";
import { APP_SETTINGS } from "@/config/app";
import { chooseAhmadMessage, inboxTime } from "@/core/inbox";
import { greetingFor } from "@/core/preferences";
import { messages, type Lang } from "@/i18n/messages";

type Props = { lang: Lang; hour: number; today: TodaySnapshot; now: Date };

/** The plan shows at most this many events and tasks, then "+N more". */
export const PLAN_EVENTS = 5;
export const PLAN_TASKS = 3;

/**
 * The Today screen: the greeting with both dates, the Now card, Ahmad's one message, today's plan
 * and the orb. Nothing else (AC-12, AC-13). Ahmad's message comes before the plan so a waiting
 * approval is on the first screen. Pure view: all data comes in through props.
 */
export function TodayView({ lang, hour, today, now }: Props) {
  const t = messages(lang);
  const comma = lang === "ar" ? "، " : ", ";
  const tz = APP_SETTINGS.timeZone;
  const events = today.events.slice(0, PLAN_EVENTS);
  const moreEvents = today.events.length - events.length;
  const tasks = today.tasks.slice(0, PLAN_TASKS);
  const moreTasks = today.tasks.length - tasks.length;
  const message = chooseAhmadMessage(today.approvals ?? [], today.cards ?? [], now, tz);
  const second = !message ? "" : message.kind === "approval"
    ? (message.more > 0 ? t.ahmad.waitingMore(message.more) : t.ahmad.waiting)
    : `${t.inbox.kind[message.kind]} ${inboxTime(message.createdAt, lang, now, tz)}`;
  const quiet = "t-small text-muted";

  return (
    // orb-clear (globals.css) keeps the last line of the plan clear of the orb and its glow.
    <div className="orb-clear pt-4" data-screen="today">
      <h1 className="t-title wrap">{t.greeting[greetingFor(hour)]}{comma}{t.ownerName}</h1>
      <p className={`${quiet} mt-1`} data-testid="today-dates">
        <span>{today.gregorianDate}</span><span className="sr-only">, </span>
        <span className="date-rule" aria-hidden="true" />
        <span>{today.hijriDate}</span>
      </p>
      {today.sample && <p className={`${quiet} mt-1`} data-testid="sample-note">{t.placeholderNote}</p>}

      <NowCard lang={lang} items={today.now} serverNow={now.toISOString()} />

      <section aria-labelledby="ahmad-title" data-testid="ahmad">
        <h2 id="ahmad-title" className="t-heading mt-8 mb-3">{t.ahmadCards}</h2>
        {message ? (
          <Link href={`/inbox?open=${encodeURIComponent(message.id)}`} data-testid="ahmad-message" data-kind={message.kind}
            aria-label={`${message.title}. ${second}. ${t.ahmad.openInInbox}`}
            className="row-press -mx-2 grid min-h-11 items-center gap-x-2 px-2 py-2" style={{ gridTemplateColumns: "minmax(0, 1fr) auto" }}>
            <span className="min-w-0">
              <span className="t-body wrap clamp-2" data-slot="message-title"><bdi>{message.title}</bdi></span>
              {message.kind === "approval" ? (
                <span className="t-small block text-gold-ink">{second}</span>
              ) : (
                <span className={`${quiet} flex gap-2`}>
                  <span>{t.inbox.kind[message.kind]}</span>
                  <span className="nums"><bdi>{inboxTime(message.createdAt, lang, now, tz)}</bdi></span>
                </span>
              )}
            </span>
            <ChevronForwardIcon className="flex-none text-muted" />
          </Link>
        ) : (
          <p className={quiet} data-testid="ahmad-empty">{t.noCards}</p>
        )}
      </section>

      <section aria-labelledby="plan-title" data-testid="plan">
        <h2 id="plan-title" className="t-heading mt-8 mb-3">{t.plan.title}</h2>
        <ul aria-label={t.plan.events} data-testid="plan-events">
          {events.map((event) => (
            <li key={event.id} className="plan-row">
              <span className={`${quiet} nums pt-0.5`}><bdi>{event.allDay ? t.plan.allDay : event.time}</bdi></span>
              <span className="t-body wrap clamp-2" data-slot="event-title"><bdi>{event.title}</bdi></span>
            </li>
          ))}
          {moreEvents > 0 && (
            <li className="plan-row"><span /><span className={quiet} aria-label={t.plan.moreEventsLabel(moreEvents)}>{t.plan.more(moreEvents)}</span></li>
          )}
          {events.length === 0 && (
            <li className="plan-row"><span /><span className={quiet}>{today.google === "ok" ? t.plan.noEvents : t.plan.eventsUnavailable}</span></li>
          )}
        </ul>
        <hr className="hairline my-3" />
        <ul aria-label={t.plan.tasks} data-testid="plan-tasks">
          {tasks.map((task) => {
            // An overdue task says so in words, not by colour alone.
            const due = task.overdue && !task.due.includes(t.plan.overdue)
              ? (task.due ? `${t.plan.overdue}${comma}${task.due}` : t.plan.overdue) : task.due;
            return (
              <li key={task.id} className="plan-row" data-overdue={task.overdue ? "true" : undefined}>
                <span className="pt-1 text-muted"><TaskCircleIcon /></span>
                <span className="min-w-0">
                  <span className="t-body wrap clamp-2" data-slot="task-title"><bdi>{task.title}</bdi></span>
                  {/* The due line sits under its task's own text, never at the far edge of the column (Arabic at 360/390). */}
                  {due && (
                    <span className={`t-caption wrap block text-start ${task.overdue ? "font-medium text-gold-ink" : "text-muted"}`}><bdi>{due}</bdi></span>
                  )}
                </span>
              </li>
            );
          })}
          {moreTasks > 0 && (
            <li className="plan-row"><span /><span className={quiet} aria-label={t.plan.moreTasksLabel(moreTasks)}>{t.plan.more(moreTasks)}</span></li>
          )}
          {tasks.length === 0 && (
            <li className="plan-row"><span /><span className={quiet}>{today.todoist === "ok" ? t.plan.noTasks : t.plan.tasksUnavailable}</span></li>
          )}
        </ul>
      </section>

      <div className="orb-dock">
        <Orb href="/chat" label={t.openChat} />
      </div>
    </div>
  );
}
