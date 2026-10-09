import { Bot, FlaskConical, User } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ChatMessage({ message }: { message: ChatMessageType }) {
  const isUser = message.role === "user";
  return (
    <li className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "grid size-8 shrink-0 place-items-center rounded-full",
          isUser ? "bg-muted text-muted-foreground" : "bg-primary text-primary-foreground",
        )}
        aria-hidden
      >
        {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
      </div>
      <div className={cn("max-w-[85%] space-y-1.5 sm:max-w-[75%]", isUser && "items-end text-right")}>
        <span className="sr-only">{isUser ? "You said:" : "VyaparAI said:"}</span>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-left text-sm whitespace-pre-wrap",
            isUser ? "rounded-tr-sm bg-primary text-primary-foreground" : "rounded-tl-sm border bg-card",
          )}
        >
          {message.content}
        </div>
        {message.isMock && (
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <FlaskConical className="size-3 text-brand-accent" aria-hidden />
            Demo reply — the AI isn&apos;t connected yet and can&apos;t see your records.
          </p>
        )}
      </div>
    </li>
  );
}

export function TypingIndicator() {
  return (
    <li className="flex gap-3" aria-label="VyaparAI is typing">
      <div className="grid size-8 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground" aria-hidden>
        <Bot className="size-4" />
      </div>
      <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm border bg-card px-4 py-3" aria-hidden>
        {[0, 150, 300].map((d) => (
          <span key={d} className="size-1.5 animate-bounce rounded-full bg-muted-foreground" style={{ animationDelay: `${d}ms` }} />
        ))}
      </div>
    </li>
  );
}
