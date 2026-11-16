"use server";

import { revalidatePath } from "next/cache";
import { memoryAdapter } from "@/adapters";
import { MemoryError, type DateInput, type FactInput, type MemberInput } from "@/adapters/memory/types";
import { messages } from "@/i18n/messages";
import { getPreferences } from "@/core/server-preferences";
import { conversationId, mailboxFor, requireSession } from "@/core/session";

/** What the About me page gets back: ok, or which message to show. Never throws into the page. */
export type MemoryResult = { ok: true } | { ok: false; error: "secret" | "invalid" | "duplicate" | "failed" | "notReady" };

async function run(work: (userId: string | null) => Promise<void>): Promise<MemoryResult> {
  const session = await requireSession();
  try {
    await work(session.userId);
  } catch (error) {
    if (error instanceof MemoryError) {
      return { ok: false, error: error.schemaMissing ? "notReady" : error.kind };
    }
    return { ok: false, error: "failed" };
  }
  revalidatePath("/about");
  return { ok: true };
}

const fromForm = {
  fact: (v: FactInput): FactInput => ({ id: v?.id ?? null, section: v?.section, body: String(v?.body ?? "") }),
  member: (v: MemberInput): MemberInput => ({
    id: v?.id ?? null, name: String(v?.name ?? ""), relation: v?.relation, note: String(v?.note ?? ""),
  }),
  date: (v: DateInput): DateInput => ({
    id: v?.id ?? null, memberId: String(v?.memberId ?? ""), label: v?.label, title: String(v?.title ?? ""),
    calendar: v?.calendar, year: v?.year === null || v?.year === undefined ? null : Number(v.year),
    month: Number(v?.month), day: Number(v?.day),
  }),
};

export async function saveFact(input: FactInput) {
  return run((u) => memoryAdapter(u).saveFact(fromForm.fact(input)));
}
export async function forgetFact(id: string) {
  return run((u) => memoryAdapter(u).forgetFact(String(id ?? "")));
}
export async function saveMember(input: MemberInput) {
  return run((u) => memoryAdapter(u).saveMember(fromForm.member(input)));
}
export async function forgetMember(id: string) {
  return run((u) => memoryAdapter(u).forgetMember(String(id ?? "")));
}
export async function saveDate(input: DateInput) {
  return run((u) => memoryAdapter(u).saveDate(fromForm.date(input)));
}
export async function forgetDate(id: string) {
  return run((u) => memoryAdapter(u).forgetDate(String(id ?? "")));
}

/**
 * "Interview me again": sends Khalid's own words for it to Ahmad in Chat, in the app's language, exactly
 * as if he typed them; the worker matches them in code and starts the interview (no new database right).
 */
export async function startInterview(): Promise<{ ok: boolean }> {
  const session = await requireSession();
  const { lang } = await getPreferences();
  try {
    await mailboxFor(session).sendChat({
      conversationId: conversationId(session), body: messages(lang).about.interviewPhrase, lang,
    });
  } catch {
    return { ok: false };
  }
  revalidatePath("/chat");
  return { ok: true };
}
