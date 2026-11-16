/**
 * The no-secrets rule for memory (Khalid, Nov 16, 2026): never store passwords, ID numbers or card
 * numbers. The same rule as public.snafi_memory_ok (migration 0010, which the database enforces on every
 * memory row) and the worker's memory/guard.py; tests/fixtures/snafi_memory_guard.json is checked by all
 * three. Here it only gives Khalid a clear message before the database refuses.
 */

const DIGITS: Record<string, string> = Object.fromEntries(
  [..."٠١٢٣٤٥٦٧٨٩"].map((d, i) => [d, String(i)]).concat([..."۰۱۲۳۴۵۶۷۸۹"].map((d, i) => [d, String(i)])),
);
const LETTERS: Record<string, string> = { "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي" };
const MARKS = /[ً-ٰٟـ]/g;

/** أإآٱ -> ا, ة -> ه, ى -> ي, Arabic-Indic digits -> 0-9, no tashkeel or tatweel, lower case. */
export function normalise(text: string): string {
  return [...(text ?? "")].map((c) => LETTERS[c] ?? DIGITS[c] ?? c).join("").replace(MARKS, "").toLowerCase();
}

const LONG_NUMBER = /[0-9](?:[ .-]?[0-9]){8,}/;
const EN_WORDS = new RegExp(
  "(^|[^a-z0-9_])(password|passwords|passcode|passwd|pin|pins|otp|cvv|cvc|iban|iqama|token|secret|api key|card number"
  + "|card no|credit card|debit card|id number|national id|passport number|passport no|security code"
  + "|verification code|login code)(?![a-z0-9_])",
);
const AR_WORDS = new RegExp(
  "(كلمه المرور|كلمه السر|كلمات المرور|الرقم السري|الرمز السري|رمز التحقق|رمز الدخول|رقم الهويه"
  + "|الهويه الوطنيه|رقم الاقامه|رقم الجواز|رقم البطاقه|البطاقه الائتمانيه|رقم الحساب|الايبان|ايبان)",
);

export type Refusal = "number" | "secret";

export function memoryRefusal(text: string): Refusal | null {
  const norm = normalise(text);
  if (LONG_NUMBER.test(norm)) return "number";
  if (EN_WORDS.test(norm) || AR_WORDS.test(norm)) return "secret";
  return null;
}
