"use client";

import { useEffect } from "react";
import { dayPartFor } from "@/core/preferences";

/** Sets body[data-daypart] from the phone's local time and refreshes it every 10 minutes. */
export function DayPartTone() {
  useEffect(() => {
    const apply = () => {
      document.body.dataset.daypart = dayPartFor(new Date().getHours());
    };
    apply();
    const timer = window.setInterval(apply, 10 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, []);
  return null;
}
