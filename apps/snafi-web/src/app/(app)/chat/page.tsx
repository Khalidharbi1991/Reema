import { AutoRefresh } from "@/components/AutoRefresh";
import { getPreferences } from "@/core/server-preferences";
import { conversationId, mailboxFor, requireSession } from "@/core/session";
import { decideApproval, sendMessage, undoAction } from "../actions";
import { ChatView } from "./ChatView";

export default async function ChatPage() {
  const session = await requireSession();
  const { lang } = await getPreferences();
  const mailbox = mailboxFor(session);
  const messages = await mailbox.listMessages(conversationId(session), 60);
  const cardIds = messages.map((m) => m.approvalId).filter((id): id is string => !!id);
  const actionIds = messages.flatMap((m) => m.meta.actions ?? []);
  const [cards, actions] = await Promise.all([mailbox.approvals(cardIds), mailbox.actions(actionIds)]);
  return (
    <>
      <AutoRefresh seconds={3} />
      <ChatView lang={lang} messages={messages} preview={session.preview}
        cards={Object.fromEntries(cards.map((c) => [c.id, c]))}
        actions={Object.fromEntries(actions.map((a) => [a.id, a]))}
        decide={decideApproval} undo={undoAction} send={sendMessage} />
    </>
  );
}
