# Aetherius AI — Engineering & Operational Rules

> **Note**: For the full documentation suite, see [`docs/rules.md`](file:///c:/Users/VinayHattikal/OneDrive%20-%20ERBrains%20It%20Solutions%20Pvt%20ltd/Desktop/projects/aetherius_ai/docs/rules.md), [`docs/prd.md`](file:///c:/Users/VinayHattikal/OneDrive%20-%20ERBrains%20It%20Solutions%20Pvt%20ltd/Desktop/projects/aetherius_ai/docs/prd.md), [`docs/architecture.md`](file:///c:/Users/VinayHattikal/OneDrive%20-%20ERBrains%20It%20Solutions%20Pvt%20ltd/Desktop/projects/aetherius_ai/docs/architecture.md), [`docs/memory.md`](file:///c:/Users/VinayHattikal/OneDrive%20-%20ERBrains%20It%20Solutions%20Pvt%20ltd/Desktop/projects/aetherius_ai/docs/memory.md), and [`docs/design.md`](file:///c:/Users/VinayHattikal/OneDrive%20-%20ERBrains%20It%20Solutions%20Pvt%20ltd/Desktop/projects/aetherius_ai/docs/design.md).

## 1. Golden Architectural Principles

### Rule 1: PostgreSQL ONLY (Zero SQLite Fallback)
* **Strict Constraint**: The application must run **exclusively** on PostgreSQL 18 with `pgvector` and `asyncpg`.
* Under no circumstances shall SQLite, ChromaDB, TinyDB, or flat-file databases be used as a fallback. If the PostgreSQL cluster is unreachable, the system must report a clear database diagnostic error rather than silently degrading into local SQLite.
* **Database Connection Configuration**:
  - Host: `127.0.0.1`
  - Port: `54329` (Dedicated Aetherius PostgreSQL Cluster)
  - Database: `aetherius`
  - Encoding: Strictly `UTF8` with `LC_COLLATE 'C'` and `LC_CTYPE 'C'`.
  - Client Settings: `connect_args={"server_settings": {"client_encoding": "utf8"}}` to prevent Windows `WIN1252` encoding exceptions with emojis and unicode characters.

---

### Rule 2: Privacy-First Execution & Data Egress Boundaries
Every operation must strictly honor the user's active `privacy_mode`:

| Mode | Egress Allowed | Permitted Model Targets | Permitted Web Search | Document Storage |
| :--- | :--- | :--- | :--- | :--- |
| `LOCAL_ONLY` | ❌ NONE | Local Ollama models (`qwen2.5-coder`, `deepseek-r1`, `llama3.2`, etc.) | Disabled | Local PostgreSQL only |
| `HYBRID` | ⚠️ Controlled | Local models by default; Cloud models only for complex tasks when requested | Optional / Auto-filtered | Local PostgreSQL only |
| `CLOUD` | ✅ Full Cloud | Anthropic Claude, OpenAI GPT-4o, Groq Llama 3.3 | Enabled | Local PostgreSQL metadata |

* **Security Pre-Processing**: All outgoing prompts to external APIs must pass through the `PIISanitizer` (masking emails, phone numbers, credit card numbers, SSNs, and secret tokens).
* **Prompt Injection Defense**: Every user input must pass through the security inspector checking for jailbreak signatures before context assembly.

---

### Rule 3: Zero-Overhead Token-by-Token Streaming
* Chat completions must support real-time token streaming via Server-Sent Events (`POST /api/v1/chat/stream`).
* The desktop client must update the UI incrementally as tokens arrive without waiting for complete response generation.
* The streaming response structure must emit standard event packets:
  - `data: {"type": "init", "conversation_id": "...", "citations": [...]}`
  - `data: {"type": "token", "token": "..."}`
  - `data: {"type": "done", "message_id": "...", "content": "...", "citations": [...]}`

---

### Rule 4: Dynamic Hardware Intelligence & Model Lifecycle
1. **Telemetry Accuracy**: Telemetry detection must be non-blocking and execute in `< 500ms` using native OS APIs (`psutil`, `GPUtil`, `platform`).
2. **Real Ollama Lifecycle**:
   - Model installation (`POST /api/v1/models/{model_id}/install`) must invoke Ollama `/api/pull`.
   - Model uninstallation (`POST /api/v1/models/{model_id}/uninstall`) must invoke Ollama `DELETE /api/delete` to free physical disk space.
   - The UI must always display a confirmation modal dialog before deleting model weights.
   - The registry must dynamically synchronize `is_installed` status with actual Ollama tags on disk.

---

### Rule 5: Context Engine & Token Budgeting
1. **Token Constraint**: All prompts must be budgeted using `ContextEngine.assemble_context` against the target model's `context_size`.
2. **Prioritization Order**:
   - Level 1 (Top Priority): System Prompt & Workspace Guidelines.
   - Level 2: Relevant Retrieved RAG Document Chunks.
   - Level 3: Live Real-Time Web Search Results.
   - Level 4: Episodic & Semantic Long-Term Memories.
   - Level 5: Conversation History (fitted newest to oldest).
   - Level 6: Current User Message.
3. **Prompt Integrity**: When live web search or document knowledge is provided in the prompt, system instructions must mandate that the model use those facts and prohibit the model from stating *"I don't have access to real-time data"*.
4. **Terminal Citations**: The model must conclude responses with a structured `### Sources & References` section.

---

## 2. Code Quality & Language Standards

### Backend (Python & FastAPI)
* **Framework**: FastAPI with Python 3.10+ and Async/Await throughout.
* **ORM & Migrations**: SQLAlchemy 2.0 async engine with Alembic migrations.
* **Schemas**: Pydantic v2 `BaseModel` with `model_validator(mode="before")` for flexible parameter aliases (`model_id`/`model_name`, `use_web_search`/`enable_web_search`).
* **Formatting & Linting**: Ruff rules configured in `.ruff.toml` with line-length `100`.
* **Tests**: Pytest suite using `pytest-asyncio` with 100% pass requirement.

### Desktop Frontend (Electron, React & Tailwind)
* **Framework**: React 18, TypeScript (strict mode), Vite 5, Electron.
* **Styling**: Tailwind CSS with dark theme as primary (`#09090b` background, `#121215` cards, `#27272a` borders).
* **Viewport & Layout**:
  - Window frame must set `autoHideMenuBar: true` and remove the default Windows menu bar (`File Edit View Window Help`) to prevent viewport clipping.
  - Root containers must use `h-full w-full overflow-hidden` rather than rigid `h-screen`.
  - Content containers must use `overflow-y-auto` and avoid `my-auto` when content height can exceed the screen height.
  - Text selection must be universally enabled (`user-select: text`).
