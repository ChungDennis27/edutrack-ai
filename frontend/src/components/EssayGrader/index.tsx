import { useState } from "react";
import { apiJson } from "@/lib/api";
import { cn } from "@/lib/utils";

interface GrammarError {
  original: string;
  corrected: string;
  error_type: "grammar" | "vocabulary" | "punctuation" | "spelling" | string;
  explanation: string;
}

interface VocabularyUpgrade {
  original: string;
  upgraded: string;
  context: string;
}

interface GradeResult {
  content_score: number;
  content_feedback: string;
  language_score: number;
  language_feedback: string;
  organization_score: number;
  organization_feedback: string;
  overall_score: number;
  overall_feedback: string;
  grammar_errors?: GrammarError[];
  vocabulary_upgrades?: VocabularyUpgrade[];
  strengths?: string[];
  areas_for_improvement?: string[];
  word_count?: number;
  error?: string;
}

const TASK_TYPES = [
  { value: "argumentative", label: "議論文" },
  { value: "narrative", label: "敘事文" },
  { value: "descriptive", label: "描寫文" },
  { value: "letter", label: "書信" },
  { value: "report", label: "報告" },
];

const ERROR_TYPE_STYLE: Record<string, string> = {
  grammar: "bg-accent-red/15 text-accent-red ring-accent-red/30",
  vocabulary: "bg-secondary-500/15 text-secondary-300 ring-secondary-500/30",
  punctuation: "bg-accent-amber/15 text-accent-amber ring-accent-amber/30",
  spelling: "bg-orange-500/15 text-orange-300 ring-orange-500/30",
};

function DimensionCard({
  label,
  score,
  feedback,
  tone,
  bar,
}: {
  label: string;
  score: number;
  feedback: string;
  tone: string;
  bar: string;
}) {
  const percent = Math.round((Math.min(Math.max(score, 0), 7) / 7) * 100);
  return (
    <div className="glass-card p-5">
      <div className="mb-3 flex items-baseline justify-between">
        <span className="text-sm font-medium text-zinc-300">{label}</span>
        <span className={cn("text-lg font-bold", tone)}>
          {score}
          <span className="text-xs font-normal text-zinc-500">/7</span>
        </span>
      </div>
      <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-surface-elevated">
        <div className={cn("h-full rounded-full", bar)} style={{ width: `${percent}%` }} />
      </div>
      <p className="text-xs leading-relaxed text-zinc-400">{feedback}</p>
    </div>
  );
}

function ResultSkeleton() {
  return (
    <div className="space-y-4">
      <div className="skeleton h-28" />
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="skeleton h-40" />
        <div className="skeleton h-40" />
        <div className="skeleton h-40" />
      </div>
      <div className="skeleton h-52" />
    </div>
  );
}

export default function EssayGrader() {
  const [taskType, setTaskType] = useState("argumentative");
  const [essay, setEssay] = useState("");
  const [result, setResult] = useState<GradeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const wordCount = essay.trim() ? essay.trim().split(/\s+/).length : 0;
  const tooShort = wordCount > 0 && wordCount < 50;

  const grade = async () => {
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const data = await apiJson<GradeResult>("/api/chat/grade-essay", {
        method: "POST",
        body: { essay, task_type: taskType },
      });
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "批改失敗，請稍後再試。");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="animate-fade-in">
      <header className="mb-6">
        <h2 className="text-2xl font-semibold text-zinc-50">英文作文批改</h2>
        <p className="mt-1 text-sm text-zinc-500">
          模擬 HKEAA 閱卷員，按 Content、Language、Organization 三個維度評分並指出文法與用詞問題。
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        {/* Input */}
        <section className="glass-card flex flex-col p-6 lg:sticky lg:top-24 lg:self-start">
          <label className="mb-2 text-sm text-zinc-400">文體</label>
          <div className="mb-4 flex flex-wrap gap-2">
            {TASK_TYPES.map((t) => (
              <button
                key={t.value}
                onClick={() => setTaskType(t.value)}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                  taskType === t.value
                    ? "bg-primary-500/20 text-primary-300 ring-1 ring-primary-500/30"
                    : "bg-surface-elevated text-zinc-400 hover:text-zinc-200"
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          <textarea
            value={essay}
            onChange={(e) => setEssay(e.target.value)}
            placeholder="在此貼上你的 DSE English 作文（至少 50 字）…"
            rows={16}
            className="min-h-[260px] flex-1 resize-y rounded-xl border border-white/10 bg-surface-card px-4 py-3 text-sm leading-relaxed text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/20"
          />

          <div className="mt-3 flex items-center justify-between text-xs text-zinc-500">
            <span className={cn(tooShort && "text-accent-amber")}>
              {wordCount} 字{tooShort && "（建議至少 50 字）"}
            </span>
            <button
              onClick={grade}
              disabled={loading || wordCount < 5}
              className="btn-ai disabled:opacity-50"
            >
              {loading ? "閱卷中…" : "開始批改"}
            </button>
          </div>

          {error && (
            <p
              role="alert"
              className="mt-3 rounded-xl bg-accent-red/10 px-3 py-2 text-sm text-accent-red ring-1 ring-accent-red/20"
            >
              {error}
            </p>
          )}
        </section>

        {/* Results */}
        <section>
          {loading && <ResultSkeleton />}

          {!loading && !result && (
            <div className="glass-card flex h-64 flex-col items-center justify-center p-8 text-center">
              <p className="text-sm text-zinc-500">
                提交作文後，這裡會顯示評分、文法修正與用詞升級建議。
              </p>
            </div>
          )}

          {!loading && result && (
            <div className="space-y-4">
              {/* Overall */}
              <div className="glass-card flex items-center gap-6 p-6">
                <div className="flex h-24 w-24 shrink-0 flex-col items-center justify-center rounded-full bg-gradient-ai text-white">
                  <span className="text-3xl font-bold">{result.overall_score ?? "–"}</span>
                  <span className="text-[10px] opacity-80">/ 21</span>
                </div>
                <div>
                  <p className="text-sm text-zinc-300">{result.overall_feedback}</p>
                  {result.word_count != null && (
                    <p className="mt-1 text-xs text-zinc-500">全文字數：{result.word_count}</p>
                  )}
                </div>
              </div>

              {/* Dimensions */}
              <div className="grid gap-4 sm:grid-cols-3">
                <DimensionCard
                  label="Content 內容"
                  score={result.content_score}
                  feedback={result.content_feedback}
                  tone="text-primary-400"
                  bar="bg-primary-500"
                />
                <DimensionCard
                  label="Language 語言"
                  score={result.language_score}
                  feedback={result.language_feedback}
                  tone="text-secondary-300"
                  bar="bg-secondary-500"
                />
                <DimensionCard
                  label="Organization 組織"
                  score={result.organization_score}
                  feedback={result.organization_feedback}
                  tone="text-emerald-400"
                  bar="bg-emerald-500"
                />
              </div>

              {/* Grammar errors */}
              {!!result.grammar_errors?.length && (
                <div className="glass-card p-6">
                  <h3 className="mb-4 text-sm font-semibold text-zinc-200">
                    文法與拼寫修正（{result.grammar_errors.length}）
                  </h3>
                  <ul className="space-y-3">
                    {result.grammar_errors.map((g, i) => (
                      <li key={i} className="rounded-xl bg-surface-elevated/60 p-4">
                        <div className="mb-2 flex items-center gap-2">
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-[10px] font-medium ring-1",
                              ERROR_TYPE_STYLE[g.error_type] ?? ERROR_TYPE_STYLE.grammar
                            )}
                          >
                            {g.error_type}
                          </span>
                        </div>
                        <p className="text-sm">
                          <span className="text-accent-red line-through">{g.original}</span>
                          <span className="mx-2 text-zinc-600">→</span>
                          <span className="text-emerald-400">{g.corrected}</span>
                        </p>
                        {g.explanation && (
                          <p className="mt-1 text-xs text-zinc-500">{g.explanation}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Vocabulary upgrades */}
              {!!result.vocabulary_upgrades?.length && (
                <div className="glass-card p-6">
                  <h3 className="mb-4 text-sm font-semibold text-zinc-200">
                    高級用詞替換
                  </h3>
                  <ul className="space-y-2">
                    {result.vocabulary_upgrades.map((v, i) => (
                      <li
                        key={i}
                        className="flex flex-wrap items-baseline gap-x-2 gap-y-1 rounded-lg bg-surface-elevated/60 px-4 py-2.5 text-sm"
                      >
                        <span className="text-zinc-400">{v.original}</span>
                        <span className="text-zinc-600">→</span>
                        <span className="font-medium text-secondary-300">{v.upgraded}</span>
                        {v.context && (
                          <span className="w-full text-xs text-zinc-500">{v.context}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Strengths / improvements */}
              <div className="grid gap-4 sm:grid-cols-2">
                {!!result.strengths?.length && (
                  <div className="glass-card p-5">
                    <h3 className="mb-3 text-sm font-semibold text-emerald-400">優點</h3>
                    <ul className="space-y-1.5 text-xs text-zinc-300">
                      {result.strengths.map((s, i) => (
                        <li key={i}>· {s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {!!result.areas_for_improvement?.length && (
                  <div className="glass-card p-5">
                    <h3 className="mb-3 text-sm font-semibold text-accent-amber">改善方向</h3>
                    <ul className="space-y-1.5 text-xs text-zinc-300">
                      {result.areas_for_improvement.map((s, i) => (
                        <li key={i}>· {s}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
