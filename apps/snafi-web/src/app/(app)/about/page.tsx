import { memoryAdapter } from "@/adapters";
import { MemoryError, type MemoryView } from "@/adapters/memory/types";
import { getPreferences } from "@/core/server-preferences";
import { requireSession } from "@/core/session";
import { forgetDate, forgetFact, forgetMember, saveDate, saveFact, saveMember, startInterview } from "./actions";
import { AboutView } from "./AboutView";

/**
 * About me (Snafi step 6): everything Ahmad knows about Khalid, grouped Me, Family, Preferences and
 * Routine, with Edit and Forget on every item, and "Interview me again". Only Khalid's own rows are read
 * (row-level security); every change goes through the database's save_* and forget_* functions.
 */
export default async function AboutPage() {
  const session = await requireSession();
  const { lang } = await getPreferences();
  let view: MemoryView | null = null;
  let problem: "loadFailed" | "notReady" | null = null;
  try {
    view = await memoryAdapter(session.userId).load();
  } catch (error) {
    problem = error instanceof MemoryError && error.schemaMissing ? "notReady" : "loadFailed";
  }
  return (
    <AboutView lang={lang} view={view} problem={problem}
      actions={{ saveFact, forgetFact, saveMember, forgetMember, saveDate, forgetDate, startInterview }} />
  );
}
