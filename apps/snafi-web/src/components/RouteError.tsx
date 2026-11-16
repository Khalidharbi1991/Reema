"use client";

import { useSyncExternalStore } from "react";
import { messages, type Lang } from "@/i18n/messages";

const noSubscribe = () => () => {};
const pageLang = (): Lang => (document.documentElement.lang === "ar" ? "ar" : "en");

/** What a screen shows when it could not load: what happened, and a button to try again. */
export function RouteError({ screen, retry }: { screen: "today" | "inbox"; retry: () => void }) {
  const lang = useSyncExternalStore<Lang>(noSubscribe, pageLang, () => "en");
  const t = messages(lang);
  return (
    <div className="pt-12" data-testid="route-error">
      <p className="t-body wrap">{screen === "today" ? t.today.loadFailed : t.inbox.loadFailed}</p>
      <button type="button" className="btn btn-secondary mt-4" onClick={retry}>{t.retry}</button>
    </div>
  );
}
