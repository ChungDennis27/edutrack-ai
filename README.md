# EduTrack AI — HKDSE 智能學習平台

> 專為香港中學文憑考試（HKDSE）設計的 AI 個人化學習平台

## 專案結構

```
edutrack-ai/
├── docker-compose.yml                # 一鍵啟動（postgres + backend + frontend）
├── backend/                          # Flask (Python) RESTful API
│   ├── app/
│   │   ├── __init__.py               # App factory + Blueprint 註冊
│   │   ├── config.py                 # 環境配置 (JWT, DB, ChromaDB, LLM)
│   │   ├── models.py                 # SQLAlchemy 關聯模型
│   │   ├── routes/
│   │   │   ├── auth.py               # JWT httpOnly Cookie 認證
│   │   │   ├── ai_tutor.py           # RAG 串流聊天 (/api/chat)
│   │   │   ├── quizzes.py            # AI 動態測驗生成
│   │   │   ├── flashcards.py         # SM-2 間隔重複
│   │   │   └── analytics.py          # 弱項分析報告
│   │   ├── services/
│   │   │   ├── llm_client.py         # Provider 無關 LLM 層（OpenAI 相容 / Anthropic）
│   │   │   ├── prompt_rules.py       # 共用 prompt 規則（LaTeX 格式）
│   │   │   ├── chroma_store.py       # ChromaDB 初始化 + RAG 檢索
│   │   │   ├── document_ingest.py    # PDF/TXT/MD → 清理 → chunk → metadata
│   │   │   ├── classical_texts.py    # 12 指定 + 8 建議文言文（20 篇章）
│   │   │   ├── ai_engine.py          # LLM + RAG 編排
│   │   │   ├── quiz_generator.py     # 測驗 JSON 生成與驗證
│   │   │   ├── essay_grading.py      # 英文作文批改（C/L/O）
│   │   │   ├── math_hint.py          # 數學步驟提示
│   │   │   ├── flashcard_service.py  # SM-2 演算法
│   │   │   └── analytics.py          # 弱項分析 + 週趨勢
│   │   └── data/
│   │       ├── chroma_store/         # 本地向量資料庫持久化目錄
│   │       └── materials/            # 課程教材（PDF，見該目錄 README）
│   ├── scripts/
│   │   ├── init_chroma.py            # ChromaDB 初始化 CLI
│   │   ├── ingest_classical.py       # 將文言文寫入向量庫（可重複執行）
│   │   ├── ingest_documents.py       # 將教材 PDF 寫入向量庫
│   │   ├── inspect_chroma.py         # 檢視向量庫內容／語意搜尋
│   │   ├── seed_db.py                # 課程科目／課題／知識點（upsert）
│   │   ├── seed_attempts.py          # 合成測驗資料（弱項分析用）
│   │   └── wait_for_db.py            # Docker 啟動時等 DB 就緒
│   ├── tests/                        # pytest（SM-2 / chunking / analytics）
│   ├── Dockerfile                    # python:3.12-slim + gunicorn
│   ├── docker-entrypoint.sh          # migrate → seed → ingest → gunicorn
│   ├── requirements.txt
│   ├── .env.example
│   └── run.py
└── frontend/                         # React (TypeScript) SPA
    ├── src/
    │   ├── components/
    │   │   ├── Auth/                 # 登入／註冊 + 路由守衛
    │   │   ├── common/               # ChatPanel / MarkdownMath (Markdown+KaTeX) 共用元件
    │   │   ├── ChatBot/              # SSE 串流 RAG 聊天
    │   │   ├── ClassicalChinese/     # 文言文雙欄對照 + AI 導師
    │   │   ├── MathHint/             # 數學 Method Marks 步驟引導
    │   │   ├── EssayGrader/          # 英文作文批改報告
    │   │   ├── Dashboard/            # Recharts 雷達圖/折線圖
    │   │   ├── Flashcard/            # 3D 翻轉 + SM-2
    │   │   └── Quiz/                 # 動態測驗 JSON 渲染
    │   ├── context/
    │   │   └── AuthContext.tsx       # httpOnly Cookie 認證封裝
    │   ├── lib/
    │   │   ├── api.ts                # fetch 封裝（credentials + CSRF token）
    │   │   └── utils.ts              # cn() Tailwind 合併工具
    │   ├── index.css                 # HKDSE 主題 + Glassmorphism
    │   ├── App.tsx
    │   └── main.tsx
    ├── tailwind.config.ts            # Primary/Secondary/Accent 色板
    ├── vite.config.ts
    ├── Dockerfile                    # node build → nginx
    ├── nginx.conf                    # SPA fallback + /api proxy
    └── package.json
```

## 快速啟動

### Backend

> 需求：**Python 3.12**（chromadb / torch 尚未支援 3.13+）、Docker（用於 PostgreSQL）

```bash
# 1. 啟動 PostgreSQL 16（Docker）
docker run -d --name edutrack-postgres \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=edutrack_ai -p 5432:5432 \
  -v edutrack_pgdata:/var/lib/postgresql/data --restart unless-stopped \
  postgres:16-alpine

# 2. 安裝依賴
cd backend
py -3.12 -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
copy .env.example .env           # 填入 ANTHROPIC_API_KEY（並設定 SECRET_KEY / JWT_SECRET_KEY）

# 3. 初始化資料庫與向量庫
flask --app run.py db init
flask --app run.py db migrate -m "initial schema"
flask --app run.py db upgrade
python scripts/seed_db.py        # 建立科目／課題／知識點
python scripts/init_chroma.py    # 建立 ChromaDB collection 並寫入種子內容

# 4. 啟動
python run.py                    # http://127.0.0.1:5000
```

### Frontend

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

---

## Docker 一鍵啟動（全棧）

想一條指令起齊 **PostgreSQL + Flask + Nginx 前端**（唔使喺本機裝 Python / Node）：

```bash
# 前置：backend/.env 必須存在（由 .env.example 複製並填好 LLM_API_KEY）
cd edutrack-ai
docker compose up --build
```

| 服務 | 容器內 | 對外 |
|------|--------|------|
| `frontend` | Nginx :80 | **http://localhost:8080** ← 開呢個 |
| `backend` | gunicorn :5000 | 只經 Nginx 代理，不對外 |
| `postgres` | :5432 | 只供內部網絡，不對外 |

**自動化啟動流程**（`docker-entrypoint.sh`）：
1. 等待 PostgreSQL 就緒（`pg_isready` + healthcheck）
2. `flask db upgrade` 套用遷移
3. `seed_db.py` 建立課程資料（已存在則略過）
4. `init_chroma.py` 初始化向量庫（已存在則略過）
5. 以 gunicorn（gthread、timeout 300s，支援 SSE）啟動

**常用指令**：

```bash
docker compose logs -f backend     # 睇後端 log
docker compose down                # 停止（資料保留於 volume）
docker compose down -v             # 停止並清除所有資料
docker compose up --build -d       # 背景重建並啟動
```

**重點設計**：
- Nginx 設 `proxy_buffering off`，確保 RAG 的 SSE 串流即時推送。
- 後端 image 用 CPU-only torch（`--index-url .../whl/cpu`）並預先下載多語言 embedding 模型，首次查詢免等下載。
- JWT 用 httpOnly Cookie，經 Nginx 同源代理，CSRF double-submit 照常運作。
- 秘密（`.env`）透過 `env_file` 注入，**不會被打包進 image 或推送 Git**。
- 若本機已用 `docker run` 起了 `edutrack-postgres`（開發用），兩者不會衝突（compose 的 postgres 不發佈 host 埠）；但建議 `docker stop edutrack-postgres` 省資源。

## API 端點一覽

| Method | Endpoint | 說明 |
|--------|----------|------|
| POST | `/api/auth/register` | 用戶註冊 |
| POST | `/api/auth/login` | 登入 (JWT → httpOnly Cookie) |
| POST | `/api/auth/logout` | 登出（清除 Cookie） |
| GET | `/api/auth/me` | 取得目前登入用戶 |
| POST | `/api/chat/query` | RAG 非串流問答 |
| POST | `/api/chat/stream` | RAG SSE 串流問答 |
| POST | `/api/chat/grade-essay` | 英文作文批改（HKEAA C/L/O） |
| POST | `/api/chat/math-hint` | 數學步驟提示（Method Marks） |
| GET | `/api/quiz/subjects` | 科目／課題清單 |
| POST | `/api/quiz/generate` | AI 動態生成測驗 |
| POST | `/api/quiz/submit` | 提交測驗答案 |
| GET | `/api/quiz/attempt/<id>/results` | 測驗成績明細 |
| GET | `/api/analytics/report` | 弱項分析報告 |
| GET | `/api/analytics/trend` | 每週平均分趨勢 |
| GET | `/api/flashcards/due` | 今日待複習記憶卡 |
| POST | `/api/flashcards/review` | SM-2 複習評分 |
| POST | `/api/flashcards/generate-from-mistakes` | 由錯題生成記憶卡 |

> 認證採 JWT httpOnly Cookie + CSRF double-submit：所有非 GET 請求必須帶 `X-CSRF-TOKEN`（前端已由 `src/lib/api.ts` 自動處理）。

## 技術棧

- **Frontend**: React 18 + TypeScript + Tailwind CSS + Vite
- **Backend**: Flask + SQLAlchemy + Flask-JWT-Extended
- **Database**: PostgreSQL (關聯數據) + ChromaDB (向量 RAG)
- **LLM**: Provider 無關（OpenAI 相容端點，如 TeamoRouter `deepseek-flash-free`；或原生 Anthropic）
- **Embedding**: sentence-transformers (multilingual)

## LLM 設定

`.env` 預設指向 TeamoRouter（OpenAI 相容）：

```env
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.teamorouter.com/v1
LLM_API_KEY=<你的 TeamoRouter API key>
LLM_MODEL=deepseek-flash-free
```

若改用原生 Anthropic：設 `LLM_PROVIDER=anthropic` 並填 `ANTHROPIC_API_KEY`。

## 課程教材（RAG）Ingestion

把 syllabus / past paper / 筆記放入 `backend/data/materials/<subject>/<source_type>/`，詳見該目錄的 `README.md`。

```powershell
cd backend ; .\venv\Scripts\activate
python scripts\ingest_documents.py                 # 全部
python scripts\ingest_documents.py --subject math  # 單科
python scripts\ingest_documents.py --reset         # 清空後重入
python scripts\inspect_chroma.py --source-type past_papers
python scripts\inspect_chroma.py --search "判別式"
```
- 支援 `.pdf` / `.txt` / `.md`；掃描版 PDF 需先 OCR。
- 可用 `<檔名>.pdf.meta.yml` 逐檔覆寫 metadata（`year`、`paper`、`knowledge_point_code`…）。
- Docker 啟動時會自動執行 `--if-empty`（首次入，之後略過）。

## 合成測驗資料（Data-Driven Weakness Analysis）

```powershell
python scripts\seed_attempts.py            # 20 學生 × 10 測驗（1000 明細）
python scripts\seed_attempts.py --reset    # 先清除 demo 資料
```
- 產生 `demo1@demo.local` … `demo20@demo.local`（密碼 `demo12345`），分佈於過去 8 週。
- 用嚟展示弱項雷達圖、推薦與週趨勢（`/api/analytics/trend`）。

## 測試

```powershell
cd backend ; .\venv\Scripts\activate
python -m pytest        # 15 tests：SM-2 / chunking / analytics
```

## 前端渲染
LLM 輸出經 `MarkdownMath`（react-markdown + remark-math + rehype-katex）渲染，支援 Markdown 與 KaTeX；`normalizeMath()` 會把 `\(...\)`、`\[...\]` 正規化並包裹裸 LaTeX。

---

## 用 Git / GitHub 備份與換電腦

目標：只把 **FYP 原始碼**放上 GitHub（其餘 workspace 檔案、`venv`、`node_modules`、`.env` 都不上傳）。

### 公司在公司電腦：push

```powershell
cd "edutrack-ai"          # 只對 FYP 資料夾做 git
git init
git add .
git status                # 檢查：唔應該見到 venv/ node_modules/ .env
git commit -m "Initial commit: EduTrack AI FYP"

# 喺 GitHub 網頁開一個新 repo（唔好勾 Add README / .gitignore）
git branch -M main
git remote add origin https://github.com/<你的帳號>/edutrack-ai.git
git push -u origin main
```

確認冇洩漏機密：
```powershell
git ls-files | Select-String "\.env"
# 應該只出現 backend/.env.example，唔會有 backend/.env
```

### ⚠️ `.env` 唔會上 GitHub
因為 `.gitignore` 已排除 `.env`（裡面有 API key）。返屋企要**另外帶**：
- 用密碼管理器（1Password / Bitwarden）存住 `LLM_API_KEY` 等，返屋企重建 `.env`；或
- 只帶 non-secret 設定，key 到屋企重新貼。

### 屋企電腦：clone 並還原環境

```powershell
# 先安裝：Git、Python 3.12、Node.js LTS、Docker Desktop
git clone https://github.com/<你的帳號>/edutrack-ai.git
cd edutrack-ai
```

**方法 A：Docker 一鍵（最簡單）**
```powershell
copy backend\.env.example backend\.env   # 填入你的 LLM_API_KEY
docker compose up --build                # → http://localhost:8080
```
（DB、遷移、seed、Chroma 全部自動處理，唔使裝 Python/Node。）

**方法 B：原生開發**
```powershell
# 後端
cd backend
py -3.12 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env                   # 填 LLM_API_KEY / SECRET_KEY / JWT_SECRET_KEY
docker start edutrack-postgres           # 或 docker compose up -d postgres
flask --app run.py db upgrade
python scripts\seed_db.py
python scripts\init_chroma.py
python run.py

# 前端（另開 terminal）
cd ..\frontend
npm install
npm run dev
```

> 之後日常更新：公司 `git add . && git commit -m "..." && git push`；屋企 `git pull` 即可。
> 只有**原始碼**同步；資料庫資料與 ChromaDB 索引屬本機 runtime，各自重建即可。
