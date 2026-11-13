import "server-only";
import { createSupabaseServerClient } from "@/adapters/supabase/server-client";
import { checkKeys, checkTicket, ThrottleError, type ThrottleAdapter } from "./types";

/**
 * The throttle in Supabase (migration 0005). The table is hidden; the app can only
 * call the two functions, with the publishable key, signed in or not.
 */
export class SupabaseThrottleAdapter implements ThrottleAdapter {
  private async client() {
    const client = await createSupabaseServerClient();
    if (!client) throw new ThrottleError("Supabase is not configured");
    return client;
  }

  async begin(keys: string[]) {
    const { data, error } = await (await this.client()).rpc("signin_begin", { p_keys: checkKeys(keys) });
    if (error) throw new ThrottleError(error.message);
    return checkTicket(data);
  }

  async forget(attempt: string) {
    const { error } = await (await this.client()).rpc("signin_forget", { p_attempt: attempt });
    if (error) throw new ThrottleError(error.message);
  }
}
