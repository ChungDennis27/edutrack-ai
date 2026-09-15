import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/utils";

interface TopicData {
  knowledge_point_id: number;
  code: string;
  name_zh: string;
  name_en: string;
  topic_name_zh: string;
  total_attempts: number;
  correct_count: number;
  mastery_percent: number;
  avg_time_spent: number;
  is_weak: boolean;
}

interface ReportData {
  user_id: number;
  generated_at: string;
  overall_mastery: number;
  weak_topics: TopicData[];
  strong_topics: TopicData[];
  recommendations: {
    knowledge_point_id: number;
    name_zh: string;
    topic: string;
    mastery_percent: number;
    message: string;
    resource_query: string;
  }[];
}

function StatCard({
  label,
  value,
  suffix = "",
  color = "primary",
}: {
  label: string;
  value: string | number;
  suffix?: string;
  color?: "primary" | "secondary" | "accent-red" | "accent-amber";
}) {
  const colorMap = {
    primary: "text-primary-400",
    secondary: "text-secondary-400",
    "accent-red": "text-accent-red",
    "accent-amber": "text-accent-amber",
  };

  return (
    <div className="glass-card-hover p-5">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className={cn("mt-1 text-2xl font-bold", colorMap[color])}>
        {value}
        <span className="text-sm font-normal text-zinc-500">{suffix}</span>
      </p>
    </div>
  );
}

export default function Dashboard() {
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchReport();
  }, []);

  const fetchReport = async () => {
    try {
      const res = await fetch("/api/analytics/report", {
        credentials: "include",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法載入數據");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton h-24" />
        ))}
        <div className="skeleton h-80 md:col-span-2" />
        <div className="skeleton h-80 md:col-span-2" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card p-8 text-center">
        <p className="text-accent-red">⚠️ {error}</p>
        <p className="mt-2 text-sm text-zinc-500">
          請先完成至少一次測驗以查看分析報告。
        </p>
      </div>
    );
  }

  if (!report) return null;

  // Prepare radar chart data
  const radarData = [
    ...report.strong_topics.map((t) => ({
      subject: t.name_zh.length > 6 ? t.name_zh.slice(0, 6) + "…" : t.name_zh,
      mastery: t.mastery_percent,
      fullMark: 100,
    })),
    ...report.weak_topics.slice(0, 5).map((t) => ({
      subject: t.name_zh.length > 6 ? t.name_zh.slice(0, 6) + "…" : t.name_zh,
      mastery: t.mastery_percent,
      fullMark: 100,
    })),
  ];

  // Mock trend data (would come from backend in production)
  const trendData = [
    { date: "第1週", score: 45 },
    { date: "第2週", score: 52 },
    { date: "第3週", score: 48 },
    { date: "第4週", score: 61 },
    { date: "第5週", score: 58 },
    { date: "第6週", score: report.overall_mastery },
  ];

  const totalAttempts = [...report.weak_topics, ...report.strong_topics].reduce(
    (sum, t) => sum + t.total_attempts,
    0
  );

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Stats row */}
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard
          label="整體掌握度"
          value={report.overall_mastery}
          suffix="%"
          color={report.overall_mastery >= 60 ? "primary" : "accent-amber"}
        />
        <StatCard
          label="弱項數量"
          value={report.weak_topics.length}
          color="accent-red"
        />
        <StatCard
          label="已作答題目"
          value={totalAttempts}
          color="secondary"
        />
        <StatCard
          label="強勢課題"
          value={report.strong_topics.length}
          color="primary"
        />
      </div>

      {/* Charts row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Radar chart */}
        <div className="glass-card p-6">
          <h3 className="mb-4 text-sm font-semibold text-zinc-300">
            知識點掌握雷達圖
          </h3>
          {radarData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#3f3f46" />
                <PolarAngleAxis
                  dataKey="subject"
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                />
                <PolarRadiusAxis
                  angle={30}
                  domain={[0, 100]}
                  tick={{ fill: "#71717a", fontSize: 10 }}
                />
                <Radar
                  name="掌握度"
                  dataKey="mastery"
                  stroke="#2563eb"
                  fill="#2563eb"
                  fillOpacity={0.25}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #3f3f46",
                    borderRadius: "8px",
                    color: "#fafafa",
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[300px] items-center justify-center text-sm text-zinc-500">
              暫無數據
            </div>
          )}
        </div>

        {/* Area chart */}
        <div className="glass-card p-6">
          <h3 className="mb-4 text-sm font-semibold text-zinc-300">
            學習進度趨勢
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={trendData}>
              <defs>
                <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563eb" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="date" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fill: "#71717a", fontSize: 10 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  border: "1px solid #3f3f46",
                  borderRadius: "8px",
                  color: "#fafafa",
                }}
              />
              <Area
                type="monotone"
                dataKey="score"
                stroke="#2563eb"
                strokeWidth={2}
                fill="url(#scoreGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recommendations */}
      {report.recommendations.length > 0 && (
        <div className="glass-card p-6">
          <h3 className="mb-4 text-sm font-semibold text-zinc-300">
            🎯 弱項推薦 — 建議加強複習
          </h3>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {report.recommendations.map((rec) => (
              <div
                key={rec.knowledge_point_id}
                className="glass-card-hover p-4"
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs text-zinc-500">{rec.topic}</span>
                  <span className="badge-weak">{rec.mastery_percent}%</span>
                </div>
                <h4 className="mb-1 text-sm font-medium text-zinc-200">
                  {rec.name_zh}
                </h4>
                <p className="text-xs text-zinc-500">{rec.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
