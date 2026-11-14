import Link from "next/link";
import { DEFAULT_SETTINGS, type Settings } from "@/adapters/mailbox/types";
import { vapidPublicKey } from "@/config/env";
import { getPreferences } from "@/core/server-preferences";
import { mailboxFor, requireSession } from "@/core/session";
import { messages } from "@/i18n/messages";
import { removePushSubscription, requestTestPush, savePushSubscription, saveSettings } from "../actions";
import { SettingsForm } from "./SettingsForm";

/** Step 5: push on/off, the morning brief time (12-hour, AM/PM) and the daily push limit. */
export default async function SettingsPage() {
  const session = await requireSession();
  const { lang } = await getPreferences();
  const t = messages(lang);
  let settings: Settings = { ...DEFAULT_SETTINGS, lang };
  try {
    settings = await mailboxFor(session).settings();
  } catch {
    // shown with the defaults; saving tells Khalid if the mailbox is unreachable
  }
  return (
    <div className="pb-16">
      <div className="mt-4 flex items-center justify-between gap-4">
        <h1 className="text-[2rem] leading-tight">{t.settings.title}</h1>
        <Link href="/today" className="text-sm text-muted hover:text-ink">{t.settings.back}</Link>
      </div>
      <SettingsForm
        initial={settings}
        lang={lang}
        t={t.settings}
        publicKey={vapidPublicKey()}
        save={saveSettings}
        subscribe={savePushSubscription}
        unsubscribe={removePushSubscription}
        test={requestTestPush}
      />
    </div>
  );
}
