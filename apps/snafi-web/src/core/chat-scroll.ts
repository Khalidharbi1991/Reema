/** Chat's scroll rules (AC-20 to AC-24, AC-33), as pure functions so they can be tested without a layout. */

/** "At the bottom" means within this many pixels of the end of the list. */
export const NEAR_BOTTOM_PX = 80;

export type ScrollMetrics = { scrollTop: number; scrollHeight: number; clientHeight: number };

export function isAtBottom(m: ScrollMetrics): boolean {
  return m.scrollHeight - m.scrollTop - m.clientHeight <= NEAR_BOTTOM_PX;
}

/**
 * A new item arrived. At the bottom: follow it. Scrolled up: follow only Khalid's own message;
 * anything from Ahmad leaves the position alone (the jump button shows its "new" mark instead).
 */
export function onNewItem(state: { atBottom: boolean; mine: boolean }): "scroll" | "hold" {
  return state.atBottom || state.mine ? "scroll" : "hold";
}

/** Scrolling done by code is instant when "reduce motion" is on. */
export function scrollBehavior(reducedMotion: boolean): "auto" | "smooth" {
  return reducedMotion ? "auto" : "smooth";
}

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function scrollToEnd(el: HTMLElement, behavior: "auto" | "smooth"): void {
  if (typeof el.scrollTo === "function") el.scrollTo({ top: el.scrollHeight, behavior });
  else el.scrollTop = el.scrollHeight;
}
