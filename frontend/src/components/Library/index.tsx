import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiJson } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LibraryDocument {
  id: number;
  filename: string;
  subject: string;
  size_bytes: number;
  status: "processing" | "ready" | "empty" | "failed" | string;
  chunk_count: number;
  error: string | null;
  created_at: string | null;
}

interface Quota {
  files: number;
  file_limit: number;
  bytes: number;
  byte_limit: number;
  per_file_limit: number;
}

interface LibraryResponse {
  documents: LibraryDocument[];
  quota: Quota;
}

const SUBJECTS = [
  { value: "general", label: "通用" },
  { value: "chinese", label: "中文" },
  { value: "math", label: "數學" },
  { value: "english", label: "英文" },
];

const SUBJECT_LABEL: Record<string, string> = {
  general: "通用",
  chinese: "中文",
  math: "數學",
  english: "英文",
};

const STATUS_LABEL: Record<string, string> = {
  ready: "已索引",
  empty: "抽唔到文字",
  failed: "索引失敗",
  processing: "處理中",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Library() {
  const [documents, setDocuments] = useState<LibraryDocument[]>([]);
  const [quota, setQuota] = useState<Quota | null>(null);
  const [subject, setSubject] = useState("general");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    const data = await apiJson<LibraryResponse>("/api/uploads");
    setDocuments(data.documents);
    setQuota(data.quota);
  }, []);

  useEffect(() => {
    load()
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "未能載入資料庫");
      })
      .finally(() => setLoading(false));
  }, [load]);

  const uploadFiles = async (files: FileList | File[]) => {
    const list = Array.from(files);
    if (list.length === 0 || uploading) return;
    setUploading(true);
    setError("");
    const failures: string[] = [];
    for (const file of list) {
      const form = new FormData();
      form.append("file", file);
      form.append("subject", subject);
      try {
        await apiJson("/api/uploads", { method: "POST", body: form });
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "上傳失敗";
        failures.push(`${file.name}：${message}`);
      }
    }
    try {
      await load();
    } catch (err) {
      failures.push(err instanceof ApiError ? err.message : "未能重新載入清單");
    }
    setError(failures.join("\n"));
    setUploading(false);
    if (inputRef.current) inputRef.current.value = "";
  };

  const remove = async (doc: LibraryDocument) => {
    setError("");
    try {
      await apiJson(`/api/uploads/${doc.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "未能刪除");
    }
  };

  const usedRatio = quota ? Math.min(quota.bytes / quota.byte_limit, 1) : 0;

  return (
    <div className="animate-fade-in space-y-6">
      <section className="glass-card p-6">
        <h2 className="text-2xl font-bold">我的資料庫</h2>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">
          上傳自己的筆記，導師就可以喺「我的資料」或「全部」範圍引用。預設聊天仍然只搜 DSE 課程。
          只接受 PDF、TXT、MD。掃描版 PDF 抽唔到字，OCR 未做。
        </p>
        {quota && (
          <div className="mt-4">
            <div className="mb-1 flex justify-between text-xs text-zinc-500">
              <span>
                {quota.files} / {quota.file_limit} 個檔
              </span>
              <span>
                {formatBytes(quota.bytes)} / {formatBytes(quota.byte_limit)}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-elevated">
              <div
                className="h-full rounded-full bg-gradient-primary"
                style={{ width: `${usedRatio * 100}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-zinc-600">每個檔案上限 {formatBytes(quota.per_file_limit)}</p>
          </div>
        )}
      </section>

      <section
        className={cn(
          "glass-card border-dashed p-8 text-center transition-colors",
          dragging && "border-primary-500/50 bg-primary-500/5"
        )}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          void uploadFiles(event.dataTransfer.files);
        }}
      >
        <p className="text-sm text-zinc-300">拖放檔案到呢度，或者選擇檔案</p>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
          <label className="text-sm text-zinc-400">
            科目
            <select
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              className="ml-2 rounded-lg border border-white/10 bg-surface-card px-3 py-2 text-sm text-zinc-100 outline-none"
            >
              {SUBJECTS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="btn-primary disabled:opacity-50"
          >
            {uploading ? "上傳中…" : "選擇檔案"}
          </button>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.txt,.md,.markdown,application/pdf,text/plain,text/markdown"
            multiple
            className="hidden"
            onChange={(event) => {
              if (event.target.files) void uploadFiles(event.target.files);
            }}
          />
        </div>
      </section>

      {error && (
        <p className="whitespace-pre-wrap rounded-xl border border-accent-red/30 bg-accent-red/10 px-4 py-3 text-sm text-accent-red">
          {error}
        </p>
      )}

      <section className="space-y-3">
        {loading && <div className="skeleton h-20 w-full" />}
        {!loading && documents.length === 0 && (
          <p className="text-sm text-zinc-500">未有上傳檔案。demo 帳號預設都係空的。</p>
        )}
        {documents.map((doc) => (
          <article key={doc.id} className="glass-card flex items-start justify-between gap-4 p-4">
            <div className="min-w-0">
              <h3 className="truncate text-sm font-semibold text-zinc-100">{doc.filename}</h3>
              <p className="mt-1 text-xs text-zinc-500">
                {SUBJECT_LABEL[doc.subject] || doc.subject} · {formatBytes(doc.size_bytes)} ·{" "}
                {STATUS_LABEL[doc.status] || doc.status}
                {doc.status === "ready" ? ` · ${doc.chunk_count} 段` : ""}
              </p>
              {doc.error && (
                <p className={cn("mt-1 text-xs", doc.status === "ready" ? "text-amber-400" : "text-accent-red")}>
                  {doc.error}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => void remove(doc)}
              className="shrink-0 rounded-lg bg-surface-elevated px-3 py-1.5 text-xs text-zinc-300 hover:text-zinc-100"
            >
              刪除
            </button>
          </article>
        ))}
      </section>
    </div>
  );
}
