/**
 * The phone's side of turning push on or off (Settings). Every step has a time limit and, when it
 * fails, says WHICH step failed, so the screen can tell Khalid instead of waiting forever (live bug,
 * Nov 15, 2026: On did nothing and Save stayed on "Saving…" on Android).
 *
 * Steps: permission (the phone's "Allow notifications?" prompt), worker (Snafi's service worker,
 * registered here if the page has none yet, then active), subscribe (the browser's push service),
 * server (the push address saved through save_push_subscription).
 */

export type PushStep = "unsupported" | "permission" | "worker" | "subscribe" | "server";

export class PushStepError extends Error {
  constructor(public readonly step: PushStep, public readonly detail: string = "") {
    super(`push step ${step} failed${detail ? `: ${detail}` : ""}`);
    this.name = "PushStepError";
  }
}

export const LIMITS = { permission: 120_000, worker: 15_000, subscribe: 30_000, server: 20_000 } as const;

/** Rejects with PushStepError(step, "timed out") if `promise` has not settled within `ms`. */
export function within<T>(promise: Promise<T>, ms: number, step: PushStep): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new PushStepError(step, "timed out")), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

/** The error's name (NotAllowedError, AbortError, InvalidStateError…), never its message text. */
function nameOf(error: unknown): string {
  if (error instanceof PushStepError) return error.detail;
  return error instanceof Error && /^[A-Za-z]{1,40}$/.test(error.name) ? error.name : "error";
}

async function step<T>(name: PushStep, ms: number, run: () => Promise<T>): Promise<T> {
  try {
    return await within(run(), ms, name);
  } catch (error) {
    throw error instanceof PushStepError ? error : new PushStepError(name, nameOf(error));
  }
}

/** The browser objects used, so tests can pass fakes. */
export type PushEnv = {
  serviceWorker: ServiceWorkerContainer;
  requestPermission: () => Promise<NotificationPermission>;
  supported: boolean;
};

export function browserEnv(): PushEnv | null {
  if (typeof window === "undefined" || !("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
    return null;
  }
  return { serviceWorker: navigator.serviceWorker, requestPermission: () => Notification.requestPermission(), supported: true };
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const b64 = base64url.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (base64url.length % 4)) % 4);
  const raw = atob(b64);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

/** base64url (no padding) of a key from PushSubscription.toJSON(), whatever form the browser gave. */
export function toBase64Url(value: string | undefined): string {
  return (value ?? "").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Snafi's registration, registering /sw.js now if this page has none, and waiting until it is active. */
async function activeRegistration(sw: ServiceWorkerContainer): Promise<ServiceWorkerRegistration> {
  const reg = (await sw.getRegistration("/")) ?? (await sw.register("/sw.js", { scope: "/" }));
  if (reg.active) return reg;
  const ready = await sw.ready;  // bounded by the step's time limit
  if (!ready.active) throw new PushStepError("worker", "not active");
  return ready;
}

export async function enablePush(
  publicKey: string,
  save: (k: { endpoint: string; p256dh: string; auth: string }) => Promise<{ ok: boolean }>,
  env: PushEnv | null = browserEnv(),
  limits: { [K in keyof typeof LIMITS]: number } = LIMITS,
): Promise<void> {
  if (!env?.supported) throw new PushStepError("unsupported");
  const permission = await step("permission", limits.permission, env.requestPermission);
  if (permission !== "granted") throw new PushStepError("permission", permission);
  const reg = await step("worker", limits.worker, () => activeRegistration(env.serviceWorker));
  const sub = await step("subscribe", limits.subscribe, async () =>
    (await reg.pushManager.getSubscription())
      ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) })));
  const json = sub.toJSON();
  const saved = await step("server", limits.server, () =>
    save({ endpoint: sub.endpoint, p256dh: toBase64Url(json.keys?.p256dh), auth: toBase64Url(json.keys?.auth) }));
  if (!saved.ok) {
    await sub.unsubscribe().catch(() => undefined);
    throw new PushStepError("server", "refused");
  }
}

/** Unsubscribes this phone (best effort) and tells the server; push_enabled is saved separately. */
export async function disablePush(
  remove: (endpoint: string) => Promise<{ ok: boolean }>,
  env: PushEnv | null = browserEnv(),
  limits: { [K in keyof typeof LIMITS]: number } = LIMITS,
): Promise<void> {
  if (!env?.supported) return;
  const reg = await step("worker", limits.worker, async () => (await env.serviceWorker.getRegistration("/")) ?? null);
  const sub = reg ? await step("subscribe", limits.subscribe, () => reg.pushManager.getSubscription()) : null;
  if (!sub) return;
  await step("server", limits.server, () => remove(sub.endpoint));
  await sub.unsubscribe().catch(() => undefined);
}
