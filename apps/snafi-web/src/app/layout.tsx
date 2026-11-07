import type { Metadata, Viewport } from "next";
import "@fontsource/cormorant-garamond/500.css";
import "@fontsource/cormorant-garamond/600.css";
import "@fontsource-variable/inter";
import "@fontsource/amiri/400.css";
import "@fontsource/amiri/700.css";
import "@fontsource/ibm-plex-sans-arabic/400.css";
import "@fontsource/ibm-plex-sans-arabic/500.css";
import "./globals.css";
import { getPreferences } from "@/core/server-preferences";
import { direction } from "@/i18n/messages";
import { DayPartTone } from "@/components/DayPartTone";
import { ServiceWorkerRegister } from "@/components/ServiceWorkerRegister";

export const metadata: Metadata = {
  title: "Snafi",
  description: "Snafi, Khalid's personal assistant.",
  applicationName: "Snafi",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Snafi", statusBarStyle: "black-translucent" },
  icons: {
    icon: [{ url: "/icons/icon.svg", type: "image/svg+xml" }],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180" }],
  },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0E0E10" },
    { media: "(prefers-color-scheme: light)", color: "#F7F3EC" },
  ],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const { theme, lang } = await getPreferences();
  return (
    <html lang={lang} dir={direction(lang)} data-theme={theme} suppressHydrationWarning>
      <body>
        <DayPartTone />
        <ServiceWorkerRegister />
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}
