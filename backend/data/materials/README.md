# DSE 課程教材（RAG 來源）

把教材按以下結構放入，然後執行 ingestion 寫入 ChromaDB：

```
materials/
  <subject>/            # chinese | math | english
    syllabus/           # 課程指引
    past_papers/        # 歷屆試題（可連 mark scheme）
    notes/              # 筆記／補充材料
```

## 支援格式
`.pdf`、`.txt`、`.md`

## Ingestion
```powershell
cd edutrack-ai\backend
.\venv\Scripts\activate
python scripts\ingest_documents.py                 # 全部
python scripts\ingest_documents.py --subject math  # 單科
python scripts\ingest_documents.py --reset         # 清空後重新入
python scripts\ingest_documents.py --if-empty      # 已有就略過
```
檢查：
```powershell
python scripts\inspect_chroma.py --source-type past_papers
python scripts\inspect_chroma.py --search "二次方程 判別式"
```

## 自動推斷的 metadata
由資料夾路徑推斷：`subject`、`source_type`；由檔名推斷 `doc_title`。
另外會自動加：`origin=materials`、`source_file`、`page`、`chunk_index`、`language`。

## 逐檔覆寫 metadata（可選）
在 PDF 旁邊放一個 `<檔名>.pdf.meta.yml`，例如 `2023_p1.pdf.meta.yml`：
```yaml
year: 2023
paper: "Paper 1"
topic: 二次方程
knowledge_point_code: MATH-QUAD-03
language: zh-HK
source_type: past_papers
```
> 可用 key：`year`、`paper`、`question_no`、`topic`、`knowledge_point_code`、`language`、`source_type`、`doc_title`。

## 注意
- **掃描版 PDF** 抽唔到文字（會顯示 `no extractable text`），需要 OCR 後再入。
- 大檔案建議用 Git LFS（單檔 >100MB 會被 GitHub 拒絕）。
