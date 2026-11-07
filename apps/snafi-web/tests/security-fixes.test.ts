// @vitest-environment node
/** SEC-1, SEC-2 and SEC-5 from the step 1 security review. */
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { isLocalHost, isSecureRequest, sessionCookieOptions } from "@/adapters/supabase/cookie-policy";

const appDir = fileURLToPath(new URL("..", import.meta.url));
const read = (p: string) => readFileSync(fileURLToPath(new URL(`../${p}`, import.meta.url)), "utf8");

describe("SEC-1: dev server on this PC only by default", () => {
  const scripts = JSON.parse(read("package.json")).scripts as Record<string, string>;

  it("binds dev and start to 127.0.0.1", () => {
    expect(scripts.dev).toContain("--hostname 127.0.0.1");
    expect(scripts.start).toContain("--hostname 127.0.0.1");
  });

  it("keeps Wi-Fi as a separate opt-in script", () => {
    expect(scripts["dev:lan"]).toContain("--hostname 0.0.0.0");
    const others = Object.entries(scripts).filter(([name]) => name !== "dev:lan");
    expect(others.some(([, cmd]) => cmd.includes("0.0.0.0"))).toBe(false);
  });

  it("warns in the README against real sign-in over plain HTTP", () => {
    expect(read("README.md")).toMatch(/Never sign in with the real account over plain HTTP/);
  });
});

describe("SEC-2: session cookies", () => {
  it("are HttpOnly and SameSite=Lax everywhere", () => {
    for (const host of ["localhost:3000", "snafi.vercel.app", "192.168.1.113:3000", null]) {
      const o = sessionCookieOptions(host);
      expect(o.httpOnly).toBe(true);
      expect(o.sameSite).toBe("lax");
      expect(o.path).toBe("/");
    }
  });

  it("are Secure except on localhost", () => {
    expect(sessionCookieOptions("localhost:3000").secure).toBe(false);
    expect(sessionCookieOptions("127.0.0.1:3000").secure).toBe(false);
    expect(sessionCookieOptions("[::1]:3000").secure).toBe(false);
    expect(sessionCookieOptions("snafi.vercel.app").secure).toBe(true);
    expect(sessionCookieOptions("192.168.1.113:3000").secure).toBe(true);
    expect(sessionCookieOptions("localhost.evil.example").secure).toBe(true);
    expect(sessionCookieOptions(null).secure).toBe(true);
  });

  it("allows sign-in only over HTTPS or on localhost", () => {
    expect(isSecureRequest("snafi.vercel.app", "https")).toBe(true);
    expect(isSecureRequest("localhost:3000", null)).toBe(true);
    expect(isSecureRequest("192.168.1.113:3000", "http")).toBe(false);
    expect(isSecureRequest("192.168.1.113:3000", null)).toBe(false);
    expect(isSecureRequest("snafi.vercel.app", "https, http")).toBe(true);
    expect(isLocalHost("LOCALHOST")).toBe(true);
    expect(isLocalHost("127.0.0.2")).toBe(false);
  });

  it("is passed to both Supabase clients", () => {
    expect(read("src/adapters/supabase/server-client.ts")).toMatch(/cookieOptions: sessionCookieOptions\(host\)/);
    expect(read("src/adapters/supabase/proxy-session.ts")).toMatch(/cookieOptions: sessionCookieOptions\(host\)/);
    expect(read("src/adapters/auth/supabase.ts")).toMatch(/\.secure\) return \{ ok: false, error: "insecure" \}/);
  });
});

describe("SEC-5: env files stay out of Git", () => {
  it("ignores every env file except .env.example", () => {
    const check = (path: string) => {
      try {
        execFileSync("git", ["check-ignore", "-q", "--no-index", path], { cwd: appDir });
        return true;
      } catch {
        return false;
      }
    };
    for (const path of [".env", ".env.local", ".env.development", ".env.production", ".env.test", ".env.production.local"]) {
      expect(check(path), path).toBe(true);
    }
    expect(check(".env.example")).toBe(false);
  });
});
