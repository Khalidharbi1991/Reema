import Link from "next/link";
import { Orb } from "@/components/Orb";
import { TopBar } from "@/components/TopBar";
import { isPreviewMode } from "@/config/env";
import { requestOrigin } from "@/core/request-origin";
import { getPreferences } from "@/core/server-preferences";
import { messages } from "@/i18n/messages";
import { signIn } from "./actions";
import { SignInForm } from "./SignInForm";

export default async function SignInPage() {
  const { theme, lang } = await getPreferences();
  const t = messages(lang);
  const preview = isPreviewMode();
  // SEC-10: decided here on the server, so the first HTML already has the form off over plain HTTP.
  const { secure } = await requestOrigin();
  return (
    <div className="shell" style={{ maxWidth: "28rem" }}>
      <a href="#content" className="skip-link">{t.skipToContent}</a>
      {/* Menu only: no bell and no wordmark in the bar on Sign-in. */}
      <TopBar
        screen="sign-in"
        theme={theme}
        lang={lang}
        labels={{ menu: t.menu, closeMenu: t.closeMenu, theme: t.theme, dark: t.dark, light: t.light, language: t.language, signOut: t.signOut }}
      />
      {/* Not centred vertically, so the form does not jump when the keyboard opens. */}
      <main id="content" className="shell-main gutter screen-in" style={{ paddingBlockStart: "clamp(24px, 8dvh, 72px)" }} data-screen="sign-in">
        <div className="mb-8 flex flex-col items-center text-center">
          <Orb label="" size={64} />
          <p className="t-wordmark mt-6" style={{ fontSize: "2rem" }}>{t.appName}</p>
          <h1 className="t-title mt-6">{t.signIn.title}</h1>
          <p className="t-small mt-1 text-muted">{t.signIn.subtitle}</p>
        </div>
        {preview ? (
          <div className="space-y-4">
            <p className="t-small wrap text-muted" data-testid="preview-banner">{t.previewBanner}</p>
            <Link href="/today" className="btn btn-primary btn-tall w-full">{t.previewOpen}</Link>
          </div>
        ) : (
          <SignInForm t={t.signIn} action={signIn} serverSecure={secure} />
        )}
        <p className="t-caption mt-6 text-center text-muted">{t.signIn.inviteOnly}</p>
      </main>
    </div>
  );
}
