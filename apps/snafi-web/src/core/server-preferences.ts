import "server-only";
import { cookies } from "next/headers";
import { readPreferences } from "./preferences";

export async function getPreferences() {
  const store = await cookies();
  return readPreferences((name) => store.get(name)?.value);
}
