/**
 * Stand-in for Next's `server-only` marker, which only Next's bundler resolves. Aliased in
 * vitest.config.ts so server modules (the Supabase mailbox, for one) can be unit-tested.
 * It does nothing: the real guard still runs in the build.
 */
export {};
