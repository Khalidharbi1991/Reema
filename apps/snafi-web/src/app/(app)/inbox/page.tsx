import { isId } from "@/adapters/mailbox/types";
import { AutoRefresh } from "@/components/AutoRefresh";
import { loadToday } from "@/core/today-data";
import { decideApproval, markCardRead } from "../actions";
import { InboxView } from "./InboxView";

/**
 * The Inbox (a full page, Khalid's Q5): pending approvals first, then Ahmad's cards newest first.
 * `/inbox?open=<id>` (from Ahmad's message on Today) opens that item. The id is checked here,
 * on the server: anything that is not one of our ids is dropped and the page draws as usual,
 * with nothing opened, nothing marked read and nothing said (SEC-174).
 */
export default async function InboxPage({ searchParams }: { searchParams: Promise<{ [key: string]: string | string[] | undefined }> }) {
  const { lang, now, today } = await loadToday();
  const { open } = await searchParams;
  return (
    <>
      <AutoRefresh seconds={30} />
      <InboxView lang={lang} now={now.toISOString()} approvals={today.approvals} cards={today.cards}
        open={isId(open) ? open.toLowerCase() : undefined} decide={decideApproval} markRead={markCardRead} />
    </>
  );
}
