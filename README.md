# Aetherius AI Platform

> **Simple on the surface. Powerful underneath.**

Aetherius AI is a next-generation AI Operating Environment combining adaptive local execution, cloud reasoning engines, PostgreSQL + pgvector storage, role-tailored workspaces, task state continuity, and hardware-native capability detection.

---

## 🏛️ Phase 1 Architecture Overview

```
                                 AETHERIUS DESKTOP
                           (Electron + React + Vite + Tailwind)
                                         │
                                   REST / WebSocket
                                         │
                                         ▼
                                AETHERIUS CORE ENGINE
                               (FastAPI / Python 3.11+)
                                         │
                      ┌──────────────────┴──────────────────┐
                      ▼                                     ▼
           Hardware Detector & Compat Engine       SQLAlchemy 2.0 / Alembic
                      │                                     │
                      │                              PostgreSQL + pgvector
                      │                              - users
                      │                              - user_settings
                      │                              - workspaces
                      │                              - system_profiles
                      │                              - models (registry)
                      │                              - model_packages
                      │                              - audit_logs
```

---

## 🚀 Key Features Implemented in Phase 1

1. **Strict PostgreSQL Persistence**:
   - Zero SQLite dependencies.
   - Dedicated PostgreSQL database engine with `pgvector` compatibility and UUID-keyed schema.
   - Alembic migration environment and declarative SQLAlchemy 2.0 async session architecture.
   - Initial schemas for `users`, `user_settings`, `workspaces`, `system_profiles`, `models`, `model_packages`, and `audit_logs`.

2. **System & Hardware Detection Engine**:
   - Multi-platform hardware detection (`HardwareDetector`).
   - CPU identification (cores, logical threads, frequency, architecture).
   - Real-time RAM total, available, used, and percent consumption.
   - Dedicated & integrated GPU detection (NVIDIA CUDA, AMD ROCm, DirectML, Apple Metal).
   - Storage utilization and disk availability.
   - Compute tier classification (`Ultra`, `High`, `Medium`, `Low`, `Minimum`).

3. **Model Compatibility Engine**:
   - Model memory footprint estimation (weights + KV cache overhead).
   - Multi-tier compatibility scoring (Compatible, Maybe Compatible, Not Recommended).
   - Recommended execution strategy (Local GPU, Hybrid GPU+CPU, Local CPU/RAM, Cloud).
   - Tailored quantization recommendation (Q4_K_M, Q5_K_M, Q8_0, FP16).

4. **Multi-Role Workspaces Foundation**:
   - Seeded system presets for `General`, `Developer`, `Student`, `Research`, `HR`, `Sales`, `Finance`, `Content`, and `Custom`.
   - Workspace isolation for system instructions, tool capabilities, and preferred models.

5. **Desktop Client (Electron + React 18 + TypeScript + Vite + Tailwind CSS)**:
   - **Step 1: Welcome Screen**: Premium hero introducing Aetherius.
   - **Step 2: System Analyzing Screen**: Live animated hardware telemetry scan and compute tier computation.
   - **Step 3: Recommended AI**: Hardware-matched models and curated model packages with one-click installation toggle.
   - **Step 4: Initial Workspace Picker**: Role-tailored workspace selection.
   - **Main Shell**: Sidebar navigation, active workspace indicators, real-time hardware telemetry pills, model registry manager, and platform settings.

---

## 🛠️ Quick Start & Development

### 1. Requirements
- Node.js 18+ and npm
- Python 3.11+
- PostgreSQL 16+ or Docker

### 2. Start with Development Runner

#### Windows:
```cmd
start-dev.bat
```

#### Cross-Platform Python Runner:
```bash
python run_dev.py
```

#### Docker Compose (PostgreSQL + pgvector):
```bash
docker compose up -d postgres
```

### 3. Run Automated Tests

#### Backend & Hardware Engine Test Suite:
```bash
.\.venv\Scripts\python -m pytest backend/tests -v
```

#### Frontend Desktop App Build:
```bash
cd apps/desktop
npm run build
```
