/**
 * Snafi step 6 in the app: the About me page (grouped, Edit and Forget on every item, Forget asks first),
 * the no-secrets rule (the same fixture as the worker and the database), the memory adapters chosen by
 * config, the Menu's About me link, "Turn off on all phones" (SEC-153 follow-up) and the worker's Hijri
 * table checked against the Umm al-Qura calendar.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DEFAULT_SETTINGS } from "@/adapters/mailbox/types";
import { createMemoryBookStore, InMemoryMemoryAdapter } from "@/adapters/memory/inmemory";
import { checkDate, MemoryError, type MemoryView } from "@/adapters/memory/types";
import type { MemoryResult } from "@/app/(app)/about/actions";
import { AboutView, dateText } from "@/app/(app)/about/AboutView";
import { SettingsForm } from "@/app/(app)/settings/SettingsForm";
import { Menu } from "@/components/Menu";
import { adapterChoice } from "@/config/services";
import { memoryRefusal, normalise } from "@/core/memory-guard";
import { messages } from "@/i18n/messages";

const refresh = vi.fn();
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh, push }), usePathname: () => "/about" }));

const REPO = resolve(process.cwd(), "..", "..");
const GUARD = JSON.parse(readFileSync(resolve(REPO, "tests", "fixtures", "snafi_memory_guard.json"), "utf8")) as {
  allowed: string[]; refused: string[];
};
const ME = "11111111-1111-4111-8111-111111111111";
const OTHER = "22222222-2222-4222-8222-222222222222";
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const t = messages("en").about;

describe("the no-secrets rule, the same as the worker and the database", () => {
  it.each(GUARD.allowed)("allows %s", (text) => expect(memoryRefusal(text)).toBeNull());
  it.each(GUARD.refused)("refuses %s", (text) => expect(memoryRefusal(text)).not.toBeNull());

  it("normalises Arabic the way the worker does", () => {
    expect(normalise("أإآٱ")).toBe("اااا");
    expect(normalise("زوجةٌ")).toBe("زوجه");
    expect(normalise("مُصطفى")).toBe("مصطفي");
    expect(normalise("١٢٣")).toBe("123");
  });
});

describe("the worker's Hijri table matches the Umm al-Qura calendar", () => {
  it("every month start in src/snafi_worker/memory/hijri.py is day 1 of that Hijri month", () => {
    const source = readFileSync(resolve(REPO, "src", "snafi_worker", "memory", "hijri.py"), "utf8");
    const rows = [...source.matchAll(/\((\d{4}), (\d{1,2}), "(\d{4}-\d{2}-\d{2})"\)/g)];
    expect(rows.length).toBe(41 * 12);
    const f = new Intl.DateTimeFormat("en-u-ca-islamic-umalqura-nu-latn", { timeZone: "UTC", year: "numeric", month: "numeric", day: "numeric" });
    for (const [, y, m, iso] of rows) {
      const parts = Object.fromEntries(f.formatToParts(new Date(`${iso}T12:00:00Z`)).map((p) => [p.type, p.value]));
      expect([Number(parts.year.replace(/\D/g, "")), Number(parts.month), Number(parts.day)], iso).toEqual([Number(y), Number(m), 1]);
    }
  });
});

describe("memory adapters", () => {
  it("are chosen by SNAFI_MEMORY_ADAPTER, and never the in-memory one in production", () => {
    expect(adapterChoice({}).memory).toBe("supabase");
    expect(adapterChoice({ SNAFI_MEMORY_ADAPTER: "memory" }).memory).toBe("memory");
    expect(adapterChoice({}, true).memory).toBe("memory");
    expect(() => adapterChoice({ SNAFI_MEMORY_ADAPTER: "memory" }, false, "production")).toThrow(/tests and the development server/);
    expect(() => adapterChoice({ SNAFI_MEMORY_ADAPTER: "pgvector" })).toThrow(/is not one of/);
  });

  it("each user sees and changes only their own memory; forgetting a person takes their dates", async () => {
    const store = createMemoryBookStore();
    const mine = new InMemoryMemoryAdapter(store, ME);
    const theirs = new InMemoryMemoryAdapter(store, OTHER);
    await mine.saveFact({ id: null, section: "preferences", body: "Likes tea" });
    await mine.saveMember({ id: null, name: "Sara", relation: "wife", note: "" });
    const sara = (await mine.load()).members[0];
    await mine.saveDate({ id: null, memberId: sara.id, label: "birthday", title: "", calendar: "hijri", year: null, month: 9, day: 30 });
    expect(await theirs.load()).toEqual({ facts: [], members: [], dates: [], interview: "none" });
    await theirs.forgetMember(sara.id);
    expect((await mine.load()).dates).toHaveLength(1);
    await expect(theirs.saveDate({ id: null, memberId: sara.id, label: "other", title: "x", calendar: "gregorian", year: null, month: 1, day: 1 }))
      .rejects.toBeInstanceOf(MemoryError);
    await mine.forgetMember(sara.id);
    const after = await mine.load();
    expect([after.members, after.dates]).toEqual([[], []]);
    await expect(mine.saveFact({ id: null, section: "me", body: "My password is x" })).rejects.toMatchObject({ kind: "secret" });
  });

  it("checks dates in both calendars", () => {
    const base = { id: null, memberId: id(1), label: "birthday" as const, title: "", year: null as number | null };
    expect(() => checkDate({ ...base, calendar: "gregorian", month: 2, day: 30 })).toThrow();
    expect(() => checkDate({ ...base, calendar: "gregorian", month: 2, day: 29, year: 2023 })).toThrow();
    expect(checkDate({ ...base, calendar: "gregorian", month: 2, day: 29, year: 2024 }).day).toBe(29);
    expect(checkDate({ ...base, calendar: "hijri", month: 9, day: 30, year: 1440 }).day).toBe(30);
    expect(() => checkDate({ ...base, calendar: "hijri", month: 9, day: 31 })).toThrow();
    expect(() => checkDate({ ...base, calendar: "hijri", month: 9, day: 1, year: 2020 })).toThrow();
  });
});

// ---------- the About me page ----------
const VIEW: MemoryView = {
  facts: [
    { id: id(1), body: "Works as an IT consultant", section: "me", source: "interview", createdAt: "" },
    { id: id(2), body: "Likes black coffee", section: "preferences", source: "told", createdAt: "" },
  ],
  members: [{ id: id(3), name: "Sara", relation: "wife", note: "Loves white roses" }],
  dates: [{ id: id(4), memberId: id(3), label: "birthday", title: "", calendar: "gregorian", year: 1992, month: 3, day: 14 }],
  interview: "done",
};

function actions() {
  const ok = async (): Promise<MemoryResult> => ({ ok: true });
  return {
    saveFact: vi.fn(ok), forgetFact: vi.fn(ok), saveMember: vi.fn(ok), forgetMember: vi.fn(ok), saveDate: vi.fn(ok),
    forgetDate: vi.fn(ok), startInterview: vi.fn(async () => ({ ok: true })),
  };
}

beforeEach(() => {
  refresh.mockClear();
  push.mockClear();
});

describe("About me", () => {
  it("shows everything Ahmad knows, grouped Me, Family, Preferences and Routine", () => {
    render(<AboutView lang="en" view={VIEW} problem={null} actions={actions()} />);
    expect(within(screen.getByTestId("group-me")).getByText("Works as an IT consultant")).toBeInTheDocument();
    expect(within(screen.getByTestId("group-me")).getByText("From the interview")).toBeInTheDocument();
    expect(within(screen.getByTestId("group-preferences")).getByText("Likes black coffee")).toBeInTheDocument();
    const fam = screen.getByTestId("group-family");
    expect(within(fam).getByText("Sara")).toBeInTheDocument();
    expect(within(fam).getByTestId("family-date")).toHaveTextContent("Birthday · 14 March 1992");
    expect(within(screen.getByTestId("group-routine")).getByText(t.empty.routine)).toBeInTheDocument();
    expect(screen.getByTestId("interview")).toHaveTextContent("Interview me again");
    expect(screen.getByText(/leaves the PC's daily backups within 30 days/)).toBeInTheDocument();
  });

  it("every item has Edit and Forget", () => {
    render(<AboutView lang="en" view={VIEW} problem={null} actions={actions()} />);
    // two facts, one person, one date
    expect(screen.getAllByRole("button", { name: /^Edit: / })).toHaveLength(4);
    expect(screen.getAllByRole("button", { name: /^Forget: / })).toHaveLength(4);
  });

  it("Forget asks first; Cancel changes nothing; Yes deletes", async () => {
    const a = actions();
    render(<AboutView lang="en" view={VIEW} problem={null} actions={a} />);
    fireEvent.click(screen.getByRole("button", { name: "Forget: Likes black coffee" }));
    expect(screen.getByTestId("forget-confirm")).toHaveTextContent("Forget this for good?");
    fireEvent.click(within(screen.getByTestId("forget-confirm")).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByTestId("forget-confirm")).toBeNull();
    expect(a.forgetFact).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Forget: Sara" }));
    expect(screen.getByTestId("forget-confirm")).toHaveTextContent("this person and all their dates");
    fireEvent.click(screen.getByTestId("forget-yes"));
    expect(await screen.findByText("Forgotten.")).toBeInTheDocument();
    expect(a.forgetMember).toHaveBeenCalledWith(id(3));
    expect(refresh).toHaveBeenCalled();
  });

  it("Edit saves the change; secrets are refused before anything is sent", async () => {
    const a = actions();
    render(<AboutView lang="en" view={VIEW} problem={null} actions={a} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit: Likes black coffee" }));
    const box = screen.getByLabelText("What Ahmad should know");
    fireEvent.change(box, { target: { value: "My card number is 4111 1111 1111 1111" } });
    expect(screen.getByRole("alert")).toHaveTextContent("never keeps passwords");
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    fireEvent.change(box, { target: { value: "Likes Arabic coffee" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(a.saveFact).toHaveBeenCalledWith({ id: id(2), section: "preferences", body: "Likes Arabic coffee" });
  });

  it("adds a person and a Hijri date", async () => {
    const a = actions();
    render(<AboutView lang="en" view={VIEW} problem={null} actions={a} />);
    fireEvent.click(screen.getByTestId("add-person"));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Noura" } });
    fireEvent.change(screen.getByLabelText("Relation"), { target: { value: "daughter" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(a.saveMember).toHaveBeenCalledWith({ id: null, name: "Noura", relation: "daughter", note: "" });
    fireEvent.click(screen.getByRole("button", { name: "Add a date" }));
    fireEvent.click(screen.getByRole("button", { name: "Hijri" }));
    fireEvent.change(screen.getByLabelText("Month"), { target: { value: "9" } });
    fireEvent.change(screen.getByLabelText("Day"), { target: { value: "30" } });
    fireEvent.change(screen.getByLabelText("Year (optional)"), { target: { value: "1440" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findAllByText("Saved.");
    expect(a.saveDate).toHaveBeenCalledWith({ id: null, memberId: id(3), label: "birthday", title: "", calendar: "hijri",
      year: 1440, month: 9, day: 30 });
  });

  it("says why a save failed", async () => {
    const a = actions();
    a.saveFact.mockResolvedValueOnce({ ok: false, error: "secret" });
    render(<AboutView lang="en" view={VIEW} problem={null} actions={a} />);
    fireEvent.click(screen.getByTestId("add-routine"));
    fireEvent.change(screen.getByLabelText("What Ahmad should know"), { target: { value: "Walks after Isha" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByTestId("about-note")).toHaveTextContent(t.errors.secret);
  });

  it("Interview me sends Khalid to Chat, where the interview starts", async () => {
    const a = actions();
    render(<AboutView lang="en" view={{ ...VIEW, facts: [], members: [], dates: [], interview: "invited" }} problem={null} actions={a} />);
    fireEvent.click(screen.getByTestId("interview"));
    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/chat"));
    expect(screen.getByTestId("interview")).toHaveTextContent("Interview me");
  });

  it("works in Arabic and with Hijri month names", () => {
    const ar = messages("ar").about;
    render(<AboutView lang="ar" view={VIEW} problem={null} actions={actions()} />);
    expect(screen.getByText(ar.groups.preferences)).toBeInTheDocument();
    expect(dateText({ calendar: "hijri", year: 1440, month: 9, day: 12 }, ar, "ar")).toBe("12 رمضان 1440 هـ");
    expect(dateText({ calendar: "hijri", year: null, month: 9, day: 12 }, t, "en")).toBe("12 Ramadan AH");
  });

  it("says plainly when memory can't be loaded or isn't set up yet", () => {
    const { unmount } = render(<AboutView lang="en" view={null} problem="notReady" actions={actions()} />);
    expect(screen.getByTestId("about-problem")).toHaveTextContent("migration 0010");
    unmount();
    render(<AboutView lang="en" view={null} problem="loadFailed" actions={actions()} />);
    expect(screen.getByTestId("about-problem")).toHaveTextContent("Couldn't load");
  });
});

describe("the menu", () => {
  it("has About me above Settings when signed in", () => {
    const m = messages("en");
    render(<Menu labels={{ menu: m.menu, closeMenu: m.closeMenu, theme: m.theme, dark: m.dark, light: m.light, language: m.language,
      signOut: m.signOut, settings: m.settingsLink, about: m.aboutLink }} theme="dark" lang="en" signOutAction={async () => undefined} />);
    fireEvent.click(screen.getByTestId("menu-button"));
    const about = screen.getByTestId("menu-about");
    expect(about).toHaveAttribute("href", "/about");
    expect(about.compareDocumentPosition(screen.getByTestId("menu-settings")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe("Turn off on all phones (SEC-153 follow-up)", () => {
  const ok = async () => ({ ok: true });
  const s = messages("en").settings;

  it("asks first, then removes every phone in the database and switches push off", async () => {
    const save = vi.fn(ok);
    const all = vi.fn(async () => ({ ok: true }));
    render(<SettingsForm initial={{ ...DEFAULT_SETTINGS, pushEnabled: true }} lang="en" t={s} publicKey={"B" + "A".repeat(86)}
      save={save} subscribe={ok} unsubscribe={ok} unsubscribeAll={all} test={ok} env={() => null} />);
    fireEvent.click(screen.getByRole("button", { name: "Turn off on all phones" }));
    expect(all).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Yes, turn off on all phones" }));
    expect(await screen.findByText(/Notifications are off on all phones/)).toBeInTheDocument();
    expect(all).toHaveBeenCalledTimes(1);
    expect(save).not.toHaveBeenCalled();
  });

  it("before migration 0011 it still switches the account off", async () => {
    const save = vi.fn(ok);
    render(<SettingsForm initial={{ ...DEFAULT_SETTINGS, pushEnabled: true }} lang="en" t={s} publicKey={"B" + "A".repeat(86)}
      save={save} subscribe={ok} unsubscribe={ok} unsubscribeAll={async () => ({ ok: false, missing: true })} test={ok}
      env={() => null} />);
    fireEvent.click(screen.getByRole("button", { name: "Turn off on all phones" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, turn off on all phones" }));
    expect(await screen.findByText(/Notifications are off on all phones/)).toBeInTheDocument();
    expect(save).toHaveBeenCalledWith({ pushEnabled: false, briefTime: "07:00", dailyCap: 10 });
  });

  it("a real failure is shown and nothing claims success", async () => {
    render(<SettingsForm initial={{ ...DEFAULT_SETTINGS, pushEnabled: true }} lang="en" t={s} publicKey={"B" + "A".repeat(86)}
      save={ok} subscribe={ok} unsubscribe={ok} unsubscribeAll={async () => ({ ok: false })} test={ok} env={() => null} />);
    fireEvent.click(screen.getByRole("button", { name: "Turn off on all phones" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, turn off on all phones" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't save");
  });
});
