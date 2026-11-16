/**
 * What Ahmad knows about Khalid (Snafi step 6), for the About me page. Supabase today (migration 0010);
 * an in-memory stand-in for tests and preview. The app reads its own rows and changes them only through
 * the database's save_* and forget_* functions; Forget really deletes.
 */
import { memoryRefusal } from "@/core/memory-guard";

export const SECTIONS = ["me", "family", "preferences", "routine"] as const;
export type Section = (typeof SECTIONS)[number];
export const RELATIONS = ["wife", "husband", "daughter", "son", "mother", "father", "sister", "brother", "other"] as const;
export type Relation = (typeof RELATIONS)[number];
export const LABELS = ["birthday", "anniversary", "other"] as const;
export type DateLabel = (typeof LABELS)[number];
export type Calendar = "gregorian" | "hijri";

export type Fact = { id: string; body: string; section: Section; source: "told" | "interview" | "learned"; createdAt: string };
export type FamilyMember = { id: string; name: string; relation: Relation; note: string };
export type FamilyDate = {
  id: string; memberId: string; label: DateLabel; title: string; calendar: Calendar;
  year: number | null; month: number; day: number;
};
export type InterviewStatus = "none" | "invited" | "active" | "paused" | "done";
export type MemoryView = { facts: Fact[]; members: FamilyMember[]; dates: FamilyDate[]; interview: InterviewStatus };

export type FactInput = { id: string | null; section: Section; body: string };
export type MemberInput = { id: string | null; name: string; relation: Relation; note: string };
export type DateInput = {
  id: string | null; memberId: string; label: DateLabel; title: string; calendar: Calendar;
  year: number | null; month: number; day: number;
};

export const FACT_MAX = 500;
export const NAME_MAX = 80;
export const NOTE_MAX = 300;
export const TITLE_MAX = 80;

/** kind "secret": the no-secrets rule; "invalid": bad input; "duplicate": already saved. */
export class MemoryError extends Error {
  constructor(message: string, readonly kind: "secret" | "invalid" | "duplicate" | "failed" = "failed",
    readonly schemaMissing = false) {
    super(message);
  }
}

export interface MemoryAdapter {
  load(): Promise<MemoryView>;
  saveFact(input: FactInput): Promise<void>;
  forgetFact(id: string): Promise<void>;
  saveMember(input: MemberInput): Promise<void>;
  /** Their dates go with them. */
  forgetMember(id: string): Promise<void>;
  saveDate(input: DateInput): Promise<void>;
  forgetDate(id: string): Promise<void>;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function memoryId(id: unknown): string {
  if (typeof id !== "string" || !UUID.test(id)) throw new MemoryError("invalid id", "invalid");
  return id.toLowerCase();
}

function clean(text: unknown, max: number, required: boolean): string {
  const v = typeof text === "string" ? text.replace(/\s+/g, " ").trim() : "";
  if (required && !v) throw new MemoryError("empty", "invalid");
  if (v.length > max) throw new MemoryError("too long", "invalid");
  if (memoryRefusal(v)) throw new MemoryError("memory never keeps passwords, ID or card numbers", "secret");
  return v;
}

const DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

export function checkFact(f: FactInput): FactInput {
  if (!SECTIONS.includes(f.section)) throw new MemoryError("invalid section", "invalid");
  return { id: f.id === null ? null : memoryId(f.id), section: f.section, body: clean(f.body, FACT_MAX, true) };
}

export function checkMember(m: MemberInput): MemberInput {
  if (!RELATIONS.includes(m.relation)) throw new MemoryError("invalid relation", "invalid");
  return { id: m.id === null ? null : memoryId(m.id), name: clean(m.name, NAME_MAX, true), relation: m.relation,
    note: clean(m.note, NOTE_MAX, false) };
}

export function checkDate(d: DateInput): DateInput {
  if (!LABELS.includes(d.label) || (d.calendar !== "gregorian" && d.calendar !== "hijri")) {
    throw new MemoryError("invalid date", "invalid");
  }
  const whole = (n: unknown) => typeof n === "number" && Number.isInteger(n);
  if (!whole(d.month) || d.month < 1 || d.month > 12 || !whole(d.day) || d.day < 1) throw new MemoryError("invalid date", "invalid");
  const most = d.calendar === "hijri" ? 30 : DAYS[d.month - 1];
  if (d.day > most) throw new MemoryError("invalid date", "invalid");
  if (d.year !== null) {
    const [lo, hi] = d.calendar === "hijri" ? [1300, 1500] : [1900, 2100];
    if (!whole(d.year) || d.year < lo || d.year > hi) throw new MemoryError("invalid date", "invalid");
    if (d.calendar === "gregorian" && d.month === 2 && d.day === 29
      && !(d.year % 4 === 0 && (d.year % 100 !== 0 || d.year % 400 === 0))) throw new MemoryError("invalid date", "invalid");
  }
  const title = clean(d.title, TITLE_MAX, d.label === "other");
  return { ...d, id: d.id === null ? null : memoryId(d.id), memberId: memoryId(d.memberId), title };
}

const text = (v: unknown, max: number) => (typeof v === "string" ? v.slice(0, max) : "");
const int = (v: unknown) => (typeof v === "number" && Number.isInteger(v) ? v : null);

export function toFact(r: Record<string, unknown>): Fact {
  const section = SECTIONS.includes(r.section as Section) ? (r.section as Section) : "me";
  const source = r.source === "interview" || r.source === "learned" ? r.source : "told";
  return { id: text(r.id, 40), body: text(r.body, FACT_MAX), section, source, createdAt: text(r.created_at, 40) };
}
export function toMember(r: Record<string, unknown>): FamilyMember {
  const relation = RELATIONS.includes(r.relation as Relation) ? (r.relation as Relation) : "other";
  return { id: text(r.id, 40), name: text(r.name, NAME_MAX), relation, note: text(r.note, NOTE_MAX) };
}
export function toDate(r: Record<string, unknown>): FamilyDate {
  return {
    id: text(r.id, 40), memberId: text(r.member_id, 40),
    label: LABELS.includes(r.label as DateLabel) ? (r.label as DateLabel) : "other",
    title: text(r.title, TITLE_MAX), calendar: r.calendar === "hijri" ? "hijri" : "gregorian",
    year: int(r.year), month: int(r.month) ?? 1, day: int(r.day) ?? 1,
  };
}
export function toInterview(r: { status?: unknown } | null): InterviewStatus {
  const s = r?.status;
  return s === "invited" || s === "active" || s === "paused" || s === "done" ? s : "none";
}
