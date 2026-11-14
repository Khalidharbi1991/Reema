"use client";

import { useId, useState, useSyncExternalStore, useTransition } from "react";
import { CAP_MAX, CAP_MIN, type Settings } from "@/adapters/mailbox/types";
import { joinHHMM, splitHHMM } from "@/core/clock";
import type { Lang, Messages } from "@/i18n/messages";

type Result = Promise<{ ok: boolean }>;
type Props = {
  initial: Settings;
  lang: Lang;
  t: Messages["settings"];
  /** NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY, or null when push is not set up on the server. */
  publicKey: string | null;
  save: (s: { pushEnabled: boolean; briefTime: string; dailyCap: number }) => Result;
  subscribe: (k: { endpoint: string; p256dh: string; auth: string }) => Result;
  unsubscribe: (endpoint: string) => Result;
  test: () => Result;
};

const HOURS = Array.from({ length: 12 }, (_, i) => i + 1);
const MINUTES = Array.from({ length: 12 }, (_, i) => i * 5);

/** base64url (no padding) of a key from PushSubscription.toJSON(), whatever form the browser gave. */
export function toBase64Url(value: string | undefined): string {
  return (value ?? "").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const b64 = base64url.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (base64url.length % 4)) % 4);
  const raw = atob(b64);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

const noSubscribe = () => () => undefined;

function pushSupported(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

/**
 * The Settings screen. Push is asked for only when Khalid taps On (iPhone requires a tap, and only in
 * the installed app). The phone's push address goes to the database through save_push_subscription,
 * which accepts only the four browser push services.
 */
export function SettingsForm({ initial, lang, t, publicKey, save, subscribe, unsubscribe, test }: Props) {
  const start = splitHHMM(initial.briefTime);
  const [push, setPush] = useState(initial.pushEnabled);
  const [hour12, setHour12] = useState(start.hour12);
  const [minute, setMinute] = useState(start.minute);
  const [pm, setPm] = useState(start.pm);
  const [cap, setCap] = useState(String(initial.dailyCap));
  const [note, setNote] = useState<string | null>(null);
  const [pending, run] = useTransition();
  const ids = { hour: useId(), minute: useId(), cap: useId() };

  // Whether this browser can take push at all (server render: assume yes, to avoid a flash).
  const supported = useSyncExternalStore(noSubscribe, pushSupported, () => true);

  const capValue = Number.parseInt(cap, 10);
  const capOk = Number.isInteger(capValue) && capValue >= CAP_MIN && capValue <= CAP_MAX && /^\d+$/.test(cap.trim());
  const values = (pushEnabled = push) => ({ pushEnabled, briefTime: joinHHMM(hour12, minute, pm), dailyCap: capValue });

  const onSave = () => run(async () => {
    if (!capOk) return setNote(t.saveFailed);
    setNote((await save(values())).ok ? t.saved : t.saveFailed);
  });

  const turnOn = () => run(async () => {
    setNote(null);
    if (!publicKey) return setNote(t.pushNotSetUp);
    if (!pushSupported()) return setNote(t.pushUnsupported);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") return setNote(t.pushDenied);
      const reg = await navigator.serviceWorker.ready;
      const existing = await reg.pushManager.getSubscription();
      const sub = existing ?? await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) });
      const json = sub.toJSON();
      const saved = await subscribe({ endpoint: sub.endpoint, p256dh: toBase64Url(json.keys?.p256dh), auth: toBase64Url(json.keys?.auth) });
      if (!saved.ok) {
        await sub.unsubscribe().catch(() => undefined);
        return setNote(t.pushFailed);
      }
      const ok = capOk && (await save(values(true))).ok;
      setPush(true);
      setNote(ok ? t.saved : t.saveFailed);
    } catch {
      setNote(t.pushFailed);
    }
  });

  const turnOff = () => run(async () => {
    setNote(null);
    try {
      const reg = pushSupported() ? await navigator.serviceWorker.ready : null;
      const sub = reg ? await reg.pushManager.getSubscription() : null;
      if (sub) {
        await unsubscribe(sub.endpoint);
        await sub.unsubscribe().catch(() => undefined);
      }
    } catch {
      // the server switch below still stops every push
    }
    setPush(false);
    setNote(capOk && (await save(values(false))).ok ? t.saved : t.saveFailed);
  });

  const onTest = () => run(async () => setNote((await test()).ok ? t.testSent : t.testFailed));

  const option = (active: boolean) =>
    `min-h-11 flex-1 rounded-xl border px-3 text-sm transition-colors ${active ? "border-gold bg-gold/15 text-gold-ink" : "border-edge text-ink"}`;
  const field = "min-h-11 rounded-xl border border-edge bg-card px-3 text-sm text-ink";

  return (
    <div className="mt-6 space-y-6" data-testid="settings-form">
      <section className="rounded-2xl border border-edge bg-card p-4">
        <h2 className="text-lg">{t.pushTitle}</h2>
        <div className="mt-3 flex gap-2" role="group" aria-label={t.pushTitle}>
          <button type="button" className={option(push)} aria-pressed={push} disabled={pending} onClick={turnOn}>{t.pushOn}</button>
          <button type="button" className={option(!push)} aria-pressed={!push} disabled={pending} onClick={turnOff}>{t.pushOff}</button>
        </div>
        <p className="mt-3 text-xs text-muted">{t.pushHelp}</p>
        {!publicKey && <p className="mt-2 text-xs text-gold-ink" data-testid="push-not-set-up">{t.pushNotSetUp}</p>}
        {publicKey && !supported && <p className="mt-2 text-xs text-gold-ink">{t.pushUnsupported}</p>}
        <button type="button" onClick={onTest} disabled={pending || !push}
          className="mt-3 min-h-11 rounded-xl border border-edge px-4 text-sm disabled:opacity-50">{t.test}</button>
      </section>

      <section className="rounded-2xl border border-edge bg-card p-4">
        <h2 className="text-lg">{t.briefTitle}</h2>
        <p className="mt-1 text-xs text-muted">{t.briefHelp}</p>
        <div className="mt-3 flex flex-wrap items-end gap-2" dir="ltr" lang={lang}>
          <label className="flex flex-col text-xs text-muted" htmlFor={ids.hour}>
            {t.hour}
            <select id={ids.hour} className={field} value={hour12} onChange={(e) => setHour12(Number(e.target.value))}>
              {HOURS.map((h) => <option key={h} value={h}>{h}</option>)}
            </select>
          </label>
          <span className="pb-3">:</span>
          <label className="flex flex-col text-xs text-muted" htmlFor={ids.minute}>
            {t.minute}
            <select id={ids.minute} className={field} value={minute} onChange={(e) => setMinute(Number(e.target.value))}>
              {(MINUTES.includes(minute) ? MINUTES : [...MINUTES, minute].sort((a, b) => a - b)).map((m) => (
                <option key={m} value={m}>{String(m).padStart(2, "0")}</option>
              ))}
            </select>
          </label>
          <div className="flex gap-2" role="group" aria-label={`${t.am} / ${t.pm}`}>
            <button type="button" className={option(!pm)} aria-pressed={!pm} onClick={() => setPm(false)}>{t.am}</button>
            <button type="button" className={option(pm)} aria-pressed={pm} onClick={() => setPm(true)}>{t.pm}</button>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-edge bg-card p-4">
        <label className="text-lg" htmlFor={ids.cap}>{t.capTitle}</label>
        <input id={ids.cap} type="number" inputMode="numeric" min={CAP_MIN} max={CAP_MAX} step={1} value={cap}
          onChange={(e) => setCap(e.target.value)} aria-invalid={!capOk}
          className={`${field} mt-3 block w-28`} dir="ltr" />
        <p className="mt-2 text-xs text-muted">{t.capHelp}</p>
      </section>

      <button type="button" onClick={onSave} disabled={pending || !capOk}
        className="min-h-11 w-full rounded-xl bg-gold px-4 text-sm font-medium text-[#0E0E10] disabled:opacity-50">
        {pending ? t.saving : t.save}
      </button>
      {note && <p role="status" className="text-sm text-muted" data-testid="settings-note">{note}</p>}
    </div>
  );
}
