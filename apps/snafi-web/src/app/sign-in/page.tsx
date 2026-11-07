import Link from "next/link";
import { Orb } from "@/components/Orb";
import { TopBar } from "@/components/TopBar";
import { isPreviewMode } from "@/config/env";
import { getPreferences } from "@/core/server-preferences";
import { messages } from "@/i18n/messages";
import { signIn } from "./actions";
import { SignInForm } from "./SignInForm";

export default async function SignInPage() {
  const { theme, lang } = await getPreferences();
  const t = messages(lang);
  const preview = isPreviewMode();
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col">
      <TopBar
        appName=""
        theme={theme}
        lang={lang}
        labels={{ menu: t.menu, closeMenu: t.closeMenu, theme: t.theme, dark: t.dark, light: t.light, language: t.language, signOut: t.signOut }}
      />
      <main className="screen-in flex flex-1 flex-col justify-center px-6 pb-16">
        <div className="rise-in mb-10 flex flex-col items-center text-center">
          <Orb label="" size={72} />
          <p className="mt-6 font-heading text-4xl tracking-[0.1em] text-gold-ink">{t.appName}</p>
          <h1 className="mt-6 text-2xl">{t.signIn.title}</h1>
          <p className="mt-1 text-sm text-muted">{t.signIn.subtitle}</p>
        </div>
        <div className="rise-in rounded-2xl border border-edge bg-card p-6" style={{ ["--i" as string]: 1 }}>
          {preview ? (
            <div className="space-y-4 text-sm">
              <p className="text-muted" data-testid="preview-banner">{t.previewBanner}</p>
              <Link href="/today" className="flex min-h-12 items-center justify-center rounded-xl bg-gold font-medium text-[#0E0E10]">
                {t.previewOpen}
              </Link>
            </div>
          ) : (
            <SignInForm t={t.signIn} action={signIn} />
          )}
        </div>
        <p className="mt-6 text-center text-xs text-muted">{t.signIn.inviteOnly}</p>
      </main>
    </div>
  );
}
