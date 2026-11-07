import type { AuthAdapter, AuthUser, SignInResult } from "./types";
import { cleanCredentials } from "./validate";

/** In-memory stand-in for tests. Holds one account; no sign-up. */
export class FakeAuthAdapter implements AuthAdapter {
  private user: AuthUser | null = null;
  constructor(private readonly account: { id: string; email: string; password: string }) {}

  async signInWithPassword(email: string, password: string): Promise<SignInResult> {
    const creds = cleanCredentials(email, password);
    if (!creds) return { ok: false, error: "missing" };
    if (creds.email !== this.account.email.toLowerCase() || creds.password !== this.account.password) {
      return { ok: false, error: "invalid" };
    }
    this.user = { id: this.account.id, email: this.account.email };
    return { ok: true, user: this.user };
  }

  async signOut() {
    this.user = null;
  }

  async currentUser() {
    return this.user;
  }
}
