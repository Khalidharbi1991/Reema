import { todaySource } from "@/adapters";
import { AutoRefresh } from "@/components/AutoRefresh";
import { localHour } from "@/config/app";
import { getPreferences } from "@/core/server-preferences";
import { mailboxFor, requireSession } from "@/core/session";
import { decideApproval, dismissCard } from "../actions";
import { TodayView } from "./TodayView";

export default async function TodayPage() {
  const session = await requireSession();
  const { lang } = await getPreferences();
  const now = new Date();
  const today = await todaySource(mailboxFor(session)).getToday(lang, now);
  return (
    <>
      <AutoRefresh seconds={30} />
      <TodayView lang={lang} hour={localHour(now)} today={today} decide={decideApproval} dismiss={dismissCard} />
    </>
  );
}
