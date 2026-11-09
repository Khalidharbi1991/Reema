"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Re-reads the page from the server every few seconds while it is on screen. */
export function AutoRefresh({ seconds }: { seconds: number }) {
  const router = useRouter();
  useEffect(() => {
    const tick = () => {
      if (document.visibilityState === "visible") router.refresh();
    };
    const timer = window.setInterval(tick, seconds * 1000);
    return () => window.clearInterval(timer);
  }, [router, seconds]);
  return null;
}
