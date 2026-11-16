"use client";

import { useActionState, useSyncExternalStore } from "react";
import { AttentionIcon } from "@/components/Icons";
import type { Messages } from "@/i18n/messages";
import type { SignInState } from "./actions";

type Props = {
  t: Messages["signIn"];
  action: (prev: SignInState, form: FormData) => Promise<SignInState>;
  /** The server's decision (HTTPS or localhost). False means the form starts switched off. */
  serverSecure: boolean;
};

const noSubscribe = () => () => {};

/**
 * Email and password only. There is no sign-up link: Snafi is invite only.
 * Over plain HTTP (not localhost) the form is switched off, so the password is
 * never typed or sent unencrypted (SEC-1). The server decides first (SEC-10), so
 * the form is off even before JavaScript loads; the browser can only switch it
 * off further, never on. The server also refuses the attempt.
 */
export function SignInForm({ t, action, serverSecure }: Props) {
  const [state, formAction, pending] = useActionState(action, { error: null });
  const secure = useSyncExternalStore(
    noSubscribe,
    () => serverSecure && window.isSecureContext,
    () => serverSecure,
  );
  const error = secure ? state.error : "insecure";
  const errorText =
    error === "invalid" ? t.invalid
    : error === "missing" ? t.missing
    : error === "not_configured" ? t.notConfigured
    : error === "unavailable" ? t.unavailable
    : error === "throttled" ? t.throttled
    : error === "insecure" ? t.insecure
    : "";

  // 16px text (no zoom on focus on an iPhone) and the global focus ring.
  const field = "field w-full";

  return (
    <form action={formAction} className="space-y-4" noValidate>
      <fieldset disabled={!secure} className="space-y-4">
        <div>
          <label htmlFor="email" className="t-small mb-1.5 block text-muted">{t.email}</label>
          <input id="email" name="email" type="email" autoComplete="username" inputMode="email" dir="ltr" required className={field} />
        </div>
        <div>
          <label htmlFor="password" className="t-small mb-1.5 block text-muted">{t.password}</label>
          <input id="password" name="password" type="password" autoComplete="current-password" dir="ltr" required className={field} />
        </div>
      </fieldset>
      <p role="alert" aria-live="assertive" className="t-small with-icon min-h-5 text-danger">
        {errorText && <AttentionIcon />}<span className="wrap">{errorText}</span>
      </p>
      <button
        type="submit"
        disabled={pending || !secure}
        aria-busy={pending}
        className="btn btn-primary btn-tall w-full"
      >
        {pending ? t.submitting : t.submit}
      </button>
    </form>
  );
}
