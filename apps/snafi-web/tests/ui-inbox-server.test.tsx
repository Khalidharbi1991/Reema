// @vitest-environment node
/**
 * The server half of the Inbox, run for real: the Supabase mailbox's `cards()` and `markCardRead`
 * against a stand-in client (AC-6, AC-11 and SEC-172), and the Inbox page's check of `?open=`
 * (AC-18 and SEC-174). These replace the source-text checks in ui-acceptance.test.tsx, which could
 * only see that the code had not changed, not what it does. `server-only` is aliased to an empty
 * stub in vitest.config.ts so these modules can be loaded at all.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MailboxError, READ_KEEP_MS } from "@/adapters/mailbox/types";

const h = vi.hoisted(() => ({ client: null as unknown as FakeClient }));
vi.mock("@/adapters/supabase/server-client", () => ({ createSupabaseServerClient: async () => h.client }));

const { SupabaseMailboxAdapter } = await import("@/adapters/mailbox/supabase");

type Failure = { message: string; code?: string };
type Result = { data?: Record<string, unknown>[] | null; error?: Failure | null };

/** One PostgREST query: records the steps the adapter asks for, then answers with a set result. */
class FakeQuery {
  readonly steps: string[] = [];
  constructor(private readonly result: Result) {}
  private step(name: string, ...args: unknown[]) {
    this.steps.push(`${name}(${args.map((a) => String(a)).join(", ")})`);
    return this;
  }
  select(columns: string) { return this.step("select", columns); }
  is(column: string, value: unknown) { return this.step("is", column, value); }
  or(filter: string) { return this.step("or", filter); }
  order(column: string, o: { ascending: boolean }) { return this.step("order", column, o.ascending); }
  limit(n: number) { return this.step("limit", n); }
  then<T>(resolve: (r: { data: Record<string, unknown>[] | null; error: Failure | null }) => T) {
    return Promise.resolve({ data: this.result.data ?? null, error: this.result.error ?? null }).then(resolve);
  }
}

class FakeClient {
  readonly queries: { table: string; query: FakeQuery }[] = [];
  readonly rpcs: { name: string; args: unknown }[] = [];
  constructor(private readonly results: Result[], private readonly rpcResult: Result = {}) {}
  from(table: string) {
    const query = new FakeQuery(this.results.shift() ?? { data: [] });
    this.queries.push({ table, query });
    return query;
  }
  async rpc(name: string, args: unknown) {
    this.rpcs.push({ name, args });
    return { data: null, error: this.rpcResult.error ?? null };
  }
}

const use = (results: Result[], rpcResult: Result = {}) => (h.client = new FakeClient(results, rpcResult));
const mailbox = () => new SupabaseMailboxAdapter();
const ID = "11111111-1111-4111-8111-111111111111";
const steps = (n = 0) => h.client.queries[n].query.steps;
const row = (over: Record<string, unknown> = {}) => ({
  id: ID, kind: "reminder", title: "Call the bank", body: "At 4 PM", created_at: "2026-11-15T10:00:00Z", ...over,
});

beforeEach(() => {
  h.client = new FakeClient([]);
});

describe("AC-6: cards() asks for the read time and the 7-day window", () => {
  it("reads not-dismissed, unread-or-read-inside-7-days cards, newest first, and maps the read time", async () => {
    const readAt = "2026-11-14T10:00:00Z";
    use([{ data: [row(), row({ id: "22222222-2222-4222-8222-222222222222", read_at: readAt })] }]);
    const before = Date.now();
    const cards = await mailbox().cards(10);
    expect(cards.map((c) => c.readAt)).toEqual([null, readAt]);
    expect(h.client.queries).toHaveLength(1);
    expect(h.client.queries[0].table).toBe("cards");
    expect(steps()[0]).toBe("select(id, kind, title, body, created_at, read_at)");
    expect(steps()[1]).toBe("is(dismissed_at, null)");
    expect(steps()[3]).toBe("order(created_at, false)");
    expect(steps()[4]).toBe("limit(10)");
    // The cutoff is the server's own clock, 7 days back; an unread card is kept at any age.
    const cutoff = /^or\(read_at\.is\.null,read_at\.gt\.(.+)\)$/.exec(steps()[2])![1];
    expect(Date.parse(cutoff)).toBeGreaterThanOrEqual(before - READ_KEEP_MS - 1000);
    expect(Date.parse(cutoff)).toBeLessThanOrEqual(Date.now() - READ_KEEP_MS);
  });
});

describe("SEC-172: the old query runs only when the column or function is missing", () => {
  it.each(["42703", "42883", "PGRST204", "PGRST202"])("falls back on %s and shows the cards as unread", async (code) => {
    use([{ error: { message: "column cards.read_at does not exist", code } }, { data: [row()] }]);
    const cards = await mailbox().cards(10);
    expect(cards.map((c) => c.readAt)).toEqual([null]);
    expect(h.client.queries).toHaveLength(2);
    expect(steps(1)[0]).toBe("select(id, kind, title, body, created_at)");
    expect(steps(1).some((s) => s.startsWith("or("))).toBe(false);
  });

  it.each([
    ["57014", "canceling statement due to statement timeout"],
    ["42501", "permission denied for table cards"],
    [undefined, "fetch failed"],
  ])("passes a %s error on instead of falling back", async (code, message) => {
    use([{ error: { message, code } }, { data: [row()] }]);
    await expect(mailbox().cards(10)).rejects.toThrow(new MailboxError(message));
    expect(h.client.queries).toHaveLength(1); // the old query never ran: the page shows its error state
  });

  it("does not swallow a failure of the old query either", async () => {
    use([{ error: { message: "no read_at", code: "42703" } }, { error: { message: "gone" } }]);
    await expect(mailbox().cards(10)).rejects.toThrow(MailboxError);
  });
});

describe("AC-11 and SEC-172: markCardRead", () => {
  it("goes only through the database function, with a checked id", async () => {
    use([], {});
    await mailbox().markCardRead(ID.toUpperCase());
    expect(h.client.rpcs).toEqual([{ name: "mark_card_read", args: { p_id: ID } }]);
    await expect(mailbox().markCardRead("not-an-id")).rejects.toThrow("invalid id");
  });

  it("marks a missing mark_card_read as such, so the caller may stay quiet", async () => {
    use([], { error: { message: "function public.mark_card_read(uuid) does not exist", code: "42883" } });
    await expect(mailbox().markCardRead(ID)).rejects.toMatchObject({ schemaMissing: true });
  });

  it("marks any other failure as a real one, to be reported", async () => {
    use([], { error: { message: "permission denied", code: "42501" } });
    await expect(mailbox().markCardRead(ID)).rejects.toMatchObject({ schemaMissing: false });
  });
});

// ---------------------------------------------------------------------------------------------
const today = vi.hoisted(() => ({ load: vi.fn() }));
vi.mock("@/core/today-data", () => ({ loadToday: today.load }));
vi.mock("@/app/(app)/actions", () => ({ decideApproval: vi.fn(), markCardRead: vi.fn() }));

const { default: InboxPage } = await import("@/app/(app)/inbox/page");

/** The `open` prop the page hands to the Inbox for a given address. */
async function openProp(value: string | string[] | undefined) {
  today.load.mockResolvedValue({
    lang: "en", now: new Date("2026-11-15T13:10:00Z"), today: { approvals: [], cards: [] },
  });
  const tree = await InboxPage({ searchParams: Promise.resolve({ open: value }) });
  const children = (tree.props as { children: { props?: { open?: string } }[] }).children;
  return children.find((c) => c?.props && "open" in c.props)!.props!.open;
}

describe("SEC-174: ?open= is checked on the server", () => {
  it("keeps one of our ids, in lower case", async () => {
    expect(await openProp(ID)).toBe(ID);
    expect(await openProp(ID.toUpperCase())).toBe(ID);
  });

  it.each([
    ["a name that is not an id", "approvals"],
    ["an id with something added", `${ID}' or '1`],
    ["a very long value", "x".repeat(5000)],
    ["a path", "../../today"],
    ["a script", "<script>alert(1)</script>"],
    ["repeated in the address", [ID, ID] as string[]],
    ["nothing", undefined],
  ])("drops %s, so the page draws as usual and nothing is marked read", async (_name, value) => {
    expect(await openProp(value)).toBeUndefined();
  });
});
