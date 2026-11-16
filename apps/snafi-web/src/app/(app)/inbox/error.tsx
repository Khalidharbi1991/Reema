"use client"; // Error boundaries must be Client Components

import { RouteError } from "@/components/RouteError";

export default function InboxError({ retry }: { error: unknown; retry: () => void }) {
  return <RouteError screen="inbox" retry={retry} />;
}
