/**
 * DEMO copilot: canned replies until Gemini is integrated. Every reply is flagged isMock
 * and labelled as a demo in the UI.
 */
import type { CopilotApi } from "@/lib/api/contracts";
import { LANGUAGES } from "@/lib/constants";
import { newId } from "@/lib/id";
import type { ChatMessage, LanguageCode } from "@/lib/types";

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const REPLIES: ReadonlyArray<{ match: RegExp; reply: string }> = [
  {
    match: /overdue|pending|due|owe|collect|receiv/i,
    reply:
      "Once connected, I'll list every overdue invoice, group them by customer, and draft polite WhatsApp or email reminders you can send in one tap.",
  },
  {
    match: /gst|tax/i,
    reply:
      "Once connected, I'll summarise GST collected on your sales invoices by rate (5%, 12%, 18%, 28%) for the period you choose, so filing is easier. I won't file returns for you.",
  },
  {
    match: /cash|flow|expense|spend/i,
    reply:
      "Once connected, I'll compare money coming in with money going out each month, and point out the largest or unusual expenses.",
  },
  {
    match: /customer|best|top|sales/i,
    reply:
      "Once connected, I'll rank customers by sales and by how quickly they pay, so you know who to prioritise.",
  },
];

async function mockCopilotReply(message: string, language: LanguageCode): Promise<ChatMessage> {
  await delay(900);
  const hit = REPLIES.find((r) => r.match.test(message));
  const body =
    hit?.reply ??
    "Once connected, I'll answer questions about your sales, payments, expenses and documents, in your preferred language.";
  const lang = LANGUAGES.find((l) => l.value === language);
  const languageNote =
    lang && language !== "en" ? `\n\n(Answers will be translated into ${lang.label} once connected.)` : "";
  return {
    id: newId("msg"),
    role: "assistant",
    content: body + languageNote,
    createdAt: new Date().toISOString(),
    isMock: true,
  };
}

export const mockCopilot: CopilotApi = {
  isMock: true,
  sendMessage: (businessId, { message, language }) => mockCopilotReply(message, language),
};
