import { todaySource } from "@/adapters";
import { localHour } from "@/config/app";
import { getPreferences } from "@/core/server-preferences";
import { TodayView } from "./TodayView";

export default async function TodayPage() {
  const { lang } = await getPreferences();
  const now = new Date();
  const today = await todaySource().getToday(lang, now);
  return <TodayView lang={lang} hour={localHour(now)} today={today} />;
}
