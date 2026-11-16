// Starts the development server in preview mode on this PC only, for looking at the screens and
// taking screenshots with sample data. It blanks the Supabase, mailbox, Today and throttle settings
// for this one process, so sign-in is skipped and the in-memory mailbox with sample content is
// shown; Next still loads every other value in .env.local (the site address, the push public key
// and so on). It never changes .env.local and makes no outside call: Next is run from the copy
// already installed here, never fetched. Not for production (SEC-74 still refuses the in-memory
// stand-ins there).
import { spawn } from "node:child_process";
import { createRequire } from "node:module";

let next;
try {
  next = createRequire(import.meta.url).resolve("next/dist/bin/next");
} catch {
  console.error("next is not installed here. Run `npm install` in apps/snafi-web, then try again.");
  process.exit(1);
}

const env = {
  ...process.env,
  NEXT_PUBLIC_SUPABASE_URL: "",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "",
  SNAFI_MAILBOX_ADAPTER: "",
  SNAFI_TODAY_ADAPTER: "",
  SNAFI_THROTTLE_ADAPTER: "",
};
const child = spawn(process.execPath, [next, "dev", "--hostname", "127.0.0.1", "--port", "3100"], {
  env, stdio: "inherit",
});
child.on("exit", (code) => process.exit(code ?? 0));
