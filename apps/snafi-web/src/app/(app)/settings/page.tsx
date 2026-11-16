import { DEFAULT_SETTINGS, type Settings } from "@/adapters/mailbox/types";
import { vapidPublicKey } from "@/config/env";
import { mailboxFor } from "@/core/session";
import { loadToday } from "@/core/today-data";
import { messages } from "@/i18n/messages";
import {
  removeAllPushSubscriptions, removePushSubscription, requestTestPush, savePushSubscription, saveSettings,
} from "../actions";
import { Connections } from "./Connections";
import { SettingsForm } from "./SettingsForm";

/**
 * Settings: the Google, Yahoo and Todoist connections (moved here from Today), then push on/off,
 * the morning brief time (12-hour, AM/PM) and the daily push limit. The top bar holds the title
 * and the way back.
 */
export default async function SettingsPage() {
  const { session, lang, today } = await loadToday();
  const t = messages(lang);
  let settings: Settings = { ...DEFAULT_SETTINGS, lang };
  try {
    settings = await mailboxFor(session).settings();
  } catch {
    // shown with the defaults; saving tells Khalid if the mailbox is unreachable
  }
  return (
    <div className="pt-4 pb-10" data-screen="settings">
      <Connections lang={lang} states={{ google: today.google, yahoo: today.yahoo, todoist: today.todoist }} />
      <SettingsForm
        initial={settings}
        lang={lang}
        t={t.settings}
        publicKey={vapidPublicKey()}
        save={saveSettings}
        subscribe={savePushSubscription}
        unsubscribe={removePushSubscription}
        unsubscribeAll={removeAllPushSubscriptions}
        test={requestTestPush}
      />
    </div>
  );
}
