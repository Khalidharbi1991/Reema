"use client";

import { useEffect } from "react";

/**
 * Registers /sw.js where the browser allows it (HTTPS or localhost). Over plain
 * Wi-Fi HTTP the phone skips this silently; installing waits for a Vercel preview.
 */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
      // Not fatal: the app works without it.
    });
  }, []);
  return null;
}
