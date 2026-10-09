"use client";

import { SendHorizontal } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const MAX_LENGTH = 1000;

export function ChatComposer({ onSend, disabled }: { onSend: (text: string) => void; disabled?: boolean }) {
  const [text, setText] = useState("");
  const trimmed = text.trim();
  const tooLong = text.length > MAX_LENGTH;

  function send() {
    if (!trimmed || tooLong || disabled) return;
    onSend(trimmed);
    setText("");
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
      className="rounded-xl border bg-card p-2 focus-within:ring-3 focus-within:ring-ring/40"
    >
      <label htmlFor="chat-input" className="sr-only">
        Ask a question about your business
      </label>
      <Textarea
        id="chat-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            send();
          }
        }}
        rows={2}
        placeholder="Ask anything — e.g. “Which customers owe me the most?”"
        className="min-h-12 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 dark:bg-transparent"
        aria-describedby="chat-hint"
        aria-invalid={tooLong || undefined}
      />
      <div className="flex items-center justify-between gap-2 px-1">
        <p id="chat-hint" className={tooLong ? "text-xs text-destructive" : "text-xs text-muted-foreground"}>
          {tooLong
            ? `Please shorten your question (${text.length}/${MAX_LENGTH} characters).`
            : "Enter to send · Shift + Enter for a new line"}
        </p>
        <Button type="submit" size="icon" disabled={!trimmed || tooLong || disabled} aria-label="Send message">
          <SendHorizontal />
        </Button>
      </div>
    </form>
  );
}
