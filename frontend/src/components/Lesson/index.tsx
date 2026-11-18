import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import MarkdownMath from "@/components/common/MarkdownMath";
import { ApiError, apiJson } from "@/lib/api";
import { cn } from "@/lib/utils";

interface KnowledgePointRef {
  id: number;
  name_zh: string;
  topic: string;
  subject?: string;
}

interface LessonSource {
  id: string;
  subject: string | null;
  relevance: number;
  preview: string;
}

interface CheckQuestion {
  id: number;
  index: number;
  stem: string;
  options: Record<string, string>;
}

interface ReadyLesson {
  status: "ready";
  id: number;
  duration_minutes: number;
  knowledge_point: KnowledgePointRef;
  objective: string;
  explanation: string;
  example: {
    prompt: string;
    steps: string[];
    withheld: boolean;
  };
  sources: LessonSource[];
  attempt_id: number | null;
  attempt_status: string | null;
  questions: CheckQuestion[];
}

interface InsufficientLesson {
  status: "insufficient";
  message: string;
  knowledge_point: KnowledgePointRef;
}

interface CheckResult {
  question_id: number;
  stem: string;
  options: Record<string, string>;
  correct_answer: string;
  user_answer: string;
  is_correct: boolean;
  explanation: string;
}

interface QuizResults {
  score_percent: number;
  correct_count: number;
  total_questions: number;
  results: CheckResult[];
}

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

export default function Lesson() {
  const [params] = useSearchParams();
  const kpParam = params.get("kp");
  const kpInvalid = kpParam !== null && !/^\d+$/.test(kpParam);
  const knowledgePointId = kpParam && /^\d+$/.test(kpParam) ? Number(kpParam) : null;

  const [lesson, setLesson] = useState<ReadyLesson | null>(null);
  const [insufficient, setInsufficient] = useState("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [shownSteps, setShownSteps] = useState(1);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [startedAt, setStartedAt] = useState(() => Date.now());
  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState<QuizResults | null>(null);

  const applyPayload = useCallback((payload: ReadyLesson | InsufficientLesson) => {
    if (payload.status === "insufficient") {
      setLesson(null);
      setResults(null);
      setInsufficient(payload.message);
      return;
    }
    setInsufficient("");
    setLesson(payload);
    setShownSteps(1);
    setStartedAt(Date.now());
  }, []);

  const loadLatest = useCallback(async () => {
    const query =
      knowledgePointId === null ? "" : `?knowledge_point_id=${knowledgePointId}`;
    try {
      const payload = await apiJson<ReadyLesson>(`/api/lessons/latest${query}`);
      applyPayload(payload);
      if (payload.attempt_status === "completed" && payload.attempt_id) {
        const saved = await apiJson<QuizResults>(
          `/api/quiz/attempt/${payload.attempt_id}/results`
        );
        setResults(saved);
      } else {
        setResults(null);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setLesson(null);
        setResults(null);
      } else {
        setError(errorText(err, "未能載入課堂"));
      }
    }
  }, [applyPayload, knowledgePointId]);

  useEffect(() => {
    if (kpInvalid) {
      setLesson(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    setInsufficient("");
    loadLatest().finally(() => setLoading(false));
  }, [kpInvalid, loadLatest]);

  const generate = async (fresh: boolean) => {
    setGenerating(true);
    setError("");
    try {
      const payload = await apiJson<ReadyLesson | InsufficientLesson>("/api/lessons", {
        method: "POST",
        body: {
          ...(knowledgePointId === null ? {} : { knowledge_point_id: knowledgePointId }),
          ...(fresh ? { fresh: true } : {}),
        },
      });
      applyPayload(payload);
      if (payload.status === "ready" && payload.attempt_status === "completed" && payload.attempt_id) {
        const saved = await apiJson<QuizResults>(
          `/api/quiz/attempt/${payload.attempt_id}/results`
        );
        setResults(saved);
      } else {
        setResults(null);
        setAnswers({});
      }
    } catch (err) {
      setError(errorText(err, "未能生成課堂"));
    } finally {
      setGenerating(false);
    }
  };

  const submitChecks = async () => {
    if (!lesson?.attempt_id) return;
    const missing = lesson.questions.some((question) => !answers[String(question.id)]);
    if (missing) {
      setError("請先答完檢查題。");
      return;
    }
    setSubmitting(true);
    setError("");
    const elapsed = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
    const perQuestion = Math.max(1, Math.round(elapsed / lesson.questions.length));
    const timePerQuestion = Object.fromEntries(
      lesson.questions.map((question) => [String(question.id), perQuestion])
    );
    try {
      await apiJson("/api/quiz/submit", {
        method: "POST",
        body: {
          attempt_id: lesson.attempt_id,
          answers,
          time_per_question: timePerQuestion,
        },
      });
      const saved = await apiJson<QuizResults>(
        `/api/quiz/attempt/${lesson.attempt_id}/results`
      );
      setResults(saved);
      setLesson({ ...lesson, attempt_status: "completed" });
    } catch (err) {
      setError(errorText(err, "未能提交檢查題"));
    } finally {
      setSubmitting(false);
    }
  };

  const steps = lesson?.example.steps ?? [];
  const visibleSteps = lesson?.example.withheld ? steps.slice(0, shownSteps) : steps;

  return (
    <div className="mx-auto max-w-3xl animate-fade-in space-y-6">
      <header>
        <h2 className="text-2xl font-semibold text-zinc-50">弱項微課堂</h2>
        <p className="mt-1 max-w-2xl text-sm text-zinc-500">
          約 5 分鐘。只會用資料庫入面的 DSE 筆記，不會自由生成其他課題。數學例題只給步驟提示。
          檢查題會計入現有測驗紀錄。
        </p>
      </header>

      {kpInvalid && (
        <p className="rounded-xl border border-accent-red/30 bg-accent-red/10 px-4 py-3 text-sm text-accent-red">
          知識點編號不正確。請由分析頁重新進入。
        </p>
      )}

      {loading && <div className="skeleton h-40 w-full" />}

      {!loading && !kpInvalid && !lesson && !insufficient && (
        <section className="glass-card p-6">
          <h3 className="text-lg font-semibold text-zinc-100">
            {knowledgePointId === null ? "用最低分知識點上課" : "用分析頁揀定的弱項上課"}
          </h3>
          <p className="mt-2 text-sm text-zinc-400">
            如果筆記不夠，系統會直接話資料不足，不會硬作評分標準或試題。
          </p>
          <button
            type="button"
            onClick={() => void generate(false)}
            disabled={generating}
            className="btn-primary mt-5 disabled:opacity-50"
          >
            {generating ? "準備中…" : "開始課堂"}
          </button>
        </section>
      )}

      {insufficient && (
        <section className="rounded-xl border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-sm text-amber-200">
          <p>{insufficient}</p>
          <Link to="/dashboard" className="mt-3 inline-block text-xs text-amber-100 underline-offset-2 hover:underline">
            返回分析
          </Link>
        </section>
      )}

      {error && (
        <p className="rounded-xl border border-accent-red/30 bg-accent-red/10 px-4 py-3 text-sm text-accent-red">
          {error}
        </p>
      )}

      {lesson && (
        <>
          <section className="glass-card p-6">
            <p className="text-xs text-zinc-500">
              {lesson.knowledge_point.topic} · 約 {lesson.duration_minutes} 分鐘
            </p>
            <h3 className="mt-1 text-xl font-semibold text-zinc-50">
              {lesson.knowledge_point.name_zh}
            </h3>
            <p className="mt-4 text-sm leading-relaxed text-zinc-200">{lesson.objective}</p>
          </section>

          <section className="glass-card p-6">
            <h3 className="mb-3 text-sm font-semibold text-zinc-300">概念講解</h3>
            <MarkdownMath text={lesson.explanation} className="text-sm leading-relaxed text-zinc-200" />
            {lesson.sources.length > 0 && (
              <div className="mt-4 space-y-2">
                <p className="text-xs text-zinc-500">引用的 DSE 筆記</p>
                {lesson.sources.map((source, index) => (
                  <p key={source.id || index} className="text-xs leading-relaxed text-zinc-500">
                    資料 {index + 1}
                    {source.subject ? ` · ${source.subject}` : ""} · 相關度 {source.relevance.toFixed(2)}
                    <span className="mt-1 block text-zinc-400">{source.preview}</span>
                  </p>
                ))}
              </div>
            )}
          </section>

          <section className="glass-card p-6">
            <h3 className="mb-3 text-sm font-semibold text-zinc-300">
              {lesson.example.withheld ? "例題提示" : "例題"}
            </h3>
            <MarkdownMath text={lesson.example.prompt} className="text-sm leading-relaxed text-zinc-100" />
            {visibleSteps.length > 0 && (
              <ol className="mt-4 space-y-2">
                {visibleSteps.map((step, index) => (
                  <li key={index} className="rounded-xl bg-surface-elevated px-4 py-3 text-sm text-zinc-200">
                    <span className="mr-2 text-xs text-zinc-500">{index + 1}</span>
                    {step}
                  </li>
                ))}
              </ol>
            )}
            {lesson.example.withheld && shownSteps < steps.length && (
              <button
                type="button"
                onClick={() => setShownSteps((count) => count + 1)}
                className="mt-4 rounded-lg bg-surface-elevated px-3 py-1.5 text-xs text-zinc-300 hover:text-zinc-100"
              >
                下一步提示
              </button>
            )}
            {lesson.example.withheld && (
              <p className="mt-3 text-xs text-zinc-500">數學例題不會直接給最終答案。</p>
            )}
          </section>

          <section className="glass-card p-6">
            <h3 className="mb-4 text-sm font-semibold text-zinc-300">檢查題</h3>
            <div className="space-y-6">
              {lesson.questions.map((question) => {
                const result = results?.results.find((item) => item.question_id === question.id);
                return (
                  <div key={question.id}>
                    <MarkdownMath
                      text={question.stem}
                      className="mb-3 text-sm leading-relaxed text-zinc-100"
                    />
                    <div className="space-y-2">
                      {Object.entries(question.options).map(([key, value]) => {
                        const selected = (result?.user_answer || answers[String(question.id)]) === key;
                        const showMark = Boolean(result);
                        const correct = result?.correct_answer === key;
                        return (
                          <button
                            key={key}
                            type="button"
                            disabled={Boolean(results)}
                            onClick={() =>
                              setAnswers((prev) => ({ ...prev, [String(question.id)]: key }))
                            }
                            className={cn(
                              "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left text-sm",
                              showMark && correct && "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
                              showMark && selected && !correct && "border-accent-red/40 bg-accent-red/10 text-accent-red",
                              !showMark && selected && "border-primary-500/50 bg-primary-500/10 text-primary-300",
                              !showMark && !selected && "border-white/5 bg-surface-elevated text-zinc-300"
                            )}
                          >
                            <span className="text-xs font-bold">{key}</span>
                            <span>{value}</span>
                          </button>
                        );
                      })}
                    </div>
                    {result?.explanation && (
                      <p className="mt-2 text-xs text-zinc-400">{result.explanation}</p>
                    )}
                  </div>
                );
              })}
            </div>
            {results ? (
              <p className="mt-5 text-sm text-zinc-200">
                已寫入測驗紀錄：{results.correct_count}/{results.total_questions}（{results.score_percent}%）
              </p>
            ) : (
              <button
                type="button"
                onClick={() => void submitChecks()}
                disabled={submitting}
                className="btn-primary mt-5 disabled:opacity-50"
              >
                {submitting ? "提交中…" : "提交檢查題"}
              </button>
            )}
          </section>

          <button
            type="button"
            onClick={() => void generate(true)}
            disabled={generating}
            className="text-xs text-zinc-500 hover:text-zinc-300 disabled:opacity-50"
          >
            {generating ? "準備中…" : "用同一知識點再生成一課"}
          </button>
        </>
      )}
    </div>
  );
}
