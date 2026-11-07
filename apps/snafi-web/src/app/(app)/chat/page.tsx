import { getPreferences } from "@/core/server-preferences";
import { ChatView } from "./ChatView";

export default async function ChatPage() {
  const { lang } = await getPreferences();
  return <ChatView lang={lang} />;
}
