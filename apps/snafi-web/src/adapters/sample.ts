/**
 * Sample content for preview mode and the placeholder Today source, so Today, the Inbox and Chat
 * can be looked at on this PC without Supabase. Invented data only: no real person, mailbox or event.
 */
import type { AhmadCard, ApprovalCard, MailboxMessage, TodayFeed } from "./mailbox/types";

const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const at = (now: Date, deltaMs: number) => new Date(now.getTime() + deltaMs).toISOString();

export const SAMPLE_LONG_WORD = "Sample".padEnd(200, "LongUnbrokenWord");
export const SAMPLE_LONG_URL = `https://example.com/sample/${"very-long-path-segment/".repeat(8)}index.html?ref=snafi`;

export function sampleApprovals(conversationId: string, now: Date): ApprovalCard[] {
  return [{
    id: id(101), conversationId, tool: "send_test_message",
    args: { to: "sample.person@example.com", subject: "Sample: running late", body: "Sample: I will be there by 4:30." },
    argsHash: "a".repeat(64), summary: "Sample: send this email to the sample contact?", status: "pending",
    createdAt: at(now, -20 * MIN), expiresAt: at(now, DAY),
  }];
}

export function sampleCards(now: Date): AhmadCard[] {
  return [
    { id: id(201), kind: "reminder", title: "Sample: call the contractor about the tiles",
      body: "Sample: ask about the delivery date and the grout colour.", createdAt: at(now, -10 * MIN), readAt: null },
    { id: id(202), kind: "brief", title: "Sample: morning brief",
      body: "Sample: 2 events today. First: site visit. Top task: review the SOP draft.", createdAt: at(now, -3 * HOUR), readAt: null },
    { id: id(203), kind: "mail", title: "Sample sender", body: "Sample: drawings for review", createdAt: at(now, -40 * MIN), readAt: null },
    { id: id(204), kind: "test", title: "Sample: test notification", body: "Sample: push works.", createdAt: at(now, -DAY), readAt: null },
    { id: id(205), kind: "reminder", title: "نموذج: تجديد استمارة السيارة", body: "نموذج: الموعد يوم الخميس.",
      createdAt: at(now, -2 * DAY), readAt: at(now, -DAY) },
  ];
}

export function sampleFeed(now: Date): TodayFeed {
  return {
    nextEvent: { title: "Sample: site visit with the architect", start: at(now, 90 * MIN), end: at(now, 150 * MIN),
      location: "Sample place", allDay: false },
    emails: [],
    tasks: [
      { content: "Sample: review the patching SOP draft", due: "", priority: 1, overdue: false, recurring: false },
      { content: "Sample: call the contractor", due: "", priority: 2, overdue: true, recurring: false },
      { content: "Sample: renew car registration", due: "", priority: 3, overdue: false, recurring: false },
      { content: "Sample: book the car service", due: "", priority: 4, overdue: false, recurring: false },
      { content: "Sample: water the plants", due: "", priority: 4, overdue: false, recurring: true },
    ],
    googleStatus: "ok", yahooStatus: "ok", todoistStatus: "ok", updatedAt: now.toISOString(),
  };
}

export function sampleMessages(userId: string, conversationId: string, now: Date): MailboxMessage[] {
  const say = (n: number, role: MailboxMessage["role"], body: string, lang: "en" | "ar", minutesAgo: number,
    approvalId: string | null = null): MailboxMessage => ({
    id: id(300 + n), userId, conversationId, role, body, lang, jobId: null, approvalId,
    meta: approvalId ? { kind: "approval_card" } : {}, createdAt: at(now, -minutesAgo * MIN),
  });
  return [
    say(1, "user", "Sample: what is on today?", "en", 60),
    say(2, "assistant", "Sample: a site visit this afternoon, and three tasks due.", "en", 59),
    say(3, "user", "نموذج: ذكّرني بالاتصال بالمقاول", "ar", 45),
    say(4, "assistant", "نموذج: تم. سأذكّرك قبل الموعد.", "ar", 44),
    say(5, "user", `Sample link: ${SAMPLE_LONG_URL}`, "en", 30),
    say(6, "assistant", SAMPLE_LONG_WORD, "en", 29),
    say(7, "user", "Sample: tell the sample contact I will be late.", "en", 21),
    say(8, "assistant", "Sample: send this email to the sample contact?", "en", 20, id(101)),
  ];
}
