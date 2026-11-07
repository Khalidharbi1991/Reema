/** Light vibration on tap where the phone supports it (Android). iPhone Safari has no vibration API. */
export function tapFeedback(nav: Pick<Navigator, "vibrate"> | undefined = typeof navigator === "undefined" ? undefined : navigator): boolean {
  if (!nav || typeof nav.vibrate !== "function") return false;
  try {
    return nav.vibrate(12);
  } catch {
    return false;
  }
}
