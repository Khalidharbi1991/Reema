"use client";

import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";
import { CAP_MAX, CAP_MIN, type Settings } from "@/adapters/mailbox/types";
import { joinHHMM, splitHHMM } from "@/core/clock";
import {
  browserEnv, deviceSubscribed, disablePush, enablePush, PushStepError, within, type PushEnv, type PushStep,
} from "@/core/push-client";
import type { Lang, Messages } from "@/i18n/messages";

export { toBase64Url } from "@/core/push-client";

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
  /** The browser's push objects; tests pass fakes. */
  env?: () => PushEnv | null;
};

type Job = "push" | "save" | "test";
type Note = { where: "push" | "save"; text: string; error: boolean } | null;

const HOURS = Array.from({ length: 12 }, (_, i) => i + 1);
const MINUTES = Array.from({ length: 12 }, (_, i) => i * 5);
const SAVE_LIMIT = 20_000;

const noSubscribe = () => () => undefined;

function pushSupported(): boolean {
  return browserEnv() !== null;
}

/**
 * The Settings screen. Push is asked for only when Khalid taps On (iPhone requires a tap, and only in
 * the installed app). The phone's push address goes to the database through save_push_subscription,
 * which accepts only the four browser push services.
 *
 * Live bug fix (Nov 15, 2026): each button has its own busy state, always cleared (finally), so a step
 * that waits (the permission prompt, the service worker) can never leave Save on "Saving…"; every step
 * has a time limit; and every outcome is shown right under the button that was tapped.
 */
export function SettingsForm({ initial, lang, t, publicKey, save, subscribe, unsubscribe, test, env = browserEnv }: Props) {
  const start = splitHHMM(initial.briefTime);
  const [push, setPush] = useState(initial.pushEnabled);
  // SEC-140: what Khalid last asked for (set the moment On or Off starts), so a Save tapped meanwhile
  // never sends the old value and switches push back.
  const wanted = useRef(initial.pushEnabled);
  const [hour12, setHour12] = useState(start.hour12);
  const [minute, setMinute] = useState(start.minute);
  const [pm, setPm] = useState(start.pm);
  const [cap, setCap] = useState(String(initial.dailyCap));
  const [note, setNote] = useState<Note>(null);
  // One flag per button: Save never waits on the push steps, and the push steps never wait on Save.
  const [busy, setBusy] = useState<Record<Job, boolean>>({ push: false, save: false, test: false });
  const ids = { hour: useId(), minute: useId(), cap: useId() };
  // Push is per PHONE, while push on/off is per account (live bug, Nov 15, 2026: after the iPhone turned
  // push on, Android showed On too, though Android itself was never signed up). null = not known yet.
  const [device, setDevice] = useState<boolean | null>(null);
  const envRef = useRef(env);
  useEffect(() => {
    let live = true;
    deviceSubscribed(envRef.current()).then((v) => { if (live) setDevice(v); });
    return () => { live = false; };
  }, []);
  const thisPhoneOn = push && device !== false;

  // Whether this browser can take push at all (server render: assume yes, to avoid a flash).
  const supported = useSyncExternalStore(noSubscribe, pushSupported, () => true);

  const capValue = Number.parseInt(cap, 10);
  const capOk = Number.isInteger(capValue) && capValue >= CAP_MIN && capValue <= CAP_MAX && /^\d+$/.test(cap.trim());
  const values = (pushEnabled = push) => ({ pushEnabled, briefTime: joinHHMM(hour12, minute, pm), dailyCap: capValue });

  const stepText: Record<PushStep, string> = {
    unsupported: t.stepUnsupported, permission: t.stepPermission, worker: t.stepWorker,
    subscribe: t.stepSubscribe, server: t.stepServer,
  };

  /** Runs one button's job; the busy flag is always cleared, whatever happens. */
  async function job(which: Job, work: () => Promise<void>) {
    if (busy[which]) return;
    setBusy((b) => ({ ...b, [which]: true }));
    setNote(null);
    try {
      await work();
    } finally {
      setBusy((b) => ({ ...b, [which]: false }));
    }
  }

  async function saveValues(pushEnabled: boolean): Promise<boolean> {
    try {
      return (await within(save(values(pushEnabled)), SAVE_LIMIT, "server")).ok;
    } catch {
      return false;
    }
  }

  const onSave = () => job("save", async () => {
    if (!capOk) return setNote({ where: "save", text: t.capInvalid, error: true });
    const ok = await saveValues(wanted.current);
    setNote({ where: "save", text: ok ? t.saved : t.saveFailed, error: !ok });
  });

  const turnOn = () => job("push", async () => {
    if (!publicKey) return setNote({ where: "push", text: t.pushNotSetUp, error: true });
    if (!capOk) return setNote({ where: "push", text: t.capInvalid, error: true });
    const before = wanted.current;
    wanted.current = true;
    try {
      await enablePush(publicKey, subscribe, env());
    } catch (error) {
      wanted.current = before;
      const e = error instanceof PushStepError ? error : new PushStepError("subscribe", "error");
      const text = e.step === "unsupported" ? t.pushUnsupported
        : e.step === "permission" && (e.detail === "denied" || e.detail === "default") ? t.pushDenied
        : t.pushFailedAt.replace("{step}", stepText[e.step]) + (e.detail ? ` (${e.detail})` : "");
      return setNote({ where: "push", text, error: true });
    }
    setDevice(true);
    const ok = await saveValues(true);
    setPush(true);
    setNote({ where: "push", text: ok ? t.pushReady : t.saveFailed, error: !ok });
  });

  const turnOff = () => job("push", async () => {
    wanted.current = false;
    try {
      await disablePush(unsubscribe, env());
    } catch {
      // The server switch below still stops every push to every phone.
    }
    setDevice(false);
    const ok = await saveValues(false);
    if (ok) setPush(false);
    setNote({ where: "push", text: ok ? t.saved : t.saveFailed, error: !ok });
  });

  const onTest = () => job("test", async () => {
    let ok = false;
    try {
      ok = (await within(test(), SAVE_LIMIT, "server")).ok;
    } catch {
      ok = false;
    }
    setNote({ where: "push", text: ok ? t.testSent : t.testFailed, error: !ok });
  });

  const option = (active: boolean) =>
    `min-h-11 flex-1 rounded-xl border px-3 text-sm transition-colors ${active ? "border-gold bg-gold/15 text-gold-ink" : "border-edge text-ink"}`;
  const field = "min-h-11 rounded-xl border border-edge bg-card px-3 text-sm text-ink";
  const shown = (where: "push" | "save") => note && note.where === where && (
    <p role={note.error ? "alert" : "status"} data-testid={`settings-note-${where}`}
      className={`mt-3 rounded-xl border px-3 py-2 text-sm ${note.error ? "border-gold/60 text-gold-ink" : "border-edge text-muted"}`}>
      {note.text}
    </p>
  );

  return (
    <div className="mt-6 space-y-6" data-testid="settings-form">
      <section className="rounded-2xl border border-edge bg-card p-4">
        <h2 className="text-lg">{t.pushTitle}</h2>
        <div className="mt-3 flex gap-2" role="group" aria-label={t.pushTitle}>
          <button type="button" className={option(thisPhoneOn)} aria-pressed={thisPhoneOn} disabled={busy.push} onClick={turnOn}>
            {busy.push && !thisPhoneOn ? t.working : t.pushOn}
          </button>
          <button type="button" className={option(!thisPhoneOn)} aria-pressed={!thisPhoneOn} disabled={busy.push} onClick={turnOff}>
            {busy.push && thisPhoneOn ? t.working : t.pushOff}
          </button>
        </div>
        {shown("push")}
        {push && device === false && !note && (
          <p role="status" data-testid="push-other-phone"
            className="mt-3 rounded-xl border border-gold/60 px-3 py-2 text-sm text-gold-ink">{t.pushOtherPhone}</p>
        )}
        <p className="mt-3 text-xs text-muted">{t.pushHelp}</p>
        {!publicKey && <p className="mt-2 text-xs text-gold-ink" data-testid="push-not-set-up">{t.pushNotSetUp}</p>}
        {publicKey && !supported && <p className="mt-2 text-xs text-gold-ink">{t.pushUnsupported}</p>}
        <button type="button" onClick={onTest} disabled={busy.test || busy.push || !push}
          className="mt-3 min-h-11 rounded-xl border border-edge px-4 text-sm disabled:opacity-50">
          {busy.test ? t.working : t.test}
        </button>
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

      <div>
        <button type="button" onClick={onSave} disabled={busy.save || !capOk}
          className="min-h-11 w-full rounded-xl bg-gold px-4 text-sm font-medium text-[#0E0E10] disabled:opacity-50">
          {busy.save ? t.saving : t.save}
        </button>
        {shown("save")}
      </div>
    </div>
  );
}
