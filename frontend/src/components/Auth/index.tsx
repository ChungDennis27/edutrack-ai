import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import MarkdownMath from "@/components/common/MarkdownMath";
import { cn } from "@/lib/utils";

type Mode = "login" | "register";

interface LocationState {
  from?: string;
}

export default function Auth() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [mode, setMode] = useState<Mode>("login");
  const [identifier, setIdentifier] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const isRegister = mode === "register";

  const switchMode = (next: Mode) => {
    setMode(next);
    setError("");
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");

    if (isRegister) {
      if (password.length < 8) {
        setError("密碼至少需要 8 個字元。");
        return;
      }
      if (password !== confirm) {
        setError("兩次輸入的密碼並不一致。");
        return;
      }
    }

    setSubmitting(true);
    try {
      if (isRegister) {
        await register(email.trim(), username.trim(), password);
      } else {
        await login(identifier.trim(), password);
      }
      const state = location.state as LocationState | null;
      navigate(state?.from ?? "/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "發生錯誤，請稍後再試。");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto grid min-h-[calc(100vh-9rem)] max-w-5xl items-center gap-12 lg:grid-cols-2">
      {/* Editorial panel */}
      <section className="hidden flex-col justify-between lg:flex">
        <div>
          <p className="text-sm tracking-[0.35em] text-primary-300/70">
            HKDSE
          </p>
          <h1 className="mt-4 text-5xl font-semibold leading-[1.05] text-zinc-50">
            每個知識點，
            <br />
            都值得被<span className="text-gradient-ai">看見</span>。
          </h1>
          <p className="mt-6 max-w-sm text-sm leading-relaxed text-zinc-400">
            EduTrack AI 追蹤你每一次作答的對錯、用時與錯誤模式，
            把 DSE 備試從「做完就算」變成有數據支撐的複習路線。
          </p>
        </div>

        <div className="glass-card mt-10 p-6">
          <p className="text-xs text-zinc-500">本週待複習</p>
          <div className="mt-4 space-y-3">
            {[
              { label: "二次方程 · 判別式", value: 42, tone: "bg-accent-red" },
              { label: "文言文 · 論仁", value: 68, tone: "bg-accent-amber" },
              { label: "English · Organization", value: 81, tone: "bg-primary-500" },
            ].map((row) => (
              <div key={row.label} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs text-zinc-400">
                  <span>{row.label}</span>
                  <span className="text-zinc-500">{row.value}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-surface-elevated">
                  <div
                    className={cn("h-full rounded-full", row.tone)}
                    style={{ width: `${row.value}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-6 border-t border-white/10 pt-4 text-center text-sm text-zinc-300">
            <MarkdownMath text="$$x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$$" />
          </div>
        </div>
      </section>

      {/* Form panel */}
      <section className="glass-card w-full p-8 sm:p-10">
        <h2 className="text-2xl font-semibold text-zinc-50">
          {isRegister ? "建立你的學習檔案" : "歡迎回來"}
        </h2>
        <p className="mt-2 text-sm text-zinc-500">
          {isRegister
            ? "註冊後即可使用 AI 導師、動態測驗與弱項分析。"
            : "登入以繼續你的 DSE 備試進度。"}
        </p>

        <div className="mt-6 flex gap-1 rounded-xl bg-surface-elevated p-1">
          {(["login", "register"] as Mode[]).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => switchMode(value)}
              className={cn(
                "flex-1 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
                mode === value
                  ? "bg-primary-500/15 text-primary-300"
                  : "text-zinc-400 hover:text-zinc-200"
              )}
            >
              {value === "login" ? "登入" : "註冊"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          {isRegister ? (
            <>
              <Field
                label="電郵"
                type="email"
                value={email}
                onChange={setEmail}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
              <Field
                label="用戶名稱"
                value={username}
                onChange={setUsername}
                placeholder="hkdse_student"
                autoComplete="username"
                required
              />
            </>
          ) : (
            <Field
              label="電郵或用戶名稱"
              value={identifier}
              onChange={setIdentifier}
              placeholder="you@example.com"
              autoComplete="username"
              required
            />
          )}

          <Field
            label="密碼"
            type="password"
            value={password}
            onChange={setPassword}
            placeholder="••••••••"
            autoComplete={isRegister ? "new-password" : "current-password"}
            required
          />

          {isRegister && (
            <Field
              label="確認密碼"
              type="password"
              value={confirm}
              onChange={setConfirm}
              placeholder="••••••••"
              autoComplete="new-password"
              required
            />
          )}

          {error && (
            <p
              role="alert"
              className="rounded-xl bg-accent-red/10 px-3 py-2 text-sm text-accent-red ring-1 ring-accent-red/20"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="btn-primary w-full disabled:opacity-50"
          >
            {submitting
              ? isRegister
                ? "建立中…"
                : "登入中…"
              : isRegister
                ? "建立帳戶"
                : "登入"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-zinc-600">
          {isRegister ? "已有帳戶？" : "還未有帳戶？"}
          <button
            type="button"
            onClick={() => switchMode(isRegister ? "login" : "register")}
            className="ml-1 font-medium text-primary-400 hover:text-primary-300"
          >
            {isRegister ? "前往登入" : "立即註冊"}
          </button>
        </p>
      </section>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  ...rest
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm text-zinc-400">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-white/10 bg-surface-card px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/20"
        {...rest}
      />
    </label>
  );
}
