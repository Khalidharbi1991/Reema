"use client"; // Error boundaries must be Client Components

import { RouteError } from "@/components/RouteError";

/** Today could not load. The top bar, bell and menu (in the layout) still work. */
export default function TodayError({ retry }: { error: unknown; retry: () => void }) {
  return <RouteError screen="today" retry={retry} />;
}
