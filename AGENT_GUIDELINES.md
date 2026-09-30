# AETHERIUS AI — AGENT INSTRUCTIONS & ENGINEERING REFERENCE

This document serves as the mandatory reference for any AI assistant, developer, or agent working on the **Aetherius AI** codebase. Whenever starting a new session or continuing development, follow these principles and guidelines strictly.

---

## 1. Core Engineering Principles

1. **Root Cause Analysis First**:
   - Never guess or apply superficial "band-aids".
   - Trace the exact execution path across frontend and backend before modifying code.
   - Identify the exact component, state variable, or endpoint causing an issue.

2. **Respect Existing Architecture**:
   - Do NOT rewrite or replace entire working subsystems unnecessarily.
   - Do NOT introduce fake responses, hardcoded answers, or mock data to hide underlying problems.
   - Maintain consistency with FastAPI (backend), Electron + React + Tailwind + TypeScript (frontend), and PostgreSQL / pgvector.

3. **Validation & Verification Before Committing**:
   - Always verify TypeScript and frontend builds: `npm run build` in `apps/desktop`.
   - Always run the backend pytest suite: `python -m pytest backend/tests/test_entity_grounding.py backend/tests/test_architectural_pipeline.py -v`.
   - On Windows PowerShell, use `;` as the command separator instead of `&&`.

---

## 2. User-Facing Chat & Response Formatting (Zero System Leakage)

### Strict Separation: Internal AI Pipeline vs. User-Facing Response
The user interface must strictly provide clean, natural, modern conversational output (identical to ChatGPT, Claude, or Gemini).

### Forbidden in User-Facing Responses
Never output internal system metadata, debug traces, or routing labels in the normal chat stream:
- ❌ `Active Conversation Topic:`
- ❌ `Response:`
- ❌ `Location Context:`
- ❌ `Relevant Information:`
- ❌ `Next Steps:`
- ❌ `RAG Knowledge Enabled / Disabled`
- ❌ `Memory status / Retrieval scores / Confidence scores`
- ❌ `Provider / Runtime / Execution plan / Intent labels`

All internal diagnostics must stay in logging systems or dedicated debug panels—never in the direct stream seen by the user.

---

## 3. Entity-Aware Query Intelligence & Grounding Hierarchy

### Anti-Hallucination & Factual Grounding
When answering factual questions about real-world entities (companies, organizations, people, software, products, institutions):

1. **Entity & Intent Detection**:
   - Detect named entities (e.g. "ERBrains", "DeepSeek", "LangChain").
   - Resolve entity references across multi-turn conversations (e.g. "What about their founders?").
   - Do not rely solely on temporal keywords ("today", "latest", "recent") to trigger external research.

2. **Knowledge Source Trust Hierarchy**:
   - **Tier 1: User-Uploaded Documents / Explicit Workspace Data** (Highest priority for private context queries).
   - **Tier 2: Trusted Internal Knowledge / Enterprise RAG** (For proprietary company information).
   - **Tier 3: Web Search / Grounding** (`ddgs` / live web providers when answering queries about external entities or public information).
   - **Tier 4: Direct Model Weights** (Only for general conceptual queries, e.g. "What is polymorphism?", "How do for-loops work?").

3. **Closed-Loop Answer Validation**:
   - Verify that facts claimed in the final response are grounded in retrieved evidence.
   - If evidence is unavailable, state facts neutrally without inventing founders, funding amounts, or unsupported capabilities.

---

## 4. UI / UX Design & Frontend Standards

1. **Layout & Text Overflow Prevention**:
   - Use `min-w-0 flex-1 truncate` with native title tooltips on headers, titles, and model names.
   - Container cards must use clean flexbox or grid layouts with `overflow-hidden` or controlled scrolling.
   - Avoid hardcoded fixed-width spans that cause text clipping or badge breaking.

2. **Clean Badges & Metric Formatting**:
   - Format large numbers with human-readable notation (e.g., `1.42M`, `310K`) via `formatNumber()`.
   - Strip messy internal tag prefixes (e.g., `#task_categories:`, `#license:`, `#language:`).
   - Limit card category tags to a maximum of 3 clean pill badges.

3. **Streaming & Chat Experience**:
   - **Stop Response Support**: Always support user cancellation via `AbortController` and backend cancellation signals.
   - **Natural Autoscroll**: Allow users to scroll freely during generation; only auto-scroll if the user is already near the bottom.
   - **Composer State**: Maintain robust state transitions (`isGenerating`, `isUploading`) so inputs clear promptly upon sending and do not get stuck.

---

## 5. Model Management & Hugging Face Hub Integration

1. **Global Live Model Repository**:
   - Connect directly to Hugging Face Hub APIs (`/api/models`, `/api/datasets`).
   - Allow dynamic sorting by trending, downloads, and task categories.
   - Provide pagination ("Load More Models" / "Load More Datasets") without restrictive hardcoded limits.

2. **Local Model Management (Ollama / GGUF / ONNX)**:
   - Check model installation status and health before streaming.
   - Calculate hardware compatibility (RAM, VRAM, GPU quantization) to guide the user.

---

## 6. Directory Structure & Key Files

```
aetherius_ai/
├── apps/
│   └── desktop/                   # Electron + React + Tailwind frontend
│       ├── src/
│       │   ├── components/
│       │   │   ├── chat/          # ChatInterface, MessageList, Composer
│       │   │   └── models/        # ModelRegistryView, Local/HF tabs
│       │   └── services/api.ts    # Frontend API client (FastAPI bridge)
│       └── package.json
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/      # chat.py, models.py, rag.py, memory.py
│   │   ├── services/              # chat_service, huggingface_service, model_manager
│   │   └── services/evidence/     # web_search_providers, query_intelligence
│   └── tests/                     # test_entity_grounding.py, test_architectural_pipeline.py
├── AGENT_GUIDELINES.md            # This standard reference file
├── README.md                      # Project documentation
└── docker-compose.yml             # PostgreSQL & pgvector container configuration
```

---

## 7. Fast-Start Command Reference

### Running Tests (Backend)
```powershell
python -m pytest backend/tests/test_entity_grounding.py backend/tests/test_architectural_pipeline.py -v
```

### Building Desktop App (Frontend)
```powershell
cd apps/desktop
npm run build
```

### Git Workflow (Windows PowerShell)
```powershell
git add . ; git commit -m "feat/fix: <description>" ; git push origin main
```
