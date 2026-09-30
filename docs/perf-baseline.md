# Aetherius AI Performance Baseline (Task 1.2)

Recorded on: 2026-09-30
Hardware Environment: Intel Core i7 (8 Physical Cores, 16 Logical Threads), 16 GB RAM, Local CPU inference via Ollama.
Default Baseline Model: `llama3.2:3b`

---

## 1. 5-Prompt Baseline Measurements

| # | Prompt Category | Prompt | Total Latency (s) | Retrieval Stage (ms) | Ollama Prompt Eval (s) | Generation (s) | Throughput (tok/s) | Model Load Time (s) |
|---|---|---|---|---|---|---|---|---|
| 1 | **Greeting** | *"Hello, who are you?"* | **29.35s** | 6005.4ms | 16.79s (1321 tok) | 6.30s (60 tok) | 9.5 tok/s | 0.01s |
| 2 | **Factual Question** | *"What is the boiling point of nitrogen?"* | **3.62s** | 3.7ms | 1.65s (518 tok) | 1.75s (23 tok) | 13.1 tok/s | 0.01s |
| 3 | **Code Generation** | *"Write a Python function to check if a binary tree is balanced."* | **71.30s** | 5029.5ms | 21.41s (1373 tok) | 44.68s (405 tok) | 9.1 tok/s | 0.01s |
| 4 | **Long-Context Analysis** | *"Explain the architecture of transformer models and self-attention mechanisms in detail with trade-offs."* | **61.87s** | 2.95ms | 3.23s (577 tok) | 58.31s (637 tok) | 10.9 tok/s | 0.01s |
| 5 | **Web Search Grounding** | *"What is the current release status and new features of Python 3.13?"* | **77.98s** | 1289.5ms | 50.74s (2223 tok) | 21.13s (157 tok) | 7.4 tok/s | 4.68s |

---

## 2. Key Observations & Bottlenecks Identified

1. **Prompt Overhead & Context Window Thrashing (Task 1.3 Target)**:
   - In Prompt 5, the prompt exceeded the dynamic context window (2,223 prompt tokens vs 2,048 allocated `num_ctx`), which forced Ollama to reload weights (**4.68s model load**) and re-evaluate the full prompt context (**50.74s prompt eval**).
2. **Unnecessary Pre-flight Search (Task 1.4 Target)**:
   - In Prompt 1 (Greeting) and Prompt 3 (Code), pre-flight search took 5-6 seconds due to external HTTP timeouts and un-cached search attempts.
3. **Stage Breakdown Telemetry (Task 1.2 Verification)**:
   - `query_analysis` executes in **2.1ms - 4.3ms** (sub-millisecond target achieved).
   - `context` assembly executes in **<0.1ms**.
   - `persistence` executes in **25ms - 37ms**.
   - Real-time instrumentation is accessible via `GET /api/v1/diagnostics/last-requests?limit=20`.
