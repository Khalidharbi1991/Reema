// Starts the development server in preview mode on this PC only, for looking at the screens and
// taking screenshots with sample data. It blanks the Supabase settings for this one process, so
// .env.local is not used, sign-in is skipped and the in-memory mailbox with sample content is shown.
// It never touches .env.local and makes no outside call. Not for production (SEC-74 still refuses
// the in-memory stand-ins there).
import { spawn } from "node:child_process";

const env = {
  ...process.env,
  NEXT_PUBLIC_SUPABASE_URL: "",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "",
  SNAFI_MAILBOX_ADAPTER: "",
  SNAFI_TODAY_ADAPTER: "",
  SNAFI_THROTTLE_ADAPTER: "",
};
const child = spawn("npx", ["next", "dev", "--hostname", "127.0.0.1", "--port", "3100"], {
  env, stdio: "inherit", shell: true,
});
child.on("exit", (code) => process.exit(code ?? 0));
