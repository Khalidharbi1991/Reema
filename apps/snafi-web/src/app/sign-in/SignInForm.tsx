"use client";

import { useActionState, useSyncExternalStore } from "react";
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

  const field = "min-h-12 w-full rounded-xl border border-edge bg-bg px-4 text-base text-ink placeholder:text-muted focus:border-gold focus:outline-none disabled:opacity-50";

  return (
    <form action={formAction} className="space-y-4" noValidate>
      <fieldset disabled={!secure} className="space-y-4">
        <div>
          <label htmlFor="email" className="mb-1.5 block text-sm text-muted">{t.email}</label>
          <input id="email" name="email" type="email" autoComplete="username" inputMode="email" dir="ltr" required className={field} />
        </div>
        <div>
          <label htmlFor="password" className="mb-1.5 block text-sm text-muted">{t.password}</label>
          <input id="password" name="password" type="password" autoComplete="current-password" dir="ltr" required className={field} />
        </div>
      </fieldset>
      <p role="alert" aria-live="assertive" className="min-h-5 text-sm text-gold-ink">{errorText}</p>
      <button
        type="submit"
        disabled={pending || !secure}
        className="min-h-12 w-full rounded-xl bg-gold text-base font-medium text-[#0E0E10] transition-opacity disabled:opacity-60"
      >
        {pending ? t.submitting : t.submit}
      </button>
    </form>
  );
}
