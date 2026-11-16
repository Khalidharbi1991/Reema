import { Skeleton } from "@/components/Card";
import { getPreferences } from "@/core/server-preferences";
import { messages } from "@/i18n/messages";

/** Four skeleton rows while the Inbox loads; no spinners. */
export default async function InboxLoading() {
  const { lang } = await getPreferences();
  return (
    <div className="pt-4" aria-busy="true">
      <span className="sr-only">{messages(lang).loading}</span>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="space-y-2 py-3">
          <Skeleton className="h-4 w-[30%]" />
          <Skeleton className="h-5 w-[70%]" />
        </div>
      ))}
    </div>
  );
}
