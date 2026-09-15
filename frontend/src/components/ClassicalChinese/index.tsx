import { useEffect, useMemo, useRef, useState } from "react";
import ChatPanel, { ChatPanelHandle } from "@/components/common/ChatPanel";
import { apiJson } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Paragraph {
  original: string;
  translation: string;
  notes: string;
}

interface ClassicalText {
  id: string;
  title: string;
  author: string;
  source: string;
  dynasty: string;
  rhetoric: string;
  exam_tips: string;
  paragraphs: Paragraph[];
}

export default function ClassicalChinese() {
  const [texts, setTexts] = useState<ClassicalText[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [highlighted, setHighlighted] = useState<Set<number>>(new Set());
  const [showTranslation, setShowTranslation] = useState(true);
  const [loading, setLoading] = useState(true);
  const chatRef = useRef<ChatPanelHandle>(null);

  useEffect(() => {
    apiJson<{ texts: ClassicalText[] }>("/api/chat/classical-texts")
      .then((data) => {
        setTexts(data.texts);
        if (data.texts.length > 0) setSelectedId(data.texts[0].id);
      })
      .catch(() => setTexts([]))
      .finally(() => setLoading(false));
  }, []);

  const current = useMemo(
    () => texts.find((t) => t.id === selectedId),
    [texts, selectedId]
  );

  const selectText = (id: string) => {
    setSelectedId(id);
    setHighlighted(new Set());
  };

  const toggleHighlight = (index: number) => {
    setHighlighted((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const quote = (paragraph: Paragraph) => {
    chatRef.current?.insert(`關於「${paragraph.original}」：`);
  };

  const suggestions = current
    ? [
        `《${current.title}》的核心思想是什麼？`,
        `解釋「${current.paragraphs[0]?.original.slice(0, 12)}…」的字詞義`,
        `${current.title} 的修辭手法與考核重點`,
      ]
    : [];

  if (loading) {
    return (
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="skeleton h-[70vh]" />
        <div className="skeleton h-[70vh]" />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-50">文言文精讀</h2>
          <p className="mt-1 text-sm text-zinc-500">
            對照原文與譯文，點擊段落高亮，並讓 AI 引用考評局標準逐句講解。
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={selectedId}
            onChange={(e) => selectText(e.target.value)}
            className="rounded-xl border border-white/10 bg-surface-card px-3 py-2 text-sm text-zinc-200 outline-none focus:border-primary-500/50"
          >
            {texts.map((t) => (
              <option key={t.id} value={t.id}>
                {t.title}
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowTranslation((v) => !v)}
            className={cn(
              "rounded-xl px-3 py-2 text-xs font-medium transition-colors",
              showTranslation
                ? "bg-primary-500/20 text-primary-300 ring-1 ring-primary-500/30"
                : "bg-surface-elevated text-zinc-400 hover:text-zinc-200"
            )}
          >
            譯文
          </button>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: original text */}
        <section className="glass-card max-h-[calc(100vh-13rem)] overflow-y-auto p-6">
          {current && (
            <>
              <div className="mb-5 border-b border-white/10 pb-4">
                <h3 className="text-lg font-semibold text-zinc-100">{current.title}</h3>
                <p className="mt-1 text-xs text-zinc-500">
                  {current.dynasty} · {current.author} · {current.source}
                </p>
              </div>

              <div className="space-y-4">
                {current.paragraphs.map((p, i) => (
                  <div
                    key={i}
                    onClick={() => toggleHighlight(i)}
                    className={cn(
                      "cursor-pointer rounded-xl border p-4 transition-colors",
                      highlighted.has(i)
                        ? "border-primary-500/40 bg-primary-500/10"
                        : "border-transparent hover:border-white/10 hover:bg-white/5"
                    )}
                  >
                    <p className="whitespace-pre-wrap text-base leading-loose tracking-wide text-zinc-100">
                      {p.original}
                    </p>

                    {showTranslation && (
                      <p className="mt-3 border-l-2 border-secondary-500/40 pl-3 text-sm leading-relaxed text-zinc-400">
                        {p.translation}
                      </p>
                    )}
                    {p.notes && (
                      <p className="mt-2 text-xs text-zinc-500">註：{p.notes}</p>
                    )}

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        quote(p);
                      }}
                      className="mt-3 rounded-lg bg-surface-elevated px-2.5 py-1 text-[11px] text-zinc-400 transition-colors hover:text-secondary-300"
                    >
                      引用此段問 AI
                    </button>
                  </div>
                ))}
              </div>

              <div className="mt-6 space-y-3 border-t border-white/10 pt-4 text-xs text-zinc-500">
                <p>
                  <span className="text-zinc-400">修辭：</span>
                  {current.rhetoric}
                </p>
                <p>
                  <span className="text-zinc-400">考核重點：</span>
                  {current.exam_tips}
                </p>
              </div>
            </>
          )}
        </section>

        {/* Right: AI tutor scoped to Chinese */}
        <ChatPanel
          ref={chatRef}
          subject="chinese"
          emptyTitle="文言文 AI 導師"
          emptyHint="點擊左邊段落旁的「引用此段問 AI」，或直接輸入問題。回答會對照 HKEAA 評分標準。"
          suggestions={suggestions}
          className="glass-card h-[calc(100vh-13rem)] p-6"
        />
      </div>
    </div>
  );
}
