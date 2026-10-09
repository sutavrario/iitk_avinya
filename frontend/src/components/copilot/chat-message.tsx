import { AlertTriangle, Bot, CheckCircle2, FileText, FlaskConical, User } from "lucide-react";
import ReactMarkdown from "react-markdown";
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
            "rounded-2xl px-4 py-2.5 text-left text-sm",
            isUser ? "rounded-tr-sm bg-primary text-primary-foreground" : "rounded-tl-sm border bg-card",
            "[&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:ml-4 [&_ul]:mb-2 [&_li]:mb-1 [&_strong]:font-semibold"
          )}
        >
          {isUser ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          )}
        </div>
        
        {message.caveats && message.caveats.length > 0 && (
          <div className="rounded-md bg-amber-500/10 p-3 text-sm text-amber-600 dark:text-amber-400">
            <div className="flex items-center gap-2 font-medium mb-1">
              <AlertTriangle className="size-4" /> Keep in mind
            </div>
            <ul className="list-disc pl-5 space-y-1">
              {message.caveats.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        {message.recommendedActions && message.recommendedActions.length > 0 && (
          <div className="rounded-md bg-primary/10 p-3 text-sm text-primary">
            <div className="flex items-center gap-2 font-medium mb-1">
              <CheckCircle2 className="size-4" /> Recommended Actions
            </div>
            <ul className="list-disc pl-5 space-y-1">
              {message.recommendedActions.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          </div>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="text-xs text-muted-foreground mt-2">
            <div className="font-medium mb-1 flex items-center gap-1"><FileText className="size-3"/> Sources:</div>
            <div className="flex flex-wrap gap-2">
              {message.sources.map((s: Record<string, unknown>, i) => (
                <span key={i} className="inline-flex items-center rounded bg-muted px-2 py-0.5">
                  {s.fileName} {s.page ? `(Page ${s.page})` : s.sheetName ? `(Sheet: ${s.sheetName})` : ''}
                </span>
              ))}
            </div>
          </div>
        )}
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
