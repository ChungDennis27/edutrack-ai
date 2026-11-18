import { useEffect, useState } from "react";
import { ApiError, apiJson } from "@/lib/api";

interface LlmSettings {
  provider: "openai" | "anthropic" | string;
  base_url: string;
  model: string;
  has_key: boolean;
  key_hint: string;
  source: "saved" | "env" | string;
}

const PRESETS = [
  {
    label: "OpenAI 官方",
    provider: "openai",
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
  },
  {
    label: "DeepSeek 官方",
    provider: "openai",
    base_url: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
  },
  {
    label: "TeamoRouter",
    provider: "openai",
    base_url: "https://api.teamorouter.com/v1",
    model: "deepseek-flash-free",
  },
];

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

export default function Settings() {
  const [provider, setProvider] = useState("openai");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState<LlmSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const apply = (data: LlmSettings) => {
    setSaved(data);
    setProvider(data.provider || "openai");
    setBaseUrl(data.base_url || "");
    setModel(data.model || "");
    setApiKey("");
  };

  useEffect(() => {
    apiJson<LlmSettings>("/api/settings/llm")
      .then(apply)
      .catch((err: unknown) => setError(errorText(err, "未能載入設定")))
      .finally(() => setLoading(false));
  }, []);

  const body = {
    provider,
    base_url: baseUrl.trim(),
    model: model.trim(),
    api_key: apiKey.trim(),
  };

  const save = async () => {
    setBusy("save");
    setError("");
    setNotice("");
    try {
      const data = await apiJson<LlmSettings>("/api/settings/llm", { method: "PUT", body });
      apply(data);
      setNotice("已儲存。下一句對話會用呢個設定，唔使重開。");
    } catch (err) {
      setError(errorText(err, "未能儲存"));
    } finally {
      setBusy("");
    }
  };

  const test = async () => {
    setBusy("test");
    setError("");
    setNotice("");
    try {
      const data = await apiJson<{ reply: string }>("/api/settings/llm/test", {
        method: "POST",
        body,
      });
      setNotice(`連線成功：${data.reply}`);
    } catch (err) {
      setError(errorText(err, "連線失敗"));
    } finally {
      setBusy("");
    }
  };

  const reset = async () => {
    setBusy("reset");
    setError("");
    setNotice("");
    try {
      const data = await apiJson<LlmSettings>("/api/settings/llm/reset", { method: "POST" });
      apply(data);
      setNotice("已還原成 .env 的設定。");
    } catch (err) {
      setError(errorText(err, "未能還原"));
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="mx-auto max-w-xl animate-fade-in space-y-6">
      <header>
        <h2 className="text-2xl font-semibold text-zinc-50">AI 設定</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Key 過期或者想換中轉站，填 Base URL、API key 同模型就得。這是這部機共用的設定，儲存後即時生效。
          頁面不會再顯示完整 key。
        </p>
      </header>

      {loading ? (
        <div className="skeleton h-40 w-full" />
      ) : (
        <section className="glass-card space-y-4 p-6">
          {saved && (
            <p className="text-xs text-zinc-500">
              而家用緊{saved.source === "saved" ? "已儲存設定" : ".env"}
              {saved.has_key ? ` · key ${saved.key_hint}` : " · 未有 key"}
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            {PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => {
                  setProvider(preset.provider);
                  setBaseUrl(preset.base_url);
                  setModel(preset.model);
                }}
                className="rounded-lg bg-surface-elevated px-3 py-1.5 text-xs text-zinc-300 hover:text-zinc-100"
              >
                {preset.label}
              </button>
            ))}
          </div>

          <label className="block text-sm text-zinc-400">
            類型
            <select
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
              className="mt-1 w-full rounded-xl border border-white/10 bg-surface-card px-3 py-2 text-sm text-zinc-100 outline-none"
            >
              <option value="openai">OpenAI 相容（中轉站 / DeepSeek / OpenAI）</option>
              <option value="anthropic">Anthropic 官方</option>
            </select>
          </label>

          <label className="block text-sm text-zinc-400">
            Base URL
            <input
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="https://your-relay.example/v1"
              autoComplete="off"
              spellCheck={false}
              className="mt-1 w-full rounded-xl border border-white/10 bg-surface-card px-3 py-2 text-sm text-zinc-100 outline-none"
            />
          </label>
          <p className="-mt-2 text-xs text-zinc-600">
            中轉站通常以 /v1 結尾。Key 不要寫在網址裡。Anthropic 官方可以留空。
          </p>

          <label className="block text-sm text-zinc-400">
            模型
            <input
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder="deepseek-chat"
              autoComplete="off"
              spellCheck={false}
              className="mt-1 w-full rounded-xl border border-white/10 bg-surface-card px-3 py-2 text-sm text-zinc-100 outline-none"
            />
          </label>

          <label className="block text-sm text-zinc-400">
            API key
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={saved?.has_key ? "留空則保留現有 key" : "貼上新的 API key"}
              autoComplete="off"
              spellCheck={false}
              className="mt-1 w-full rounded-xl border border-white/10 bg-surface-card px-3 py-2 text-sm text-zinc-100 outline-none"
            />
          </label>

          {error && (
            <p className="rounded-xl border border-accent-red/30 bg-accent-red/10 px-4 py-3 text-sm text-accent-red">
              {error}
            </p>
          )}
          {notice && (
            <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
              {notice}
            </p>
          )}

          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={() => void test()} disabled={Boolean(busy)} className="btn-primary disabled:opacity-50">
              {busy === "test" ? "測試中…" : "測試連線"}
            </button>
            <button type="button" onClick={() => void save()} disabled={Boolean(busy)} className="btn-ai disabled:opacity-50">
              {busy === "save" ? "儲存中…" : "儲存"}
            </button>
            <button
              type="button"
              onClick={() => void reset()}
              disabled={Boolean(busy)}
              className="rounded-lg bg-surface-elevated px-3 py-1.5 text-xs text-zinc-300 hover:text-zinc-100 disabled:opacity-50"
            >
              還原 .env
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
