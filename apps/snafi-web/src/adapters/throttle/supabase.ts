import "server-only";
import { createSupabaseServerClient } from "@/adapters/supabase/server-client";
import { checkKeys, ThrottleError, type ThrottleAdapter } from "./types";

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

  async waitSeconds(keys: string[]) {
    const { data, error } = await (await this.client()).rpc("signin_wait_seconds", { p_keys: checkKeys(keys) });
    if (error) throw new ThrottleError(error.message);
    const wait = Number(data);
    if (!Number.isFinite(wait) || wait < 0) throw new ThrottleError("unexpected throttle answer");
    return wait;
  }

  async recordFailure(keys: string[]) {
    const { error } = await (await this.client()).rpc("signin_record_failure", { p_keys: checkKeys(keys) });
    if (error) throw new ThrottleError(error.message);
  }
}
