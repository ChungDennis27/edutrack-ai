import { useEffect, useState } from "react";
import { apiJson } from "@/lib/api";
import { cn } from "@/lib/utils";

interface FlashcardData {
  id: number;
  front: string;
  back: string;
  source: string;
  ease_factor: number;
  interval_days: number;
  repetitions: number;
  next_review_date: string | null;
  knowledge_point_id: number | null;
}

const QUALITY_BUTTONS = [
  { value: 0, label: "完全忘記", color: "bg-red-500/20 text-red-400 ring-red-500/30" },
  { value: 1, label: "很難回想", color: "bg-orange-500/20 text-orange-400 ring-orange-500/30" },
  { value: 3, label: "勉強記得", color: "bg-amber-500/20 text-amber-400 ring-amber-500/30" },
  { value: 4, label: "稍有猶豫", color: "bg-emerald-500/20 text-emerald-400 ring-emerald-500/30" },
  { value: 5, label: "完美回憶", color: "bg-primary-500/20 text-primary-400 ring-primary-500/30" },
];

export default function Flashcards() {
  const [cards, setCards] = useState<FlashcardData[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [reviewedCount, setReviewedCount] = useState(0);

  useEffect(() => {
    fetchDueCards();
  }, []);

  const fetchDueCards = async () => {
    try {
      const data = await apiJson<{ cards: FlashcardData[] }>(
        "/api/flashcards/due"
      );
      setCards(data.cards);
    } catch {
      setCards([]);
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (quality: number) => {
    if (!cards[currentIndex]) return;

    try {
      await apiJson("/api/flashcards/review", {
        method: "POST",
        body: {
          flashcard_id: cards[currentIndex].id,
          quality,
        },
      });
    } catch {
      // silent fail
    }

    // Move to next card
    setIsFlipped(false);
    setReviewedCount((c) => c + 1);

    if (currentIndex < cards.length - 1) {
      setCurrentIndex((i) => i + 1);
    } else {
      // All cards reviewed
      setCards([]);
    }
  };

  const handleGenerateFromMistakes = async () => {
    setLoading(true);
    try {
      await apiJson("/api/flashcards/generate-from-mistakes", {
        method: "POST",
      });
      await fetchDueCards();
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="skeleton h-64 w-full max-w-md" />
      </div>
    );
  }

  if (cards.length === 0) {
    return (
      <div className="mx-auto max-w-md animate-fade-in">
        <div className="glass-card p-8 text-center">
          <div className="mb-4 text-4xl">🎉</div>
          <h3 className="mb-2 text-lg font-semibold text-zinc-200">
            {reviewedCount > 0 ? "今日複習完成！" : "暫無待複習記憶卡"}
          </h3>
          <p className="mb-6 text-sm text-zinc-500">
            {reviewedCount > 0
              ? `你已複習 ${reviewedCount} 張記憶卡。明天再見！`
              : "完成測驗後，錯題會自動生成記憶卡。"}
          </p>
          <button
            onClick={handleGenerateFromMistakes}
            className="btn-ai"
          >
            從錯題生成記憶卡
          </button>
        </div>
      </div>
    );
  }

  const currentCard = cards[currentIndex];

  return (
    <div className="mx-auto max-w-lg animate-fade-in">
      {/* Progress */}
      <div className="mb-6 flex items-center justify-between text-sm text-zinc-400">
        <span>
          記憶卡 {currentIndex + 1} / {cards.length}
        </span>
        <span>已複習：{reviewedCount}</span>
      </div>

      {/* Flashcard with 3D flip */}
      <div
        className="flashcard-scene mb-6 h-80 cursor-pointer"
        onClick={() => setIsFlipped(!isFlipped)}
      >
        <div className={cn("flashcard-inner", isFlipped && "flipped")}>
          {/* Front */}
          <div className="flashcard-face">
            <p className="mb-2 text-xs text-zinc-500">問題</p>
            <p className="text-center text-base leading-relaxed text-zinc-100">
              {currentCard.front}
            </p>
            <p className="absolute bottom-4 text-xs text-zinc-600">
              點擊翻轉查看答案
            </p>
          </div>

          {/* Back */}
          <div className={cn("flashcard-face flashcard-back")}>
            <p className="mb-2 text-xs text-zinc-500">答案</p>
            <div className="overflow-y-auto text-center text-sm leading-relaxed text-zinc-200">
              {currentCard.back}
            </div>
          </div>
        </div>
      </div>

      {/* Review buttons (only visible when flipped) */}
      {isFlipped && (
        <div className="space-y-3 animate-fade-in">
          <p className="text-center text-xs text-zinc-500">
            你記得多少？
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {QUALITY_BUTTONS.map((btn) => (
              <button
                key={btn.value}
                onClick={() => handleReview(btn.value)}
                className={cn(
                  "rounded-xl px-3 py-2 text-xs font-medium ring-1 transition-all hover:brightness-110",
                  btn.color
                )}
              >
                {btn.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Card stats */}
      <div className="mt-6 flex justify-center gap-4 text-xs text-zinc-600">
        <span>間隔天數：{currentCard.interval_days}天</span>
        <span>重複：{currentCard.repetitions}次</span>
        <span>EF：{currentCard.ease_factor}</span>
      </div>
    </div>
  );
}
