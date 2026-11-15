/**
 * Live bug, Nov 15, 2026 (Android, installed app): On did nothing, and Save stayed on "Saving…" although
 * save_settings answered 200. Causes: every Settings button shared one useTransition, so a push step that
 * waited (the permission prompt, or navigator.serviceWorker.ready when no worker is active) kept Save
 * "pending" forever; those steps had no time limit; and every message was shown at the bottom of the page.
 */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_SETTINGS } from "@/adapters/mailbox/types";
import { SettingsForm } from "@/app/(app)/settings/SettingsForm";
import { enablePush, PushStepError, type PushEnv } from "@/core/push-client";
import { messages } from "@/i18n/messages";

const KEY = "B" + "A".repeat(86);
const FAST = { permission: 30, worker: 30, subscribe: 30, server: 30 };
const never = <T,>() => new Promise<T>(() => {});
const t = messages("en").settings;

function fakeEnv(opts: { permission?: () => Promise<NotificationPermission>; registration?: "active" | "none" | "never-ready";
  subscribe?: () => Promise<unknown> } = {}) {
  const sub = { endpoint: "https://fcm.googleapis.com/fcm/send/abc:def",
    toJSON: () => ({ keys: { p256dh: "B".repeat(87), auth: "C".repeat(22) } }), unsubscribe: vi.fn(async () => true) };
  const pushManager = { getSubscription: vi.fn(async () => null), subscribe: vi.fn(opts.subscribe ?? (async () => sub)) };
  const active = { active: {}, pushManager };
  const register = vi.fn(async () => (opts.registration === "never-ready" ? { active: null, pushManager } : active));
  const env = {
    supported: true,
    requestPermission: opts.permission ?? (async () => "granted" as NotificationPermission),
    serviceWorker: {
      getRegistration: vi.fn(async () => (opts.registration === "active" || !opts.registration ? active : undefined)),
      register,
      ready: opts.registration === "never-ready" ? never() : Promise.resolve(active),
    },
  } as unknown as PushEnv;
  return { env, sub, pushManager, register };
}

describe("enablePush: every step has a time limit and names itself", () => {
  it("a permission prompt that never answers fails at 'permission'", async () => {
    await expect(enablePush(KEY, async () => ({ ok: true }), fakeEnv({ permission: never }).env, FAST))
      .rejects.toMatchObject({ step: "permission", detail: "timed out" });
  });

  it("a blocked permission says so", async () => {
    await expect(enablePush(KEY, async () => ({ ok: true }), fakeEnv({ permission: async () => "denied" }).env, FAST))
      .rejects.toMatchObject({ step: "permission", detail: "denied" });
  });

  it("with no service worker it registers /sw.js itself, and a worker that never starts fails at 'worker'", async () => {
    const f = fakeEnv({ registration: "never-ready" });
    await expect(enablePush(KEY, async () => ({ ok: true }), f.env, FAST)).rejects.toMatchObject({ step: "worker" });
    expect(f.register).toHaveBeenCalledWith("/sw.js", { scope: "/" });
  });

  it("a push service that never answers fails at 'subscribe'; a thrown error keeps only its name", async () => {
    await expect(enablePush(KEY, async () => ({ ok: true }), fakeEnv({ subscribe: never }).env, FAST))
      .rejects.toMatchObject({ step: "subscribe", detail: "timed out" });
    const abort = Object.assign(new Error("push service error: secret detail"), { name: "AbortError" });
    await expect(enablePush(KEY, async () => ({ ok: true }), fakeEnv({ subscribe: async () => { throw abort; } }).env, FAST))
      .rejects.toMatchObject({ step: "subscribe", detail: "AbortError" });
  });

  it("saves the phone's address, or unsubscribes again when the server refuses it", async () => {
    const save = vi.fn(async () => ({ ok: true }));
    const ok = fakeEnv();
    await enablePush(KEY, save, ok.env, FAST);
    expect(save).toHaveBeenCalledWith({ endpoint: ok.sub.endpoint, p256dh: "B".repeat(87), auth: "C".repeat(22) });
    const refused = fakeEnv();
    await expect(enablePush(KEY, async () => ({ ok: false }), refused.env, FAST)).rejects.toBeInstanceOf(PushStepError);
    expect(refused.sub.unsubscribe).toHaveBeenCalled();
  });
});

describe("Settings screen after the fix", () => {
  const ok = async () => ({ ok: true });

  it("Save finishes and says so even while On is still waiting for the phone (bug 2)", async () => {
    const save = vi.fn(ok);
    const { env } = fakeEnv({ permission: never });
    render(<SettingsForm initial={DEFAULT_SETTINGS} lang="en" t={t} publicKey={KEY} save={save} subscribe={ok}
      unsubscribe={ok} test={ok} env={() => env} />);
    fireEvent.click(screen.getByRole("button", { name: "On" }));
    expect(await screen.findByRole("button", { name: "Working…" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
    expect(save).toHaveBeenCalledTimes(1);
  });

  it("a blocked permission is shown right under On, with how to allow it (bug 1)", async () => {
    const { env } = fakeEnv({ permission: async () => "denied" });
    render(<SettingsForm initial={DEFAULT_SETTINGS} lang="en" t={t} publicKey={KEY} save={ok} subscribe={ok}
      unsubscribe={ok} test={ok} env={() => env} />);
    fireEvent.click(screen.getByRole("button", { name: "On" }));
    const note = await screen.findByTestId("settings-note-push");
    expect(note).toHaveAttribute("role", "alert");
    expect(note).toHaveTextContent("App info → Notifications → Allow");
    expect(screen.getByRole("button", { name: "On" })).toBeEnabled();     // never stuck
  });

  it("a step that fails is named on screen, and On is usable again", async () => {
    const { env } = fakeEnv({ subscribe: async () => { throw Object.assign(new Error("x"), { name: "NotAllowedError" }); } });
    render(<SettingsForm initial={DEFAULT_SETTINGS} lang="en" t={t} publicKey={KEY} save={ok} subscribe={ok}
      unsubscribe={ok} test={ok} env={() => env} />);
    fireEvent.click(screen.getByRole("button", { name: "On" }));
    expect(await screen.findByTestId("settings-note-push"))
      .toHaveTextContent("Couldn't turn notifications on: the phone's push service didn't answer. Try again. (NotAllowedError)");
    expect(screen.getByRole("button", { name: "On" })).toBeEnabled();
  });

  it("turning on works end to end and saves push on", async () => {
    const save = vi.fn(ok);
    const subscribe = vi.fn(ok);
    const { env } = fakeEnv();
    render(<SettingsForm initial={DEFAULT_SETTINGS} lang="en" t={t} publicKey={KEY} save={save} subscribe={subscribe}
      unsubscribe={ok} test={ok} env={() => env} />);
    fireEvent.click(screen.getByRole("button", { name: "On" }));
    expect(await screen.findByText(/Notifications are on for this phone/)).toBeInTheDocument();
    expect(subscribe).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith({ pushEnabled: true, briefTime: "07:00", dailyCap: 10 });
    expect(screen.getByRole("button", { name: "On" })).toHaveAttribute("aria-pressed", "true");
  });

  it("a failed or rejected save is shown, and the button comes back", async () => {
    for (const save of [async () => ({ ok: false }), async () => { throw new Error("network"); }]) {
      const { unmount } = render(<SettingsForm initial={DEFAULT_SETTINGS} lang="en" t={t} publicKey={null} save={save}
        subscribe={ok} unsubscribe={ok} test={ok} env={() => null} />);
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
      expect(await screen.findByTestId("settings-note-save")).toHaveTextContent("Couldn't save. Try again.");
      expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
      unmount();
    }
  });

  it("a save that never answers stops after its time limit", async () => {
    vi.useFakeTimers();
    try {
      render(<SettingsForm initial={DEFAULT_SETTINGS} lang="en" t={t} publicKey={null} save={never}
        subscribe={ok} unsubscribe={ok} test={ok} env={() => null} />);
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
      expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
      await act(async () => { await vi.advanceTimersByTimeAsync(21_000); });
      expect(screen.getByTestId("settings-note-save")).toHaveTextContent("Couldn't save. Try again.");
      expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
    } finally {
      vi.useRealTimers();
    }
  });
});
