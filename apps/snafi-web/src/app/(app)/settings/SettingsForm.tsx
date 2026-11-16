"use client";

import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";
import { CAP_MAX, CAP_MIN, type Settings } from "@/adapters/mailbox/types";
import { joinHHMM, splitHHMM } from "@/core/clock";
import {
  browserEnv, deviceSubscribed, disablePush, enablePush, PushStepError, within, type PushEnv, type PushStep,
} from "@/core/push-client";
import { AttentionIcon } from "@/components/Icons";
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
  const [confirmAll, setConfirmAll] = useState(false);
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

  /** SEC-153 (Khalid): Off removes only the phone he is holding; the account setting and other phones stay. */
  const turnOff = () => job("push", async () => {
    setConfirmAll(false);
    let removed = false;
    try {
      removed = await disablePush(unsubscribe, env());
    } catch (error) {
      const e = error instanceof PushStepError ? error : new PushStepError("server", "error");
      const detail = e.detail ? ` (${e.detail})` : "";
      if (e.step === "server") {
        // Only the server step runs inside disablePush's finally, so only then is the phone already cancelled.
        setDevice(false);
        return setNote({ where: "push", error: true, text: t.offThisFailed.replace("{step}", stepText[e.step]) + detail });
      }
      // SEC-163: an earlier step failed, so nothing was cancelled; the phone's state is left as it was.
      return setNote({ where: "push", error: true, text: t.offThisCouldNot.replace("{step}", stepText[e.step]) + detail });
    }
    setDevice(false);
    setNote({ where: "push", text: removed ? t.offThisDone : t.offThisNone, error: false });
  });

  /** "Turn off on all phones": only after the confirm step. Switches the account setting off. */
  const turnOffAll = () => job("push", async () => {
    setConfirmAll(false);
    wanted.current = false;
    try {
      await disablePush(unsubscribe, env());
    } catch {
      // The account switch below still stops every push to every phone.
    }
    setDevice(false);
    const ok = await saveValues(false);
    if (ok) setPush(false);
    else wanted.current = push;  // SEC-168: a later Save keeps what the account really has
    setNote({ where: "push", text: ok ? t.offAllDone : t.saveFailed, error: !ok });
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

  // Options show "selected" from aria-pressed; fields are 16px so an iPhone does not zoom on focus.
  const option = "option";
  const field = "field";
  const heading = "t-heading mt-8 mb-3";
  const help = "t-small wrap text-muted";
  const shown = (where: "push" | "save") => note && note.where === where && (
    <p role={note.error ? "alert" : "status"} data-testid={`settings-note-${where}`}
      className={`note mt-3 ${note.error ? "note-danger" : ""}`}>
      {note.error && <AttentionIcon />}
      <span className="wrap">{note.text}</span>
    </p>
  );

  return (
    <div data-testid="settings-form">
      <section>
        <h2 className={heading}>{t.pushTitle}</h2>
        <div className="flex gap-2" role="group" aria-label={t.pushTitle}>
          <button type="button" className={option} aria-pressed={thisPhoneOn} disabled={busy.push} onClick={turnOn}>
            {busy.push && !thisPhoneOn ? t.working : t.pushOn}
          </button>
          <button type="button" className={option} aria-pressed={!thisPhoneOn} disabled={busy.push} onClick={turnOff}>
            {busy.push && thisPhoneOn ? t.working : t.pushOff}
          </button>
        </div>
        {shown("push")}
        {push && device === false && !note && (
          <p role="status" data-testid="push-other-phone"
            className="note note-attention mt-3"><AttentionIcon /><span className="wrap">{t.pushOtherPhone}</span></p>
        )}
        <p className={`${help} mt-3`}>{t.pushHelp}</p>
        {!publicKey && <p className="t-small wrap mt-2 text-gold-ink" data-testid="push-not-set-up">{t.pushNotSetUp}</p>}
        {publicKey && !supported && <p className="t-small wrap mt-2 text-gold-ink">{t.pushUnsupported}</p>}
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" onClick={onTest} disabled={busy.test || busy.push || !push}
            className="btn btn-secondary">
            {busy.test ? t.working : t.test}
          </button>
          {push && !confirmAll && (
            <button type="button" onClick={() => { setNote(null); setConfirmAll(true); }} disabled={busy.push}
              data-testid="off-all" className="btn btn-secondary">
              {t.offAll}
            </button>
          )}
        </div>
        {confirmAll && (
          <div role="alertdialog" aria-label={t.offAll} data-testid="off-all-confirm"
            className="mt-3 min-w-0 rounded-xl border border-gold-ink px-3 py-3">
            <p className="t-small wrap text-gold-ink">{t.offAllConfirm}</p>
            <div className="mt-3 flex gap-2">
              <button type="button" onClick={turnOffAll} disabled={busy.push}
                className="btn btn-secondary flex-1 border-gold-ink text-gold-ink">
                {t.offAllYes}
              </button>
              <button type="button" onClick={() => setConfirmAll(false)} disabled={busy.push}
                className="btn btn-secondary flex-1">
                {t.cancel}
              </button>
            </div>
          </div>
        )}
      </section>

      <section>
        <h2 className={heading}>{t.briefTitle}</h2>
        <p className={help}>{t.briefHelp}</p>
        <div className="mt-3 flex flex-wrap items-end gap-2" dir="ltr" lang={lang}>
          <label className="t-small flex flex-col text-muted" htmlFor={ids.hour}>
            {t.hour}
            <select id={ids.hour} className={field} value={hour12} onChange={(e) => setHour12(Number(e.target.value))}>
              {HOURS.map((h) => <option key={h} value={h}>{h}</option>)}
            </select>
          </label>
          <span className="pb-3">:</span>
          <label className="t-small flex flex-col text-muted" htmlFor={ids.minute}>
            {t.minute}
            <select id={ids.minute} className={field} value={minute} onChange={(e) => setMinute(Number(e.target.value))}>
              {(MINUTES.includes(minute) ? MINUTES : [...MINUTES, minute].sort((a, b) => a - b)).map((m) => (
                <option key={m} value={m}>{String(m).padStart(2, "0")}</option>
              ))}
            </select>
          </label>
          <div className="flex min-w-32 flex-1 gap-2" role="group" aria-label={`${t.am} / ${t.pm}`}>
            <button type="button" className={option} aria-pressed={!pm} onClick={() => setPm(false)}>{t.am}</button>
            <button type="button" className={option} aria-pressed={pm} onClick={() => setPm(true)}>{t.pm}</button>
          </div>
        </div>
      </section>

      <section>
        <label className="t-heading mt-8 block" htmlFor={ids.cap}>{t.capTitle}</label>
        <input id={ids.cap} type="number" inputMode="numeric" min={CAP_MIN} max={CAP_MAX} step={1} value={cap}
          onChange={(e) => setCap(e.target.value)} aria-invalid={!capOk}
          className={`${field} mt-3 block w-28`} dir="ltr" />
        <p className={`${help} mt-2`}>{t.capHelp}</p>
      </section>

      <div className="mt-8">
        <button type="button" onClick={onSave} disabled={busy.save || !capOk} aria-busy={busy.save}
          className="btn btn-primary w-full">
          {busy.save ? t.saving : t.save}
        </button>
        {shown("save")}
      </div>
    </div>
  );
}
