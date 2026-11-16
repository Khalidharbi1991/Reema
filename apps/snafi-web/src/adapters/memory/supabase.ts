import "server-only";
import { createSupabaseServerClient } from "@/adapters/supabase/server-client";
import {
  checkDate, checkFact, checkMember, memoryId, MemoryError, toDate, toFact, toInterview, toMember,
  type DateInput, type FactInput, type MemberInput, type MemoryAdapter, type MemoryView,
} from "./types";

const MISSING_SCHEMA_CODES: readonly string[] = ["42703", "42883", "42P01", "PGRST204", "PGRST202", "PGRST205"];

function fail(error: { code?: string | null; message: string }): never {
  const missing = !!error.code && MISSING_SCHEMA_CODES.includes(error.code);
  const kind = error.code === "23505" ? "duplicate" : /passwords, ID or card/.test(error.message) ? "secret"
    : error.code === "22023" || error.code === "23514" ? "invalid" : "failed";
  throw new MemoryError(error.message, kind, missing);
}

/**
 * Supabase memory (migration 0010). Runs as the signed-in user with the publishable key: row-level
 * security shows only Khalid's own rows, and every change goes through a definer function that checks
 * the owner and the no-secrets rule again.
 */
export class SupabaseMemoryAdapter implements MemoryAdapter {
  private async client() {
    const client = await createSupabaseServerClient();
    if (!client) throw new MemoryError("Supabase is not configured");
    return client;
  }

  async load(): Promise<MemoryView> {
    const c = await this.client();
    const [facts, members, dates, interview] = await Promise.all([
      c.from("facts").select("id, body, section, source, created_at").is("deleted_at", null)
        .order("created_at", { ascending: true }).limit(500),
      c.from("family_members").select("id, name, relation, note").order("created_at", { ascending: true }).limit(100),
      c.from("family_dates").select("id, member_id, label, title, calendar, year, month, day")
        .order("month", { ascending: true }).order("day", { ascending: true }).limit(200),
      c.from("interview_state").select("status").maybeSingle(),
    ]);
    for (const r of [facts, members, dates, interview]) if (r.error) fail(r.error);
    return {
      facts: (facts.data ?? []).map(toFact),
      members: (members.data ?? []).map(toMember),
      dates: (dates.data ?? []).map(toDate),
      interview: toInterview(interview.data as { status?: unknown } | null),
    };
  }

  async saveFact(input: FactInput) {
    const v = checkFact(input);
    const { error } = await (await this.client()).rpc("save_fact", { p_id: v.id, p_section: v.section, p_body: v.body });
    if (error) fail(error);
  }

  async forgetFact(id: string) {
    const { error } = await (await this.client()).rpc("forget_fact", { p_id: memoryId(id) });
    if (error) fail(error);
  }

  async saveMember(input: MemberInput) {
    const v = checkMember(input);
    const { error } = await (await this.client()).rpc("save_family_member", {
      p_id: v.id, p_name: v.name, p_relation: v.relation, p_note: v.note,
    });
    if (error) fail(error);
  }

  async forgetMember(id: string) {
    const { error } = await (await this.client()).rpc("forget_family_member", { p_id: memoryId(id) });
    if (error) fail(error);
  }

  async saveDate(input: DateInput) {
    const v = checkDate(input);
    const { error } = await (await this.client()).rpc("save_family_date", {
      p_id: v.id, p_member_id: v.memberId, p_label: v.label, p_title: v.title, p_calendar: v.calendar,
      p_year: v.year, p_month: v.month, p_day: v.day,
    });
    if (error) fail(error);
  }

  async forgetDate(id: string) {
    const { error } = await (await this.client()).rpc("forget_family_date", { p_id: memoryId(id) });
    if (error) fail(error);
  }
}
