/** SEC-10: the server decides, so the first HTML already has the form off over plain HTTP. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SignInForm } from "@/app/sign-in/SignInForm";
import { messages } from "@/i18n/messages";

const t = messages("en").signIn;
const action = async () => ({ error: null });
// Vitest runs from apps/snafi-web; jsdom cannot resolve import.meta.url to a file.
const read = (p: string) => readFileSync(resolve(process.cwd(), p), "utf8");

function setSecureContext(value: boolean) {
  Object.defineProperty(window, "isSecureContext", { value, configurable: true });
}

async function serverHtml(serverSecure: boolean): Promise<string> {
  // Untyped on purpose: react-dom ships no types here and none are installed.
  const specifier: string = "react-dom/server";
  const { renderToString } = await import(/* @vite-ignore */ specifier);
  return renderToString(<SignInForm t={t} action={action} serverSecure={serverSecure} />) as string;
}

afterEach(() => setSecureContext(true));

describe("SEC-10: sign-in form state decided on the server", () => {
  it("is switched off in the server's first HTML over plain HTTP", async () => {
    const html = await serverHtml(false);
    expect(html).toMatch(/<fieldset[^>]*\sdisabled=""/);
    expect(html).toMatch(/<button[^>]*type="submit"[^>]*\sdisabled=""/);
    expect(html).toContain("plain HTTP");
  });

  it("is switched on in the server's first HTML over HTTPS or localhost", async () => {
    const html = await serverHtml(true);
    expect(html).not.toMatch(/<fieldset[^>]*\sdisabled=""/);
    expect(html).not.toMatch(/<button[^>]*type="submit"[^>]*\sdisabled=""/);
  });

  it("stays off in the browser when the server said no, even in a secure context", () => {
    setSecureContext(true);
    render(<SignInForm t={t} action={action} serverSecure={false} />);
    expect(screen.getByLabelText("Password")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeDisabled();
  });

  it("can only be switched further off by the browser, never on", () => {
    setSecureContext(false);
    render(<SignInForm t={t} action={action} serverSecure={true} />);
    expect(screen.getByLabelText("Email")).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("plain HTTP");
  });

  it("is on when both server and browser agree", () => {
    setSecureContext(true);
    render(<SignInForm t={t} action={action} serverSecure={true} />);
    expect(screen.getByLabelText("Password")).toBeEnabled();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });

  it("is wired from the page's server-side check", () => {
    const page = read("src/app/sign-in/page.tsx");
    expect(page).toContain("await requestOrigin()");
    expect(page).toContain("serverSecure={secure}");
  });
});

describe("SEC-11: forwarded headers are marked as never for access decisions", () => {
  it("carries the warning where the headers are read", () => {
    for (const file of ["src/core/request-origin.ts", "src/adapters/supabase/proxy-session.ts"]) {
      const src = read(file);
      expect(src, file).toContain("SEC-11");
      expect(src, file).toMatch(/NEVER[^\n]*(throttle|redirect)/);
    }
  });
});
