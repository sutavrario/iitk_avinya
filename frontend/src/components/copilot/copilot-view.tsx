"use client";

import { Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { ChatComposer } from "@/components/copilot/chat-composer";
import { ChatMessage, TypingIndicator } from "@/components/copilot/chat-message";
import { PageHeader } from "@/components/layout/page-header";
import { useActiveBusiness } from "@/components/providers/workspace-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { newId } from "@/lib/id";
import { LANGUAGES } from "@/lib/constants";
import type { ChatMessage as ChatMessageType, LanguageCode } from "@/lib/types";

const SUGGESTIONS = [
  "Which customers owe me the most money?",
  "How did my sales this month compare to last month?",
  "Summarise the GST I collected last quarter",
  "Where am I spending the most?",
];

export function CopilotView() {
  const business = useActiveBusiness();
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [language, setLanguage] = useState<LanguageCode>("en");
  const [conversationId, setConversationId] = useState<string | undefined>();
  const endRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  useEffect(() => {
    // Falls back to English if preferences can't be loaded.
    api.preferences.get().then((p) => setLanguage(p.copilotLanguage), () => undefined);
  }, [pathname]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending]);

  async function send(text: string) {
    const userMsg: ChatMessageType = { id: newId("msg"), role: "user", content: text, createdAt: new Date().toISOString() };
    const history = [...messages, userMsg];
    setMessages(history);
    setPending(true);
    setError(null);
    try {
      const reply = await api.copilot.sendMessage(business.id, { 
          message: text, 
          history: messages, 
          language,
          conversationId
      });
      // @ts-expect-error - reply does not guarantee conversationId exists, temporary fix
      if (reply.conversationId) setConversationId(reply.conversationId);
      setMessages([...history, reply]);
    } catch {
      setError("The copilot couldn't answer right now. Please try again.");
    } finally {
      setPending(false);
    }
  }

  const languageLabel = LANGUAGES.find((l) => l.value === language)?.label ?? "English";

  return (
    <div className="flex h-[calc(100dvh-8rem)] min-h-[32rem] flex-col gap-4 lg:h-[calc(100dvh-10rem)]">
      <PageHeader
        title="AI Copilot"
        description="Ask questions about your sales, payments and expenses in plain words."
        actions={
          <Badge variant="outline" className="h-7 px-3">
            Replies in {languageLabel}
          </Badge>
        }
      />

      <div className="flex-1 overflow-y-auto rounded-xl border bg-muted/30 p-4" aria-label="Conversation">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-4 grid size-12 place-items-center rounded-full bg-primary/10 text-primary">
              <Sparkles className="size-6" aria-hidden />
            </div>
            <h2 className="font-medium">What would you like to know?</h2>
            <p className="mt-1 max-w-md text-sm text-muted-foreground">
              Ask about your business metrics, invoices, expenses, or uploaded documents.
            </p>
            <ul className="mt-6 grid w-full max-w-2xl gap-2 sm:grid-cols-2" aria-label="Suggested questions">
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <Button
                    variant="outline"
                    className="h-auto w-full justify-start py-2.5 text-left whitespace-normal"
                    onClick={() => void send(s)}
                  >
                    {s}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <ol className="space-y-5" aria-live="polite" aria-relevant="additions">
            {messages.map((m) => (
              <ChatMessage key={m.id} message={m} />
            ))}
            {pending && <TypingIndicator />}
          </ol>
        )}
        <div ref={endRef} />
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <ChatComposer onSend={(t) => void send(t)} disabled={pending} />
    </div>
  );
}
