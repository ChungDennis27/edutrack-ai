import { NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Auth from "./components/Auth";
import RequireAuth from "./components/Auth/RequireAuth";
import ChatBot from "./components/ChatBot";
import ClassicalChinese from "./components/ClassicalChinese";
import Dashboard from "./components/Dashboard";
import EssayGrader from "./components/EssayGrader";
import MathHint from "./components/MathHint";
import Quiz from "./components/Quiz";
import Flashcards from "./components/Flashcard";

const NAV_ITEMS = [
  { to: "/", label: "首頁" },
  { to: "/chat", label: "AI 導師" },
  { to: "/classical", label: "文言精讀" },
  { to: "/math-hint", label: "數學引導" },
  { to: "/essay", label: "作文批改" },
  { to: "/quiz", label: "測驗" },
  { to: "/flashcards", label: "記憶卡" },
  { to: "/dashboard", label: "分析" },
];

function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-surface/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <NavLink to="/" className="text-lg font-bold text-gradient-primary">
          EduTrack AI
        </NavLink>

        <nav className="hidden items-center gap-0.5 md:flex">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                "flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors " +
                (isActive
                  ? "bg-primary-500/10 text-primary-400"
                  : "text-zinc-400 hover:bg-surface-elevated hover:text-zinc-200")
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          {user ? (
            <>
              <span className="hidden text-sm text-zinc-400 sm:inline">
                {user.display_name || user.username}
              </span>
              <button
                onClick={handleLogout}
                className="rounded-lg bg-surface-elevated px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:text-zinc-100"
              >
                登出
              </button>
            </>
          ) : (
            <NavLink to="/login" className="btn-primary px-4 py-1.5 text-xs">
              登入
            </NavLink>
          )}
        </div>
      </div>
    </header>
  );
}

function HomePage() {
  const { user } = useAuth();

  return (
    <div className="animate-fade-in space-y-8">
      <section className="glass-card p-10 text-center">
        <h2 className="mb-3 text-4xl font-bold tracking-tight">
          歡迎使用 <span className="text-gradient-ai">EduTrack AI</span>
        </h2>
        <p className="mx-auto max-w-xl text-zinc-400">
          專為香港 DSE 考生打造的 AI 個人化學習平台。
          涵蓋中文、英文、數學三科，配備 RAG 智能導師、動態測驗生成及弱項分析。
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <NavLink to={user ? "/quiz" : "/login"} className="btn-primary">
            開始測驗
          </NavLink>
          <NavLink to={user ? "/chat" : "/login"} className="btn-ai">
            AI 導師對話
          </NavLink>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        <NavLink to="/chat" className="glass-card-hover p-6">
          <h3 className="mb-2 text-lg font-semibold">RAG 智能導師</h3>
          <p className="text-sm text-zinc-400">
            基於 DSE 課程指引的精準問答，支援數學公式渲染
          </p>
        </NavLink>
        <NavLink to="/quiz" className="glass-card-hover p-6">
          <h3 className="mb-2 text-lg font-semibold">AI 動態測驗</h3>
          <p className="text-sm text-zinc-400">
            按 Level 3-5++ 自動生成題目，即時批改
          </p>
        </NavLink>
        <NavLink to="/dashboard" className="glass-card-hover p-6">
          <h3 className="mb-2 text-lg font-semibold">弱項分析</h3>
          <p className="text-sm text-zinc-400">
            雷達圖視覺化知識盲點，推送個人化練習
          </p>
        </NavLink>
      </section>

      <section className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <NavLink to="/classical" className="glass-card-hover p-6">
          <h3 className="mb-2 text-lg font-semibold">文言文精讀</h3>
          <p className="text-sm text-zinc-400">
            原文與譯文對照，AI 引用考評局標準逐句講解
          </p>
        </NavLink>
        <NavLink to="/math-hint" className="glass-card-hover p-6">
          <h3 className="mb-2 text-lg font-semibold">數學解題引導</h3>
          <p className="text-sm text-zinc-400">
            按 Method Marks 逐步給提示，唔直接畀答案
          </p>
        </NavLink>
        <NavLink to="/essay" className="glass-card-hover p-6">
          <h3 className="mb-2 text-lg font-semibold">英文作文批改</h3>
          <p className="text-sm text-zinc-400">
            模擬 HKEAA 閱卷員，按 Content/Language/Organization 評分
          </p>
        </NavLink>
        <NavLink to="/flashcards" className="glass-card-hover p-6">
          <h3 className="mb-2 text-lg font-semibold">間隔重複記憶卡</h3>
          <p className="text-sm text-zinc-400">
            根據 SM-2 演算法自動排程，錯題自動生成記憶卡
          </p>
        </NavLink>
      </section>
    </div>
  );
}

export default function App() {
  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<Auth />} />
          <Route
            path="/chat"
            element={
              <RequireAuth>
                <ChatBot />
              </RequireAuth>
            }
          />
          <Route
            path="/quiz"
            element={
              <RequireAuth>
                <Quiz />
              </RequireAuth>
            }
          />
          <Route
            path="/flashcards"
            element={
              <RequireAuth>
                <Flashcards />
              </RequireAuth>
            }
          />
          <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <Dashboard />
              </RequireAuth>
            }
          />
          <Route
            path="/classical"
            element={
              <RequireAuth>
                <ClassicalChinese />
              </RequireAuth>
            }
          />
          <Route
            path="/math-hint"
            element={
              <RequireAuth>
                <MathHint />
              </RequireAuth>
            }
          />
          <Route
            path="/essay"
            element={
              <RequireAuth>
                <EssayGrader />
              </RequireAuth>
            }
          />
        </Routes>
      </main>
    </div>
  );
}
