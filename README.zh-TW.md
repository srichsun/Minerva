# Doc AI Assistant

[English](README.md) · **中文**

一個 **RAG（檢索增強生成）文件問答 API**。你載入一組文件（產品說明、政策、FAQ），
使用者用自然語言提問。服務會檢索相關段落，請 Claude **只根據這些段落**回答，並把
答案連同來源一起回傳。如果文件裡沒有答案，它會直接說不知道，而不是亂猜。

Demo 知識庫是一個產品 **客服助手**（方案、退換貨政策、保固）。把 `data/` 裡的檔案
換掉，它就變成內部知識庫、技術文件問答機器人等等。

## 為什麼用 RAG（而不是直接用 ChatGPT）

通用聊天機器人不知道你的私有文件，而把整份文件塞進每次 prompt 既貴又會撞到 context
上限。RAG 只檢索相關片段，所以答案 **更省、有根據、還能標出來源** —— 這正是企業會
自己建的東西。

## 架構

```
                灌入（離線）                          查詢（每次請求）
  data/*.pdf,*.md ──> 切塊 ──> embed ──> Chroma        問題
                                            │            │
                                            └── 檢索最相關的 top-k 片段
                                                         │
                                        組 prompt（context + 問題）
                                                         │
                                              Claude（Anthropic API）
                                                         │
                                             答案 + 來源引用
```

- **Embedding** 用 Chroma 內建模型在本地跑 —— 灌入與檢索都不需要 API key。
- 只有 **產生答案**（`/chat`）這步會呼叫 Anthropic API。

## 技術選型

| 部位       | 選擇       | 為什麼不是其他 |
|------------|------------|----------------|
| Web 框架   | FastAPI    | Async + 型別 + 自動 Swagger 文件；做 API 比 Django 輕。 |
| 套件管理   | uv         | 一個工具搞定 venv + 鎖版本，比 pip/poetry 快很多。 |
| 向量庫     | Chroma     | 內嵌、零 infra；不用 SaaS 帳號（Pinecone）或多架 DB（pgvector）。 |
| LLM        | Claude     | Anthropic SDK 乾淨；model 可設定，預設 `claude-haiku-4-5`（開發便宜）。 |
| Embedding  | Chroma 本地（all-MiniLM） | 預設免 key、免費；需要時再切雲端模型。 |

## 專案結構

```
app/
  config.py   從 env / .env 讀設定
  main.py     FastAPI 路由：/health, /search, /chat, /agent
  llm.py      Anthropic client + generate() 小工具
  store.py    Chroma client + 可插拔 embedding provider
  rag.py      讀檔/切塊/灌入 + 檢索 + 組 prompt
  tools.py    agent 工具：search_documents, lookup_order
  agent.py    tool-use 迴圈（Claude 自己挑工具）
  sessions.py in-memory 對話歷史
scripts/
  ingest.py   把 data/ 灌進向量庫的 CLI
data/          你的來源文件（gitignored）
tests/         pytest（LLM 與檢索都 mock，不需 API key）
```

## 安裝與啟動

```bash
# 1. 安裝依賴（uv 依 lockfile 建 venv）
uv sync

# 2. 填入 Anthropic key（只有 /chat 需要）
cp .env.example .env         # 編輯 .env 貼上你的 key

# 3. 把文件灌進向量庫（第一次會下載 embedding 模型）
uv run python -m scripts.ingest

# 4. 啟動 API
uv run uvicorn app.main:app --reload
```

打開 http://127.0.0.1:8000/docs 就是互動式 Swagger 介面。

## Endpoints

| Method | Path         | 說明 |
|--------|--------------|------|
| GET    | `/health`    | 存活檢查。 |
| GET    | `/search?q=` | 回傳 top-k 檢索片段（檢索品質檢查；不呼叫 LLM、不需 key）。 |
| POST   | `/chat`      | 固定 RAG：檢索 → 回答。`{"question"}` → `{"answer", "sources"}`。 |
| POST   | `/agent`     | Agent：Claude 自己挑工具。`{"question", "session_id?"}` → `{"answer", "tools_used", "session_id"}`。 |

`/chat` 與 `/agent` 都需要 `ANTHROPIC_API_KEY`。

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How much does an iPhone screen repair cost with AppleCare?"}'

curl -X POST http://127.0.0.1:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the status of order 1001, and can I still return it?"}'
```

## RAG（`/chat`）vs Agent（`/agent`）

兩者都從同一個知識庫回答問題，差別在於 **誰掌控流程**。

- **`/chat`（RAG）** 跑 *固定* 流程：一定先檢索，再回答。簡單、可預測 —— 適合每個
  問題都是「去文件裡查一件事」的情況。
- **`/agent`** 把檢索包成一個 `search_documents` **工具**（外加一個 `lookup_order`
  工具），讓 Claude 自己決定 *要呼叫哪些* 工具、*呼叫幾次*。像「訂單 1001 狀態、
  還能退嗎」這種問題，agent 會**自己同時呼叫兩個工具**。它也透過 `session_id`
  保留對話記憶，所以追問（「它幾號到？」）能延續上下文。

Agent 是 RAG 檢索之上很自然的 *「加一層」* —— 同一份檢索 code，包成工具而已。

## 設計決策與取捨

- **預設本地 embedding** —— 開發時免費、離線；需要更高檢索品質時，`openai` provider
  只差一個環境變數。每個 provider 各自一個 collection（向量維度不同）。
- **段落感知切塊** —— 打包整段而不是每 N 字硬切，讓每個 chunk 是乾淨的語意單位，在
  範例查詢上明顯降低了檢索距離。
- **有根據的回答** —— system prompt 要求模型只根據檢索到的內容回答、答不出來就說
  「不知道」，避免亂編政策。`/chat` 會回傳來源，答案可稽核。
- **In-memory sessions** —— demo 夠用；正式部署會改用 Redis 或資料庫，讓歷史在重啟
  後保留、並能跨 worker 擴展。

## 測試

```bash
uv run pytest
```

LLM 呼叫與檢索都被 mock，所以整套測試不需 API key 就能跑。

## Roadmap

已完成：可插拔 embedding、段落感知切塊、Agent（tool use）、多輪記憶。待辦：

- 在 API 上加一個小型 web UI（React 聊天 widget）。
- 部署一個線上 demo 到 Hugging Face Spaces（延後 —— 公開的 `/chat` 會花到擁有者的
  API key，需先加上存取控制）。
