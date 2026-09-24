import { useCallback, useEffect, useState } from "react";
import MarkdownMath from "@/components/common/MarkdownMath";
import { apiJson } from "@/lib/api";
import { cn } from "@/lib/utils";

interface QuizQuestion {
  id: number;
  index: number;
  stem: string;
  options: Record<string, string>;
  knowledge_point_code?: string;
}

interface QuizData {
  attempt_id: number;
  title: string;
  difficulty: string;
  total_questions: number;
  questions: QuizQuestion[];
}

interface QuizResult {
  attempt_id: number;
  title: string;
  score_percent: number;
  correct_count: number;
  total_questions: number;
  results: {
    question_id: number;
    stem: string;
    options: Record<string, string>;
    correct_answer: string;
    user_answer: string;
    is_correct: boolean;
    time_spent: number;
    is_slow_but_correct: boolean;
    explanation: string;
  }[];
}

const DIFFICULTY_OPTIONS = [
  { value: "level_3", label: "Level 3 基礎", color: "text-emerald-400" },
  { value: "level_4", label: "Level 4 中等", color: "text-amber-400" },
  { value: "level_5", label: "Level 5 挑戰", color: "text-orange-400" },
  { value: "level_5pp", label: "Level 5++ 頂尖", color: "text-red-400" },
];

const SUBJECT_OPTIONS = [
  { value: "math", label: "數學" },
  { value: "chinese", label: "中文" },
  { value: "english", label: "英文" },
];

interface TopicOption {
  id: number;
  name_zh: string;
  name_en: string;
  syllabus_ref?: string | null;
}

interface SubjectCatalog {
  code: string;
  name_zh: string;
  topics: TopicOption[];
}

export default function Quiz() {
  const [step, setStep] = useState<"setup" | "quiz" | "results">("setup");
  const [subject, setSubject] = useState("math");
  const [subjectCatalog, setSubjectCatalog] = useState<SubjectCatalog[]>([]);
  const [topicId, setTopicId] = useState<number | null>(null);
  const [difficulty, setDifficulty] = useState("level_4");
  const [numQuestions, setNumQuestions] = useState(5);
  const [quiz, setQuiz] = useState<QuizData | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [timePerQuestion, setTimePerQuestion] = useState<Record<string, number>>({});
  const [questionStartTime, setQuestionStartTime] = useState<number>(Date.now());
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<QuizResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiJson<{ subjects: SubjectCatalog[] }>("/api/quiz/subjects")
      .then((data) => setSubjectCatalog(data.subjects))
      .catch(() => setSubjectCatalog([]));
  }, []);

  const topicOptions =
    subjectCatalog.find((s) => s.code === subject)?.topics ?? [];

  const selectSubject = (code: string) => {
    setSubject(code);
    setTopicId(null);
  };

  const generateQuiz = async () => {
    setIsGenerating(true);
    setError("");
    try {
      const data = await apiJson<QuizData>("/api/quiz/generate", {
        method: "POST",
        body: {
          subject,
          topic_id: topicId,
          difficulty,
          num_questions: numQuestions,
        },
      });

      setQuiz(data);
      setStep("quiz");
      setCurrentIndex(0);
      setAnswers({});
      setTimePerQuestion({});
      setQuestionStartTime(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法生成測驗");
    } finally {
      setIsGenerating(false);
    }
  };

  const recordTimeForCurrent = useCallback(() => {
    if (!quiz) return;
    const elapsed = Math.round((Date.now() - questionStartTime) / 1000);
    const qId = String(quiz.questions[currentIndex].id);
    setTimePerQuestion((prev) => ({ ...prev, [qId]: elapsed }));
  }, [quiz, currentIndex, questionStartTime]);

  const selectAnswer = (questionId: number, answer: string) => {
    setAnswers((prev) => ({ ...prev, [String(questionId)]: answer }));
  };

  const goToQuestion = (index: number) => {
    recordTimeForCurrent();
    setCurrentIndex(index);
    setQuestionStartTime(Date.now());
  };

  const submitQuiz = async () => {
    if (!quiz) return;
    recordTimeForCurrent();
    setIsSubmitting(true);
    setError("");

    try {
      await apiJson("/api/quiz/submit", {
        method: "POST",
        body: {
          attempt_id: quiz.attempt_id,
          answers,
          time_per_question: timePerQuestion,
        },
      });

      const resultData = await apiJson<QuizResult>(
        `/api/quiz/attempt/${quiz.attempt_id}/results`
      );
      setResult(resultData);
      setStep("results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失敗");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Setup screen
  if (step === "setup") {
    return (
      <div className="mx-auto max-w-lg animate-fade-in">
        <div className="glass-card p-8">
          <h2 className="mb-6 text-xl font-bold text-gradient-primary">
            生成 AI 測驗
          </h2>

          {/* Subject */}
          <div className="mb-5">
            <label className="mb-2 block text-sm text-zinc-400">學科</label>
            <div className="flex gap-2">
              {SUBJECT_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => selectSubject(opt.value)}
                  className={cn(
                    "flex-1 rounded-xl px-4 py-2.5 text-sm font-medium transition-all",
                    subject === opt.value
                      ? "bg-primary-500/20 text-primary-400 ring-1 ring-primary-500/30"
                      : "bg-surface-elevated text-zinc-400 hover:bg-surface-border"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Topic */}
          {topicOptions.length > 0 && (
            <div className="mb-5">
              <label className="mb-2 block text-sm text-zinc-400">
                課題（可選）
              </label>
              <select
                value={topicId ?? ""}
                onChange={(e) =>
                  setTopicId(e.target.value ? Number(e.target.value) : null)
                }
                className="w-full rounded-xl border border-white/10 bg-surface-card px-4 py-2.5 text-sm text-zinc-200 outline-none transition-colors focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/20"
              >
                <option value="">全部課題</option>
                {topicOptions.map((topic) => (
                  <option key={topic.id} value={topic.id}>
                    {topic.name_zh}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Difficulty */}
          <div className="mb-5">
            <label className="mb-2 block text-sm text-zinc-400">難度</label>
            <div className="grid grid-cols-2 gap-2">
              {DIFFICULTY_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setDifficulty(opt.value)}
                  className={cn(
                    "rounded-xl px-4 py-2.5 text-sm font-medium transition-all",
                    difficulty === opt.value
                      ? "bg-primary-500/20 ring-1 ring-primary-500/30 " + opt.color
                      : "bg-surface-elevated text-zinc-400 hover:bg-surface-border"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Number of questions */}
          <div className="mb-6">
            <label className="mb-2 block text-sm text-zinc-400">
              題目數量：{numQuestions}
            </label>
            <input
              type="range"
              min={3}
              max={10}
              value={numQuestions}
              onChange={(e) => setNumQuestions(Number(e.target.value))}
              className="w-full accent-primary-500"
            />
          </div>

          {error && (
            <p className="mb-4 text-sm text-accent-red">⚠️ {error}</p>
          )}

          <button
            onClick={generateQuiz}
            disabled={isGenerating}
            className="btn-primary w-full disabled:opacity-50"
          >
            {isGenerating ? "AI 生成中..." : "開始測驗"}
          </button>
        </div>
      </div>
    );
  }

  // Quiz screen
  if (step === "quiz" && quiz) {
    const currentQ = quiz.questions[currentIndex];
    const currentAnswer = answers[String(currentQ.id)] || "";
    const answeredCount = Object.keys(answers).length;
    const isLastQuestion = currentIndex === quiz.questions.length - 1;

    return (
      <div className="mx-auto max-w-3xl animate-fade-in">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-zinc-100">{quiz.title}</h2>
            <p className="text-xs text-zinc-500">
              {quiz.difficulty} · 共 {quiz.total_questions} 題
            </p>
          </div>
          <div className="text-sm text-zinc-400">
            {answeredCount}/{quiz.total_questions}
          </div>
        </div>

        {/* Question navigator */}
        <div className="mb-6 flex flex-wrap gap-2">
          {quiz.questions.map((q, i) => (
            <button
              key={q.id}
              onClick={() => goToQuestion(i)}
              className={cn(
                "h-8 w-8 rounded-lg text-xs font-medium transition-all",
                i === currentIndex
                  ? "bg-primary-500 text-white"
                  : answers[String(q.id)]
                    ? "bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30"
                    : "bg-surface-elevated text-zinc-500 hover:bg-surface-border"
              )}
            >
              {i + 1}
            </button>
          ))}
        </div>

        {/* Current question */}
        <div className="glass-card p-8">
          <p className="mb-1 text-xs text-zinc-500">第 {currentIndex + 1} 題</p>
          <MarkdownMath
            text={currentQ.stem}
            className="mb-6 text-base leading-relaxed text-zinc-100"
          />

          {/* Options */}
          <div className="space-y-3">
            {Object.entries(currentQ.options).map(([key, value]) => (
              <button
                key={key}
                onClick={() => selectAnswer(currentQ.id, key)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left text-sm transition-all",
                  currentAnswer === key
                    ? "border-primary-500/50 bg-primary-500/10 text-primary-300"
                    : "border-white/5 bg-surface-elevated text-zinc-300 hover:border-white/20 hover:bg-surface-border"
                )}
              >
                <span
                  className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-bold",
                    currentAnswer === key
                      ? "bg-primary-500 text-white"
                      : "bg-surface-border text-zinc-400"
                  )}
                >
                  {key}
                </span>
                <MarkdownMath text={value} />
              </button>
            ))}
          </div>
        </div>

        {/* Navigation */}
        <div className="mt-6 flex items-center justify-between">
          <button
            onClick={() => goToQuestion(currentIndex - 1)}
            disabled={currentIndex === 0}
            className="rounded-xl bg-surface-elevated px-4 py-2 text-sm text-zinc-400 transition-all hover:bg-surface-border disabled:opacity-30"
          >
            ← 上一題
          </button>

          {isLastQuestion ? (
            <button
              onClick={submitQuiz}
              disabled={answeredCount < quiz.total_questions || isSubmitting}
              className="btn-primary disabled:opacity-50"
            >
              {isSubmitting ? "批改中..." : "提交測驗"}
            </button>
          ) : (
            <button
              onClick={() => goToQuestion(currentIndex + 1)}
              className="btn-primary"
            >
              下一題 →
            </button>
          )}
        </div>
      </div>
    );
  }

  // Results screen
  if (step === "results" && result) {
    return (
      <div className="mx-auto max-w-3xl animate-fade-in">
        {/* Score summary */}
        <div className="glass-card mb-6 p-8 text-center">
          <p className="mb-2 text-sm text-zinc-400">測驗結果</p>
          <p className="mb-1 text-4xl font-bold text-gradient-primary">
            {result.score_percent}%
          </p>
          <p className="text-sm text-zinc-500">
            答對 {result.correct_count}/{result.total_questions} 題
          </p>
        </div>

        {/* Detailed results */}
        <div className="space-y-4">
          {result.results.map((r, i) => (
            <div
              key={r.question_id}
              className={cn(
                "glass-card p-6",
                r.is_correct ? "border-l-4 border-l-emerald-500" : "border-l-4 border-l-accent-red"
              )}
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="text-sm font-medium text-zinc-200">
                  {i + 1}. <MarkdownMath text={r.stem} />
                </div>
                <span
                  className={cn(
                    "ml-2 shrink-0 rounded-full px-2 py-0.5 text-xs",
                    r.is_correct
                      ? "bg-emerald-500/20 text-emerald-400"
                      : "bg-accent-red/20 text-accent-red"
                  )}
                >
                  {r.is_correct ? "✓ 正確" : "✗ 錯誤"}
                </span>
              </div>

              <div className="mb-2 text-xs text-zinc-500">
                <span className="mr-4">
                  你的答案：
                  <span className={r.is_correct ? "text-emerald-400" : "text-accent-red"}>
                    {r.user_answer || "（未作答）"}
                  </span>
                </span>
                {!r.is_correct && (
                  <span>
                    正確答案：<span className="text-emerald-400">{r.correct_answer}</span>
                  </span>
                )}
              </div>

              {r.is_slow_but_correct && (
                <p className="mb-2 text-xs text-accent-amber">
                  ⚠️ 答對但用時過長，建議複習此課題
                </p>
              )}

              {r.explanation && (
                <p className="mt-2 text-xs text-zinc-400">
                  💡 {r.explanation}
                </p>
              )}
            </div>
          ))}
        </div>

        <div className="mt-6 flex justify-center gap-4">
          <button onClick={() => setStep("setup")} className="btn-primary">
            再測一次
          </button>
        </div>
      </div>
    );
  }

  return null;
}
