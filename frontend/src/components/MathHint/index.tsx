import { useState } from "react";
import MarkdownMath from "@/components/common/MarkdownMath";
import { apiJson } from "@/lib/api";

interface Hint {
  hint_number: number;
  hint_text: string;
  method_mark_target?: string;
  encouragement?: string;
  is_final_hint?: boolean;
  next_step_question?: string;
}

interface HintResponse extends Partial<Hint> {
  error?: string;
}

const TOPIC_SUGGESTIONS = ["二次方程", "微積分", "三角學", "概率", "數列"];

export default function MathHint() {
  const [problem, setProblem] = useState("");
  const [topic, setTopic] = useState("");
  const [studentWork, setStudentWork] = useState("");
  const [hints, setHints] = useState<Hint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const solved = hints.length > 0 && hints[hints.length - 1].is_final_hint;

  const requestHint = async () => {
    if (!problem.trim()) {
      setError("請先輸入題目。");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const data = await apiJson<HintResponse>("/api/chat/math-hint", {
        method: "POST",
        body: {
          problem,
          student_work: studentWork,
          hint_history: hints.map((h) => h.hint_text),
          topic,
        },
      });
      if (data.error) throw new Error(data.error);
      setHints((prev) => [
        ...prev,
        {
          hint_number: data.hint_number ?? prev.length + 1,
          hint_text: data.hint_text ?? "",
          method_mark_target: data.method_mark_target,
          encouragement: data.encouragement,
          is_final_hint: data.is_final_hint,
          next_step_question: data.next_step_question,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法取得提示，請稍後再試。");
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setHints([]);
    setStudentWork("");
    setError("");
  };

  return (
    <div className="animate-fade-in">
      <header className="mb-6">
        <h2 className="text-2xl font-semibold text-zinc-50">數學解題引導</h2>
        <p className="mt-1 text-sm text-zinc-500">
          依照考評局「步驟分（Method Marks）」機制，逐步給出提示，引導你自己運算而非直接給答案。
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        {/* Inputs */}
        <section className="glass-card space-y-4 p-6 lg:sticky lg:top-24 lg:self-start">
          <div>
            <label className="mb-2 block text-sm text-zinc-400">題目（支援 LaTeX）</label>
            <textarea
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              placeholder="例如：解方程 $x^2 - 5x + 6 = 0$，並求兩根之和。"
              rows={4}
              className="w-full resize-y rounded-xl border border-white/10 bg-surface-card px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/20"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm text-zinc-400">課題（可選）</label>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="例如：二次方程"
              className="w-full rounded-xl border border-white/10 bg-surface-card px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-primary-500/50"
            />
            <div className="mt-2 flex flex-wrap gap-2">
              {TOPIC_SUGGESTIONS.map((t) => (
                <button
                  key={t}
                  onClick={() => setTopic(t)}
                  className="rounded-full bg-surface-elevated px-2.5 py-1 text-[11px] text-zinc-400 transition-colors hover:text-zinc-200"
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-2 block text-sm text-zinc-400">你的目前做法（可選）</label>
            <textarea
              value={studentWork}
              onChange={(e) => setStudentWork(e.target.value)}
              placeholder="寫下你已嘗試的步驟，AI 會針對你的進度給下一個提示。"
              rows={3}
              className="w-full resize-y rounded-xl border border-white/10 bg-surface-card px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-primary-500/50"
            />
          </div>

          {error && (
            <p
              role="alert"
              className="rounded-xl bg-accent-red/10 px-3 py-2 text-sm text-accent-red ring-1 ring-accent-red/20"
            >
              {error}
            </p>
          )}

          <div className="flex gap-3">
            <button
              onClick={requestHint}
              disabled={loading || solved}
              className="btn-ai flex-1 disabled:opacity-50"
            >
              {loading
                ? "思考中…"
                : hints.length === 0
                  ? "取得第一個提示"
                  : solved
                    ? "已完成引導"
                    : "下一個提示"}
            </button>
            {hints.length > 0 && (
              <button
                onClick={reset}
                className="rounded-xl bg-surface-elevated px-4 py-2 text-sm text-zinc-400 transition-colors hover:text-zinc-200"
              >
                重設
              </button>
            )}
          </div>
        </section>

        {/* Hint timeline */}
        <section className="space-y-4">
          {hints.length === 0 && !loading && (
            <div className="glass-card flex h-64 flex-col items-center justify-center p-8 text-center">
              <p className="text-sm text-zinc-500">
                輸入題目後按「取得第一個提示」。每個提示對應一個步驟分，逐步推進。
              </p>
            </div>
          )}

          {hints.map((hint) => (
            <article key={hint.hint_number} className="glass-card relative p-6 pl-8">
              <span className="absolute left-0 top-6 h-[calc(100%-3rem)] w-0.5 bg-gradient-ai" />
              <div className="mb-3 flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-ai text-xs font-bold text-white">
                  {hint.hint_number}
                </span>
                <span className="text-xs text-zinc-500">提示 {hint.hint_number}</span>
                {hint.method_mark_target && (
                  <span className="ml-auto rounded-full bg-secondary-500/15 px-2.5 py-0.5 text-[11px] text-secondary-300 ring-1 ring-secondary-500/30">
                    {hint.method_mark_target}
                  </span>
                )}
              </div>

              <MarkdownMath
                text={hint.hint_text}
                className="text-sm leading-relaxed text-zinc-200"
              />

              {hint.next_step_question && (
                <div className="mt-4 rounded-xl bg-surface-elevated/70 px-4 py-3">
                  <p className="mb-1 text-[11px] text-zinc-500">想一想</p>
                  <MarkdownMath
                    text={hint.next_step_question}
                    className="text-sm text-primary-300"
                  />
                </div>
              )}

              {hint.encouragement && (
                <p className="mt-3 text-xs text-emerald-400">{hint.encouragement}</p>
              )}

              {hint.is_final_hint && (
                <p className="mt-4 text-xs text-accent-amber">
                  已到最後一步提示，試著自己完成餘下運算。
                </p>
              )}
            </article>
          ))}

          {loading && <div className="skeleton h-32" />}
        </section>
      </div>
    </div>
  );
}
