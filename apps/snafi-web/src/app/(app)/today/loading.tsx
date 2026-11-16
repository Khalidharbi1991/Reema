import { Skeleton } from "@/components/Card";
import { getPreferences } from "@/core/server-preferences";
import { messages } from "@/i18n/messages";

/** Skeleton while Today loads, in the same places as the content; no spinners. */
export default async function TodayLoading() {
  const { lang } = await getPreferences();
  return (
    <div className="pt-4" aria-busy="true">
      <span className="sr-only">{messages(lang).loading}</span>
      <Skeleton className="h-8 w-3/5" />
      <Skeleton className="mt-2 h-4 w-[45%]" />
      <Skeleton className="mt-6 h-24 rounded-2xl" />
      <div className="mt-8 space-y-3">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-5" />)}
      </div>
      <div className="mt-8 space-y-2">
        <Skeleton className="h-5 w-4/5" />
        <Skeleton className="h-4 w-2/5" />
      </div>
    </div>
  );
}
