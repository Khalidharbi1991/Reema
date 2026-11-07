"use client";

import { useActionState } from "react";
import type { Messages } from "@/i18n/messages";
import type { SignInState } from "./actions";

type Props = {
  t: Messages["signIn"];
  action: (prev: SignInState, form: FormData) => Promise<SignInState>;
};

/** Email and password only. There is no sign-up link: Snafi is invite only. */
export function SignInForm({ t, action }: Props) {
  const [state, formAction, pending] = useActionState(action, { error: null });
  const errorText =
    state.error === "invalid" ? t.invalid
    : state.error === "missing" ? t.missing
    : state.error === "not_configured" ? t.notConfigured
    : state.error === "unavailable" ? t.unavailable
    : "";

  const field = "min-h-12 w-full rounded-xl border border-edge bg-bg px-4 text-base text-ink placeholder:text-muted focus:border-gold focus:outline-none";

  return (
    <form action={formAction} className="space-y-4" noValidate>
      <div>
        <label htmlFor="email" className="mb-1.5 block text-sm text-muted">{t.email}</label>
        <input id="email" name="email" type="email" autoComplete="username" inputMode="email" dir="ltr" required className={field} />
      </div>
      <div>
        <label htmlFor="password" className="mb-1.5 block text-sm text-muted">{t.password}</label>
        <input id="password" name="password" type="password" autoComplete="current-password" dir="ltr" required className={field} />
      </div>
      <p role="alert" aria-live="assertive" className="min-h-5 text-sm text-gold-ink">{errorText}</p>
      <button
        type="submit"
        disabled={pending}
        className="min-h-12 w-full rounded-xl bg-gold text-base font-medium text-[#0E0E10] transition-opacity disabled:opacity-60"
      >
        {pending ? t.submitting : t.submit}
      </button>
    </form>
  );
}
