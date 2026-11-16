import { AutoRefresh } from "@/components/AutoRefresh";
import { localHour } from "@/config/app";
import { loadToday } from "@/core/today-data";
import { TodayView } from "./TodayView";

export default async function TodayPage() {
  const { lang, now, today } = await loadToday();
  return (
    <>
      <AutoRefresh seconds={30} />
      <TodayView lang={lang} hour={localHour(now)} today={today} now={now} />
    </>
  );
}
