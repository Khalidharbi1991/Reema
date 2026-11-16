import { needsAttention, type GoogleState } from "@/adapters/today/types";
import { AttentionIcon } from "@/components/Icons";
import { messages, type Lang } from "@/i18n/messages";

const SOURCES = ["google", "yahoo", "todoist"] as const;
type Props = { lang: Lang; states: Record<(typeof SOURCES)[number], GoogleState> };

/**
 * Settings, first section: one row each for Google, Yahoo Mail and Todoist, always shown, with
 * the same sentence for each state that Today used to show (AC-19). A state that needs Khalid is
 * gold with an icon and hidden "Needs attention": never colour alone.
 */
export function Connections({ lang, states }: Props) {
  const t = messages(lang);
  return (
    <section aria-labelledby="connections-title" data-testid="connections">
      <h2 id="connections-title" className="t-heading mb-1">{t.settings.connectionsTitle}</h2>
      <ul className="divide-y divide-edge">
        {SOURCES.map((source) => {
          const state = states[source];
          const attention = needsAttention(state);
          return (
            <li key={source} className="min-w-0 py-3">
              <p className="t-strong">{t.settings.service[source]}</p>
              <p role="status" data-testid={`${source}-status`} data-state={state}
                className={`t-small with-icon ${attention ? "text-gold-ink" : "text-muted"}`}>
                {attention && <AttentionIcon />}
                <span className="wrap">
                  {attention && <span className="sr-only">{t.settings.needsAttention}: </span>}
                  {t[source][state]}
                </span>
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
