import {
  checkDate, checkFact, checkMember, memoryId, MemoryError,
  type DateInput, type FactInput, type FamilyDate, type FamilyMember, type Fact, type InterviewStatus,
  type MemberInput, type MemoryAdapter,
} from "./types";

type Owned<T> = T & { userId: string };
export type MemoryBookStore = {
  facts: Owned<Fact>[];
  members: Owned<FamilyMember>[];
  dates: Owned<FamilyDate>[];
  interview: Record<string, InterviewStatus>;
};

export function createMemoryBookStore(): MemoryBookStore {
  return { facts: [], members: [], dates: [], interview: {} };
}

/**
 * In-memory memory for tests and preview mode, mirroring migration 0010: a user sees and changes only
 * their own rows, a member's dates go with them, and Forget removes the row.
 */
export class InMemoryMemoryAdapter implements MemoryAdapter {
  constructor(private readonly store: MemoryBookStore, private readonly userId: string | null) {}

  private me(): string {
    if (!this.userId) throw new MemoryError("not signed in");
    return this.userId;
  }

  async load() {
    const me = this.me();
    const mine = <T extends { userId: string }>(rows: T[]) =>
      rows.filter((r) => r.userId === me).map((r) => {
        const copy: Partial<T> = { ...r };
        delete copy.userId;
        return copy;
      });
    return {
      facts: mine(this.store.facts) as Fact[],
      members: mine(this.store.members) as FamilyMember[],
      dates: (mine(this.store.dates) as FamilyDate[]).sort((a, b) => a.month - b.month || a.day - b.day),
      interview: this.store.interview[me] ?? "none",
    };
  }

  async saveFact(input: FactInput) {
    const me = this.me();
    const v = checkFact(input);
    if (v.id === null) {
      this.store.facts.push({ id: crypto.randomUUID(), body: v.body, section: v.section, source: "told",
        createdAt: new Date().toISOString(), userId: me });
      return;
    }
    const row = this.store.facts.find((f) => f.id === v.id && f.userId === me);
    if (!row) throw new MemoryError("no fact with that id", "invalid");
    Object.assign(row, { body: v.body, section: v.section });
  }

  async forgetFact(id: string) {
    const me = this.me();
    const fid = memoryId(id);
    this.store.facts = this.store.facts.filter((f) => !(f.id === fid && f.userId === me));
  }

  async saveMember(input: MemberInput) {
    const me = this.me();
    const v = checkMember(input);
    const clash = this.store.members.find((m) => m.userId === me && m.id !== v.id
      && m.name.trim().toLowerCase() === v.name.toLowerCase());
    if (clash) throw new MemoryError("a family member with that name is already saved", "duplicate");
    if (v.id === null) {
      this.store.members.push({ id: crypto.randomUUID(), name: v.name, relation: v.relation, note: v.note, userId: me });
      return;
    }
    const row = this.store.members.find((m) => m.id === v.id && m.userId === me);
    if (!row) throw new MemoryError("no family member with that id", "invalid");
    Object.assign(row, { name: v.name, relation: v.relation, note: v.note });
  }

  async forgetMember(id: string) {
    const me = this.me();
    const mid = memoryId(id);
    if (!this.store.members.some((m) => m.id === mid && m.userId === me)) return;
    this.store.members = this.store.members.filter((m) => m.id !== mid);
    this.store.dates = this.store.dates.filter((d) => d.memberId !== mid);
  }

  async saveDate(input: DateInput) {
    const me = this.me();
    const v = checkDate(input);
    if (!this.store.members.some((m) => m.id === v.memberId && m.userId === me)) {
      throw new MemoryError("no family member with that id", "invalid");
    }
    if (v.label === "birthday" && this.store.dates.some((d) => d.userId === me && d.memberId === v.memberId
      && d.label === "birthday" && d.id !== v.id)) {
      throw new MemoryError("that person already has a birthday saved", "duplicate");
    }
    const fields = { memberId: v.memberId, label: v.label, title: v.title, calendar: v.calendar, year: v.year,
      month: v.month, day: v.day };
    if (v.id === null) {
      this.store.dates.push({ ...fields, id: crypto.randomUUID(), userId: me });
      return;
    }
    const row = this.store.dates.find((d) => d.id === v.id && d.userId === me);
    if (!row) throw new MemoryError("no date with that id", "invalid");
    Object.assign(row, fields);
  }

  async forgetDate(id: string) {
    const me = this.me();
    const did = memoryId(id);
    this.store.dates = this.store.dates.filter((d) => !(d.id === did && d.userId === me));
  }
}
