import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import MathText from "@/components/common/MathText";
import { apiRequest } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

export interface ChatPanelHandle {
  /** Insert text into the input box (e.g. quoting a passage). */
  insert: (text: string) => void;
}

interface ChatPanelProps {
  subject?: string;
  showSubjectSelector?: boolean;
  emptyTitle?: string;
  emptyHint?: string;
  suggestions?: string[];
  className?: string;
}

const SUBJECTS = [
  { value: "", label: "全部" },
  { value: "chinese", label: "中文" },
  { value: "math", label: "數學" },
  { value: "english", label: "英文" },
];

function SkeletonMessage() {
  return (
    <div className="flex justify-start">
      <div className="glass-card w-72 space-y-3 p-4">
        <div className="skeleton h-3 w-3/4" />
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-2/3" />
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser ? "bg-gradient-primary text-white" : "glass-card text-zinc-200"
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : message.content ? (
          <>
            <MathText text={message.content} />
            {message.isStreaming && (
              <span className="ml-0.5 inline-block animate-cursor-blink text-primary-400">
                ▋
              </span>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}

const ChatPanel = forwardRef<ChatPanelHandle, ChatPanelProps>(function ChatPanel(
  {
    subject: fixedSubject,
    showSubjectSelector = false,
    emptyTitle = "AI 智能導師",
    emptyHint = "歡迎提問任何 DSE 課題問題。數學題會提供步驟提示而非直接答案。",
    suggestions = [],
    className,
  }: ChatPanelProps,
  ref
) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [subject, setSubject] = useState(fixedSubject ?? "");
  const [isLoading, setIsLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const activeSubject = fixedSubject ?? subject;

  useImperativeHandle(ref, () => ({
    insert: (text: string) => {
      setInput((prev) => (prev ? `${prev}\n${text}` : text));
      inputRef.current?.focus();
    },
  }));

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = useCallback(
    async (raw: string) => {
      const query = raw.trim();
      if (!query || isLoading) return;

      const assistantId = `${Date.now()}-a`;
      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-u`, role: "user", content: query },
        { id: assistantId, role: "assistant", content: "", isStreaming: true },
      ]);
      setInput("");
      setIsLoading(true);

      try {
        const response = await apiRequest("/api/chat/stream", {
          method: "POST",
          body: { query, subject: activeSubject || undefined },
        });

        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.error || `HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response stream");
        const decoder = new TextDecoder();
        let accumulated = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });

          for (const line of chunk.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            const data = line.slice(6);
            if (data === "[DONE]") continue;

            let parsed: { text?: string; error?: string };
            try {
              parsed = JSON.parse(data);
            } catch {
              continue; // skip malformed SSE line
            }

            if (parsed.error) throw new Error(parsed.error);
            if (parsed.text) {
              accumulated += parsed.text;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: accumulated } : m
                )
              );
            }
          }
        }
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: `無法取得回覆：${
                    err instanceof Error ? err.message : "請稍後再試。"
                  }`,
                  isStreaming: false,
                }
              : m
          )
        );
      } finally {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isStreaming: false } : m
          )
        );
        setIsLoading(false);
        inputRef.current?.focus();
      }
    },
    [activeSubject, isLoading]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className={cn("flex min-h-0 flex-col", className)}>
      {showSubjectSelector && (
        <div className="mb-4 flex items-center gap-3">
          <span className="text-sm text-zinc-400">學科：</span>
          {SUBJECTS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setSubject(opt.value)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                subject === opt.value
                  ? "bg-primary-500/20 text-primary-400 ring-1 ring-primary-500/30"
                  : "bg-surface-elevated text-zinc-400 hover:text-zinc-200"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto rounded-2xl p-1">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <h3 className="mb-2 text-lg font-semibold text-zinc-200">
              {emptyTitle}
            </h3>
            <p className="max-w-sm text-sm text-zinc-500">{emptyHint}</p>
            {suggestions.length > 0 && (
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-full border border-white/10 bg-surface-elevated px-3 py-1.5 text-xs text-zinc-300 transition-colors hover:border-primary-500/30 hover:text-primary-300"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isLoading && messages[messages.length - 1]?.role !== "assistant" && (
          <SkeletonMessage />
        )}

        <div ref={endRef} />
      </div>

      <div className="mt-4 flex items-end gap-3">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="輸入你的問題…（Enter 發送，Shift+Enter 換行）"
          rows={1}
          className="max-h-40 flex-1 resize-none rounded-xl border border-white/10 bg-surface-card px-4 py-3 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition-colors focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/20"
        />
        <button
          onClick={() => send(input)}
          disabled={!input.trim() || isLoading}
          className="btn-primary disabled:opacity-50"
        >
          發送
        </button>
      </div>
    </div>
  );
});

export default ChatPanel;
