/** Sign-in layer. Supabase today; swapping providers means a new file here, nothing else. */
export type AuthUser = { id: string; email: string | null };

export type SignInResult =
  | { ok: true; user: AuthUser }
  | { ok: false; error: "invalid" | "missing" | "unavailable" | "not_configured" };

export interface AuthAdapter {
  signInWithPassword(email: string, password: string): Promise<SignInResult>;
  signOut(): Promise<void>;
  /** The verified signed-in user, or null. */
  currentUser(): Promise<AuthUser | null>;
}
