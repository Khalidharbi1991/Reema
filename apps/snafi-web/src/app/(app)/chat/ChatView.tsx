import Link from "next/link";
import { PlaceholderBadge } from "@/components/Card";
import { Orb } from "@/components/Orb";
import { messages, type Lang } from "@/i18n/messages";

const SAMPLE = {
  en: {
    ahmad: "Good evening, Khalid. This is a sample conversation. I start replying in step 2.",
    you: "Sample: what is on my calendar tomorrow?",
    suggestions: ["Sample: summarise my mail", "Sample: plan tomorrow", "Sample: next prayer"],
  },
  ar: {
    ahmad: "مساء الخير يا خالد. هذه محادثة تجريبية، وأبدأ بالرد في المرحلة الثانية.",
    you: "نموذج: ما مواعيدي غداً؟",
    suggestions: ["نموذج: لخّص بريدي", "نموذج: خطّط ليوم غد", "نموذج: الصلاة القادمة"],
  },
} as const;

/** The chat screen with sample messages. Sending is off until step 2. */
export function ChatView({ lang }: { lang: Lang }) {
  const t = messages(lang);
  const s = SAMPLE[lang];
  return (
    <div className="flex min-h-[calc(100dvh-6rem)] flex-col">
      <div className="flex items-center gap-3 py-3">
        <Link href="/today" aria-label={t.back} className="flex h-11 w-11 items-center justify-center rounded-full text-xl text-muted">
          <span aria-hidden="true" className="rtl:rotate-180">←</span>
        </Link>
        <Orb label={t.chatTitle} size={36} />
        <div className="flex-1">
          <h1 className="text-xl leading-none">{t.chatTitle}</h1>
          <p className="text-xs text-muted">{t.chatSubtitle}</p>
        </div>
        <PlaceholderBadge label={t.placeholder} />
      </div>

      <ol className="flex-1 space-y-4 py-4" aria-label={t.chatTitle}>
        <li className="rise-in flex justify-start" style={{ ["--i" as string]: 0 }}>
          <div className="max-w-[85%] rounded-2xl rounded-ss-md border border-edge bg-card px-4 py-3 text-sm">{s.ahmad}</div>
        </li>
        <li className="rise-in flex flex-wrap gap-2 ps-1" style={{ ["--i" as string]: 1 }}>
          {s.suggestions.map((label) => (
            <button key={label} type="button" disabled className="min-h-9 rounded-full border border-edge px-3 text-xs text-gold-ink disabled:opacity-70">
              {label}
            </button>
          ))}
        </li>
        <li className="rise-in flex justify-end" style={{ ["--i" as string]: 2 }}>
          <div className="max-w-[85%] rounded-2xl rounded-se-md bg-gold/15 px-4 py-3 text-sm">{s.you}</div>
        </li>
      </ol>

      <form className="sticky bottom-0 bg-bg pt-2 pb-[max(env(safe-area-inset-bottom),1rem)]" aria-describedby="chat-note">
        <div className="flex items-end gap-2 rounded-2xl border border-edge bg-card p-2">
          <button type="button" disabled aria-label={t.attach} className="flex h-10 w-10 items-center justify-center rounded-full text-lg text-muted disabled:opacity-50">
            <span aria-hidden="true">＋</span>
          </button>
          <label htmlFor="chat-input" className="sr-only">{t.messagePlaceholder}</label>
          <textarea
            id="chat-input"
            rows={1}
            disabled
            placeholder={t.messagePlaceholder}
            className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm text-ink placeholder:text-muted focus:outline-none disabled:opacity-70"
          />
          <button type="submit" disabled className="min-h-10 rounded-xl bg-gold px-4 text-sm font-medium text-[#0E0E10] disabled:opacity-50">
            {t.send}
          </button>
        </div>
        <p id="chat-note" className="mt-2 text-center text-xs text-muted">{t.chatDisabled}</p>
      </form>
    </div>
  );
}
