"use client";

import { useId, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FACT_MAX, LABELS, NAME_MAX, NOTE_MAX, RELATIONS, SECTIONS, TITLE_MAX,
  type Calendar, type DateInput, type DateLabel, type Fact, type FactInput, type FamilyDate, type FamilyMember,
  type MemberInput, type MemoryView, type Relation, type Section,
} from "@/adapters/memory/types";
import { AttentionIcon } from "@/components/Icons";
import { memoryRefusal } from "@/core/memory-guard";
import { messages, type Lang } from "@/i18n/messages";
import type { MemoryResult } from "./actions";

type Actions = {
  saveFact: (f: FactInput) => Promise<MemoryResult>;
  forgetFact: (id: string) => Promise<MemoryResult>;
  saveMember: (m: MemberInput) => Promise<MemoryResult>;
  forgetMember: (id: string) => Promise<MemoryResult>;
  saveDate: (d: DateInput) => Promise<MemoryResult>;
  forgetDate: (id: string) => Promise<MemoryResult>;
  startInterview: () => Promise<{ ok: boolean }>;
};
type Props = { lang: Lang; view: MemoryView | null; problem: "loadFailed" | "notReady" | null; actions: Actions };
type T = ReturnType<typeof messages>["about"];

/** What is open for editing: one thing at a time. */
type Open =
  | { kind: "fact"; id: string | null; section: Section }
  | { kind: "member"; id: string | null }
  | { kind: "date"; id: string | null; memberId: string }
  | { kind: "forget"; what: "fact" | "member" | "date"; id: string }
  | null;
type Note = { text: string; error: boolean } | null;

const HIJRI_MONTHS = {
  en: ["Muharram", "Safar", "Rabi' al-Awwal", "Rabi' al-Thani", "Jumada al-Ula", "Jumada al-Akhirah", "Rajab",
    "Sha'ban", "Ramadan", "Shawwal", "Dhu al-Qi'dah", "Dhu al-Hijjah"],
  ar: ["محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة", "رجب", "شعبان", "رمضان", "شوال",
    "ذو القعدة", "ذو الحجة"],
};

function monthName(month: number, calendar: Calendar, lang: Lang): string {
  if (calendar === "hijri") return HIJRI_MONTHS[lang][month - 1] ?? String(month);
  return new Intl.DateTimeFormat(lang === "ar" ? "ar-SA-u-ca-gregory-nu-latn" : "en-GB", { month: "long", timeZone: "UTC" })
    .format(new Date(Date.UTC(2000, month - 1, 1)));
}

export function dateText(d: Pick<FamilyDate, "calendar" | "year" | "month" | "day">, t: T, lang: Lang): string {
  const parts = [String(d.day), monthName(d.month, d.calendar, lang)];
  if (d.year) parts.push(String(d.year));
  return parts.join(" ") + (d.calendar === "hijri" ? ` ${t.hijriSuffix}` : "");
}

/**
 * The About me page. Every item has Edit and Forget; Forget asks first and then deletes for good.
 * Text that breaks the no-secrets rule is refused here with a clear message (the database refuses it too).
 */
export function AboutView({ lang, view, problem, actions }: Props) {
  const t = messages(lang).about;
  const router = useRouter();
  const [open, setOpen] = useState<Open>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<Note>(null);

  async function act(work: () => Promise<MemoryResult>, done: string, failed?: string) {
    if (busy) return;
    setBusy(true);
    setNote(null);
    try {
      const r = await work();
      if (r.ok) {
        setOpen(null);
        setNote({ text: done, error: false });
        router.refresh();
      } else {
        setNote({ text: failed && r.error === "failed" ? failed : t.errors[r.error], error: true });
      }
    } catch {
      setNote({ text: failed ?? t.errors.failed, error: true });
    } finally {
      setBusy(false);
    }
  }

  async function interview() {
    if (busy) return;
    setBusy(true);
    setNote(null);
    try {
      const r = await actions.startInterview();
      if (r.ok) router.push("/chat");
      else setNote({ text: t.interviewFailed, error: true });
    } catch {
      setNote({ text: t.interviewFailed, error: true });
    } finally {
      setBusy(false);
    }
  }

  const status = note && (
    <p role={note.error ? "alert" : "status"} data-testid="about-note" className={`note mt-3 ${note.error ? "note-danger" : ""}`}>
      {note.error && <AttentionIcon />}<span className="wrap">{note.text}</span>
    </p>
  );

  if (!view) {
    return (
      <div className="pt-4 pb-10" data-screen="about">
        <p role="alert" className="note note-danger" data-testid="about-problem">
          <AttentionIcon /><span className="wrap">{t.errors[problem ?? "loadFailed"]}</span>
        </p>
      </div>
    );
  }

  const facts = (section: Section) => view.facts.filter((f) => f.section === section);
  const done = view.interview === "done" || view.facts.length > 0 || view.members.length > 0;
  const forgetting = (what: "fact" | "member" | "date", id: string) => open?.kind === "forget" && open.what === what && open.id === id;

  const forgetBox = (what: "fact" | "member" | "date", id: string) => forgetting(what, id) && (
    <div role="alertdialog" aria-label={t.forget} data-testid="forget-confirm"
      className="mt-3 min-w-0 rounded-xl border border-gold-ink px-3 py-3">
      <p className="t-small wrap text-gold-ink">{what === "member" ? t.forgetPersonConfirm : t.forgetConfirm}</p>
      <div className="mt-3 flex gap-2">
        <button type="button" disabled={busy} data-testid="forget-yes"
          className="btn btn-secondary flex-1 border-gold-ink text-gold-ink"
          onClick={() => act(() => (what === "fact" ? actions.forgetFact(id) : what === "member" ? actions.forgetMember(id)
            : actions.forgetDate(id)), t.forgotten, t.errors.forgetFailed)}>
          {t.forgetYes}
        </button>
        <button type="button" disabled={busy} className="btn btn-secondary flex-1" onClick={() => setOpen(null)}>{t.cancel}</button>
      </div>
    </div>
  );

  const rowButtons = (onEdit: () => void, what: "fact" | "member" | "date", id: string, label: string) => (
    <div className="flex flex-none gap-1">
      <button type="button" className="btn btn-quiet px-3" disabled={busy} onClick={onEdit}
        aria-label={`${t.edit}: ${label}`}>{t.edit}</button>
      <button type="button" className="btn btn-quiet px-3" disabled={busy} data-testid="forget"
        onClick={() => { setNote(null); setOpen({ kind: "forget", what, id }); }} aria-label={`${t.forget}: ${label}`}>
        {t.forget}
      </button>
    </div>
  );

  const factRow = (f: Fact) => (
    <li key={f.id} className="border-b border-edge py-3" data-testid="fact">
      {open?.kind === "fact" && open.id === f.id ? (
        <FactForm t={t} initial={f} busy={busy} onCancel={() => setOpen(null)}
          onSave={(v) => act(() => actions.saveFact(v), t.saved)} />
      ) : (
        <>
          <div className="flex min-w-0 items-start gap-2">
            <div className="min-w-0 flex-1">
              <p className="wrap">{f.body}</p>
              {f.source === "interview" && <p className="t-caption text-muted">{t.fromInterview}</p>}
            </div>
            {rowButtons(() => { setNote(null); setOpen({ kind: "fact", id: f.id, section: f.section }); }, "fact", f.id, f.body)}
          </div>
          {forgetBox("fact", f.id)}
        </>
      )}
    </li>
  );

  const addFact = (section: Section) => (open?.kind === "fact" && open.id === null && open.section === section ? (
    <div className="py-3"><FactForm t={t} initial={{ body: "", section }} busy={busy} onCancel={() => setOpen(null)}
      onSave={(v) => act(() => actions.saveFact(v), t.saved)} /></div>
  ) : (
    <button type="button" className="btn btn-secondary mt-3" disabled={busy} data-testid={`add-${section}`}
      onClick={() => { setNote(null); setOpen({ kind: "fact", id: null, section }); }}>
      {section === "family" ? t.addFamilyNote : t.add}
    </button>
  ));

  const memberBlock = (m: FamilyMember) => {
    const dates = view.dates.filter((d) => d.memberId === m.id);
    return (
      <li key={m.id} className="border-b border-edge py-3" data-testid="member">
        {open?.kind === "member" && open.id === m.id ? (
          <MemberForm t={t} initial={m} busy={busy} onCancel={() => setOpen(null)}
            onSave={(v) => act(() => actions.saveMember(v), t.saved)} />
        ) : (
          <div className="flex min-w-0 items-start gap-2">
            <div className="min-w-0 flex-1">
              <p className="wrap font-semibold">{m.name} <span className="t-small text-muted">· {t.relations[m.relation]}</span></p>
              {m.note && <p className="t-small wrap text-muted">{m.note}</p>}
            </div>
            {rowButtons(() => { setNote(null); setOpen({ kind: "member", id: m.id }); }, "member", m.id, m.name)}
          </div>
        )}
        {forgetBox("member", m.id)}
        <ul className="ms-3 mt-2">
          {dates.map((d) => (
            <li key={d.id} className="py-2" data-testid="family-date">
              {open?.kind === "date" && open.id === d.id ? (
                <DateForm t={t} lang={lang} initial={d} busy={busy} onCancel={() => setOpen(null)}
                  onSave={(v) => act(() => actions.saveDate(v), t.saved)} />
              ) : (
                <>
                  <div className="flex min-w-0 items-start gap-2">
                    <p className="t-small wrap min-w-0 flex-1">
                      {d.label === "other" ? d.title : t.labels[d.label]} · {dateText(d, t, lang)}
                    </p>
                    {rowButtons(() => { setNote(null); setOpen({ kind: "date", id: d.id, memberId: m.id }); }, "date", d.id,
                      `${m.name} ${t.labels[d.label]}`)}
                  </div>
                  {forgetBox("date", d.id)}
                </>
              )}
            </li>
          ))}
        </ul>
        {open?.kind === "date" && open.id === null && open.memberId === m.id ? (
          <DateForm t={t} lang={lang} initial={{ memberId: m.id }} busy={busy} onCancel={() => setOpen(null)}
            onSave={(v) => act(() => actions.saveDate(v), t.saved)} />
        ) : (
          <button type="button" className="btn btn-quiet mt-1 px-3" disabled={busy}
            onClick={() => { setNote(null); setOpen({ kind: "date", id: null, memberId: m.id }); }}>{t.addDate}</button>
        )}
      </li>
    );
  };

  return (
    <div className="pt-4 pb-10" data-screen="about">
      <p className="t-small wrap text-muted">{t.intro}</p>
      <div className="mt-4">
        <button type="button" className="btn btn-primary w-full" disabled={busy} onClick={interview} data-testid="interview">
          {done ? t.interviewAgain : t.interview}
        </button>
        <p className="t-small wrap mt-2 text-muted">{t.interviewHelp}</p>
      </div>
      {status}

      {SECTIONS.map((section) => (
        <section key={section} aria-labelledby={`about-${section}`} data-testid={`group-${section}`}>
          <h2 id={`about-${section}`} className="t-heading mt-8 mb-1">{t.groups[section]}</h2>
          {section === "family" && (
            <>
              {view.members.length === 0 && facts("family").length === 0 && <p className="t-small text-muted">{t.empty.family}</p>}
              <ul>{view.members.map(memberBlock)}</ul>
              {open?.kind === "member" && open.id === null ? (
                <div className="py-3"><MemberForm t={t} initial={null} busy={busy} onCancel={() => setOpen(null)}
                  onSave={(v) => act(() => actions.saveMember(v), t.saved)} /></div>
              ) : (
                <button type="button" className="btn btn-secondary mt-3 me-2" disabled={busy} data-testid="add-person"
                  onClick={() => { setNote(null); setOpen({ kind: "member", id: null }); }}>{t.addPerson}</button>
              )}
            </>
          )}
          {section !== "family" && facts(section).length === 0 && <p className="t-small text-muted">{t.empty[section]}</p>}
          <ul>{facts(section).map(factRow)}</ul>
          {addFact(section)}
        </section>
      ))}
      <p className="t-caption wrap mt-8 text-muted">{t.backups}</p>
    </div>
  );
}

// ---------- the small forms ----------
function Secret({ t, text }: { t: T; text: string }) {
  return memoryRefusal(text) ? (
    <p role="alert" className="note note-danger mt-2"><AttentionIcon /><span className="wrap">{t.errors.secret}</span></p>
  ) : null;
}

function Buttons({ t, busy, ok, onCancel }: { t: T; busy: boolean; ok: boolean; onCancel: () => void }) {
  return (
    <div className="mt-3 flex gap-2">
      <button type="submit" className="btn btn-primary flex-1" disabled={busy || !ok} aria-busy={busy}>
        {busy ? t.saving : t.save}
      </button>
      <button type="button" className="btn btn-secondary flex-1" disabled={busy} onClick={onCancel}>{t.cancel}</button>
    </div>
  );
}

function FactForm({ t, initial, busy, onSave, onCancel }: {
  t: T; initial: Pick<Fact, "body" | "section"> & { id?: string }; busy: boolean;
  onSave: (f: FactInput) => void; onCancel: () => void;
}) {
  const [body, setBody] = useState(initial.body);
  const [section, setSection] = useState<Section>(initial.section);
  const ids = { body: useId(), section: useId() };
  const ok = body.trim().length > 0 && body.length <= FACT_MAX && !memoryRefusal(body);
  return (
    <form data-testid="fact-form" onSubmit={(e) => { e.preventDefault(); if (ok) onSave({ id: initial.id ?? null, section, body }); }}>
      <label className="t-small block text-muted" htmlFor={ids.body}>{t.fields.fact}</label>
      <textarea id={ids.body} className="field mt-1 block w-full py-2" rows={2} maxLength={FACT_MAX} value={body}
        onChange={(e) => setBody(e.target.value)} aria-invalid={!ok && body.length > 0} />
      <Secret t={t} text={body} />
      <label className="t-small mt-3 block text-muted" htmlFor={ids.section}>{t.fields.section}</label>
      <select id={ids.section} className="field mt-1 block w-full" value={section} onChange={(e) => setSection(e.target.value as Section)}>
        {SECTIONS.map((s) => <option key={s} value={s}>{t.groups[s]}</option>)}
      </select>
      <Buttons t={t} busy={busy} ok={ok} onCancel={onCancel} />
    </form>
  );
}

function MemberForm({ t, initial, busy, onSave, onCancel }: {
  t: T; initial: FamilyMember | null; busy: boolean; onSave: (m: MemberInput) => void; onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [relation, setRelation] = useState<Relation>(initial?.relation ?? "wife");
  const [note, setNote] = useState(initial?.note ?? "");
  const ids = { name: useId(), relation: useId(), note: useId() };
  const ok = name.trim().length > 0 && !memoryRefusal(name) && !memoryRefusal(note);
  return (
    <form data-testid="member-form"
      onSubmit={(e) => { e.preventDefault(); if (ok) onSave({ id: initial?.id ?? null, name, relation, note }); }}>
      <label className="t-small block text-muted" htmlFor={ids.name}>{t.fields.name}</label>
      <input id={ids.name} className="field mt-1 block w-full" maxLength={NAME_MAX} value={name} onChange={(e) => setName(e.target.value)} />
      <label className="t-small mt-3 block text-muted" htmlFor={ids.relation}>{t.fields.relation}</label>
      <select id={ids.relation} className="field mt-1 block w-full" value={relation} onChange={(e) => setRelation(e.target.value as Relation)}>
        {RELATIONS.map((r) => <option key={r} value={r}>{t.relations[r]}</option>)}
      </select>
      <label className="t-small mt-3 block text-muted" htmlFor={ids.note}>{t.fields.note}</label>
      <input id={ids.note} className="field mt-1 block w-full" maxLength={NOTE_MAX} value={note} onChange={(e) => setNote(e.target.value)} />
      <Secret t={t} text={`${name} ${note}`} />
      <Buttons t={t} busy={busy} ok={ok} onCancel={onCancel} />
    </form>
  );
}

function DateForm({ t, lang, initial, busy, onSave, onCancel }: {
  t: T; lang: Lang; initial: Partial<FamilyDate> & { memberId: string }; busy: boolean;
  onSave: (d: DateInput) => void; onCancel: () => void;
}) {
  const [label, setLabel] = useState<DateLabel>(initial.label ?? "birthday");
  const [title, setTitle] = useState(initial.title ?? "");
  const [calendar, setCalendar] = useState<Calendar>(initial.calendar ?? "gregorian");
  const [year, setYear] = useState(initial.year ? String(initial.year) : "");
  const [month, setMonth] = useState(initial.month ?? 1);
  const [day, setDay] = useState(initial.day ?? 1);
  const ids = { label: useId(), title: useId(), year: useId(), month: useId(), day: useId() };
  const yearNumber = year.trim() ? Number(year) : null;
  const yearOk = yearNumber === null || (Number.isInteger(yearNumber)
    && (calendar === "hijri" ? yearNumber >= 1300 && yearNumber <= 1500 : yearNumber >= 1900 && yearNumber <= 2100));
  const ok = yearOk && (label !== "other" || title.trim().length > 0) && !memoryRefusal(title);
  const days = calendar === "hijri" ? 30 : [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];
  return (
    <form data-testid="date-form" className="py-2" onSubmit={(e) => {
      e.preventDefault();
      if (ok) onSave({ id: initial.id ?? null, memberId: initial.memberId, label, title, calendar, year: yearNumber, month, day: Math.min(day, days) });
    }}>
      <label className="t-small block text-muted" htmlFor={ids.label}>{t.fields.label}</label>
      <select id={ids.label} className="field mt-1 block w-full" value={label} onChange={(e) => setLabel(e.target.value as DateLabel)}>
        {LABELS.map((l) => <option key={l} value={l}>{t.labels[l]}</option>)}
      </select>
      {label === "other" && (
        <>
          <label className="t-small mt-3 block text-muted" htmlFor={ids.title}>{t.fields.title}</label>
          <input id={ids.title} className="field mt-1 block w-full" maxLength={TITLE_MAX} value={title} onChange={(e) => setTitle(e.target.value)} />
          <Secret t={t} text={title} />
        </>
      )}
      <p className="t-small mt-3 text-muted">{t.fields.calendar}</p>
      <div className="mt-1 flex gap-2" role="group" aria-label={t.fields.calendar}>
        {(["gregorian", "hijri"] as const).map((c) => (
          <button key={c} type="button" className="option" aria-pressed={calendar === c} onClick={() => setCalendar(c)}>{t.calendars[c]}</button>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <label className="t-small flex min-w-0 flex-1 flex-col text-muted" htmlFor={ids.day}>{t.fields.day}
          <select id={ids.day} className="field mt-1" value={Math.min(day, days)} onChange={(e) => setDay(Number(e.target.value))}>
            {Array.from({ length: days }, (_, i) => i + 1).map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
        <label className="t-small flex min-w-0 flex-[2] flex-col text-muted" htmlFor={ids.month}>{t.fields.month}
          <select id={ids.month} className="field mt-1" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <option key={m} value={m}>{monthName(m, calendar, lang)}</option>)}
          </select>
        </label>
        <label className="t-small flex min-w-0 flex-1 flex-col text-muted" htmlFor={ids.year}>{t.fields.year}
          <input id={ids.year} className="field mt-1" inputMode="numeric" dir="ltr" value={year} maxLength={4}
            onChange={(e) => setYear(e.target.value.replace(/[^0-9]/g, ""))} aria-invalid={!yearOk} />
        </label>
      </div>
      <Buttons t={t} busy={busy} ok={ok} onCancel={onCancel} />
    </form>
  );
}
