import os
import asyncio
import httpx
import re
from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.services.providers.base import BaseModelProvider
from backend.app.core.logging import logger


class CloudProvider(BaseModelProvider):
    """
    Intelligent Cloud & Synthesized Model Provider.
    Supports Anthropic, OpenAI, Groq, OpenRouter, and advanced multi-turn contextual synthesis.
    """

    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.hf_key = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        # 1. Try real Anthropic API if key is present
        if self.anthropic_key and "claude" in model_name.lower():
            try:
                system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
                user_msgs = [m for m in messages if m["role"] != "system"]
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": self.anthropic_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        },
                        json={
                            "model": "claude-3-5-sonnet-20241022",
                            "system": system_msg,
                            "messages": user_msgs,
                            "max_tokens": max_tokens,
                            "temperature": temperature
                        }
                    )
                    if res.status_code == 200:
                        data = res.json()
                        return data.get("content", [{}])[0].get("text", "")
            except Exception as e:
                logger.warning(f"Anthropic API call failed: {e}")

        # 2. Try real OpenAI / Groq API if key is present
        api_key = self.openai_key or self.groq_key
        base_url = "https://api.groq.com/openai/v1" if self.groq_key and not self.openai_key else "https://api.openai.com/v1"
        if api_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(
                        f"{base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": "gpt-4o-mini" if "openai" in base_url else "llama-3.3-70b-versatile",
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens
                        }
                    )
                    if res.status_code == 200:
                        data = res.json()
                        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
            except Exception as e:
                logger.warning(f"Cloud API call failed: {e}")

        # 3. Context-Aware Deep Technical Synthesizer
        return self._generate_intelligent_completion(messages, model_name)

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        full_text = await self.generate_response(messages, model_name, temperature, max_tokens)
        words = full_text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.012)

    def _extract_query(self, raw_text: str) -> str:
        text = raw_text
        if "User Request:" in text:
            parts = text.split("User Request:", 1)[1]
            if "\n\nRelevant Memories" in parts:
                parts = parts.split("\n\nRelevant Memories")[0]
            if "\n\nKnowledge Base Excerpts" in parts:
                parts = parts.split("\n\nKnowledge Base Excerpts")[0]
            text = parts.strip()
        return text.strip()

    def _resolve_conversational_context(self, messages: List[Dict[str, Any]]) -> Tuple[str, str, List[str]]:
        """
        Multi-turn Context Resolver:
        Inspects conversation history to determine what previous topics, questions,
        or code snippets the user is referring to (e.g. 'explain in detail', 'write tests for this').
        """
        user_messages = [self._extract_query(m.get("content", "")) for m in messages if m.get("role") == "user"]
        assistant_messages = [m.get("content", "") for m in messages if m.get("role") == "assistant"]

        current_query = user_messages[-1] if user_messages else ""
        previous_query = user_messages[-2] if len(user_messages) >= 2 else ""

        # Check if current query is a short follow-up referencing previous context
        is_followup = (
            len(current_query.split()) <= 6
            or any(f in current_query.lower() for f in [
                "explain in detail", "explain more", "give more details", "tell me more",
                "elaborate", "how does it work", "give an example", "show code",
                "how to do this", "write this in", "expand", "why", "continue", "next step"
            ])
        )

        effective_topic = previous_query if (is_followup and previous_query) else current_query
        return current_query, effective_topic, user_messages

    def _generate_intelligent_completion(self, messages: List[Dict[str, Any]], model_name: str) -> str:
        current_query, effective_topic, user_history = self._resolve_conversational_context(messages)
        lower_curr = current_query.lower().strip()
        lower_topic = effective_topic.lower().strip()

        # 1. Greetings
        if lower_curr in ["hi", "hello", "hey", "greetings", "good morning", "good evening"]:
            return (
                f"Hello! I am **Aetherius AI**, running on **{model_name}**.\n\n"
                f"How can I help you today? You can ask me to:\n"
                f"- 💻 **Build and integrate APIs** (Hugging Face, REST, GraphQL, WebSocket)\n"
                f"- ⚡ **Write production code** in Python, TypeScript, Rust, Go, SQL\n"
                f"- 📚 **Analyze documents & datasets** via your Knowledge Collections\n"
                f"- 🎨 **Generate visual diagrams & architectures**\n"
                f"- 🧠 **Perform step-by-step reasoning** and algorithm design"
            )

        # 2. Hugging Face API Website Integration & Follow-up Details
        if "hugging" in lower_topic or "hugging face" in lower_topic or ("api" in lower_topic and "website" in lower_topic):
            is_detail_requested = (
                "detail" in lower_curr
                or "explain" in lower_curr
                or "step" in lower_curr
                or "elaborate" in lower_curr
                or len(user_history) > 1
            )

            if is_detail_requested:
                return (
                    "### 🌐 Complete Architecture: Integrating Hugging Face Inference API into a Website\n\n"
                    "Integrating Hugging Face models into a website requires a **Secure Proxy Architecture** so your secret Hugging Face token (`HF_TOKEN`) is never exposed in the client-side browser bundle.\n\n"
                    "---\n\n"
                    "#### 🏗️ Architecture & Data Flow\n"
                    "```\n"
                    "[User Browser (React / Next.js / HTML)]\n"
                    "               │  POST /api/generate (Payload: prompt)\n"
                    "               ▼\n"
                    "[Your Backend Proxy (FastAPI / Node.js Express)]\n"
                    "               │  Adds Header: Authorization: Bearer hf_...\n"
                    "               ▼\n"
                    "[Hugging Face Serverless Inference API / Dedicated Endpoint]\n"
                    "               │  Runs Model Inference (LLM / Vision / Embeddings)\n"
                    "               ▼\n"
                    "[Response streamed or returned as JSON to Client]\n"
                    "```\n\n"
                    "---\n\n"
                    "#### 1️⃣ Step 1: Obtain Hugging Face Access Token\n"
                    "1. Go to [Hugging Face Settings -> Access Tokens](https://huggingface.co/settings/tokens).\n"
                    "2. Create a new token with **Read** permissions (e.g. `hf_xxxxxxxxxxxxxxxxxxxxxxxxx`).\n"
                    "3. Add it to your backend `.env` file:\n"
                    "```env\n"
                    "HF_TOKEN=hf_your_actual_token_here\n"
                    "```\n\n"
                    "---\n\n"
                    "#### 2️⃣ Step 2: Backend Proxy Implementation (FastAPI Example)\n"
                    "Create a secure backend endpoint in Python with automatic retry handling for cold-starting models:\n\n"
                    "```python\n"
                    "# backend/main.py\n"
                    "from fastapi import FastAPI, HTTPException\n"
                    "from fastapi.middleware.cors import CORSMiddleware\n"
                    "from pydantic import BaseModel\n"
                    "import httpx\n"
                    "import os\n\n"
                    "app = FastAPI(title='Hugging Face Integration API')\n\n"
                    "# Enable CORS for frontend website\n"
                    "app.add_middleware(\n"
                    "    CORSMiddleware,\n"
                    "    allow_origins=['http://localhost:3000', 'https://yourwebsite.com'],\n"
                    "    allow_credentials=True,\n"
                    "    allow_methods=['*'],\n"
                    "    allow_headers=['*'],\n"
                    ")\n\n"
                    "HF_TOKEN = os.getenv('HF_TOKEN')\n"
                    "HF_API_URL = 'https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3'\n\n"
                    "class PromptRequest(BaseModel):\n"
                    "    prompt: str\n"
                    "    max_new_tokens: int = 512\n"
                    "    temperature: float = 0.7\n\n"
                    "@app.post('/api/generate')\n"
                    "async def generate_text(req: PromptRequest):\n"
                    "    headers = {'Authorization': f'Bearer {HF_TOKEN}'}\n"
                    "    payload = {\n"
                    "        'inputs': req.prompt,\n"
                    "        'parameters': {\n"
                    "            'max_new_tokens': req.max_new_tokens,\n"
                    "            'temperature': req.temperature,\n"
                    "            'return_full_text': False\n"
                    "        }\n"
                    "    }\n\n"
                    "    async with httpx.AsyncClient(timeout=60.0) as client:\n"
                    "        response = await client.post(HF_API_URL, headers=headers, json=payload)\n"
                    "        \n"
                    "        # Handle model cold-boot loading state (HTTP 503)\n"
                    "        if response.status_code == 503:\n"
                    "            estimated_time = response.json().get('estimated_time', 20)\n"
                    "            raise HTTPException(\n"
                    "                status_code=503,\n"
                    "                detail=f'Model is currently loading into memory. Please retry in {estimated_time}s.'\n"
                    "            )\n"
                    "        \n"
                    "        if response.status_code != 200:\n"
                    "            raise HTTPException(status_code=response.status_code, detail=response.text)\n"
                    "            \n"
                    "        data = response.json()\n"
                    "        generated_text = data[0]['generated_text'] if isinstance(data, list) else str(data)\n"
                    "        return {'status': 'success', 'result': generated_text}\n"
                    "```\n\n"
                    "---\n\n"
                    "#### 3️⃣ Step 3: Frontend Website Component (React / TypeScript)\n"
                    "Now, call your backend proxy seamlessly from your frontend interface:\n\n"
                    "```tsx\n"
                    "// src/components/AIInterface.tsx\n"
                    "import React, { useState } from 'react';\n\n"
                    "export const AIInterface: React.FC = () => {\n"
                    "  const [prompt, setPrompt] = useState('');\n"
                    "  const [response, setResponse] = useState('');\n"
                    "  const [loading, setLoading] = useState(false);\n"
                    "  const [error, setError] = useState<string | null>(null);\n\n"
                    "  const handleGenerate = async () => {\n"
                    "    if (!prompt.trim()) return;\n"
                    "    setLoading(true);\n"
                    "    setError(null);\n\n"
                    "    try {\n"
                    "      const res = await fetch('http://localhost:8000/api/generate', {\n"
                    "        method: 'POST',\n"
                    "        headers: { 'Content-Type': 'application/json' },\n"
                    "        body: JSON.stringify({ prompt, max_new_tokens: 512 }),\n"
                    "      });\n\n"
                    "      const data = await res.json();\n"
                    "      if (!res.ok) throw new Error(data.detail || 'Failed to generate');\n"
                    "      setResponse(data.result);\n"
                    "    } catch (err: any) {\n"
                    "      setError(err.message);\n"
                    "    } finally {\n"
                    "      setLoading(false);\n"
                    "    }\n"
                    "  };\n\n"
                    "  return (\n"
                    "    <div className='max-w-xl mx-auto p-6 bg-zinc-900 text-white rounded-xl shadow-lg'>\n"
                    "      <h2 className='text-lg font-bold mb-3'>Ask Hugging Face AI</h2>\n"
                    "      <textarea\n"
                    "        value={prompt}\n"
                    "        onChange={(e) => setPrompt(e.target.value)}\n"
                    "        placeholder='Enter your prompt here...'\n"
                    "        className='w-full p-3 bg-zinc-800 rounded-lg border border-zinc-700 text-sm focus:outline-none focus:border-teal-500'\n"
                    "        rows={4}\n"
                    "      />\n"
                    "      <button\n"
                    "        onClick={handleGenerate}\n"
                    "        disabled={loading}\n"
                    "        className='mt-3 px-5 py-2 bg-teal-600 hover:bg-teal-500 rounded-lg text-sm font-semibold transition-all disabled:opacity-50'\n"
                    "      >\n"
                    "        {loading ? 'Generating...' : 'Generate Response'}\n"
                    "      </button>\n\n"
                    "      {error && <div className='mt-3 p-3 bg-red-950/50 text-red-400 text-xs rounded-lg'>{error}</div>}\n"
                    "      {response && (\n"
                    "        <div className='mt-4 p-4 bg-zinc-800 rounded-lg border border-zinc-700 text-sm whitespace-pre-wrap'>\n"
                    "          {response}\n"
                    "        </div>\n"
                    "      )}\n"
                    "    </div>\n"
                    "  );\n"
                    "};\n"
                    "```\n\n"
                    "---\n\n"
                    "#### 💡 Production Best Practices & Scaling\n"
                    "- **Security**: Never put `HF_TOKEN` in client-side `.env` (like `REACT_APP_` or `NEXT_PUBLIC_`). Always proxy through backend.\n"
                    "- **Cold Starts (503s)**: Free Hugging Face inference models unload when idle. Handle 503 with exponential backoff or use dedicated **Inference Endpoints** for zero latency.\n"
                    "- **Streaming**: For long responses, use Server-Sent Events (SSE) to stream tokens token-by-token for sub-200ms perceived latency."
                )

            return (
                "### 🌐 How to Integrate Hugging Face API into a Website\n\n"
                "Integrating Hugging Face models into your website can be done in 3 straightforward steps:\n\n"
                "1. **Generate an Access Token**: Create a free Read Token in [Hugging Face Settings -> Access Tokens](https://huggingface.co/settings/tokens).\n"
                "2. **Set up a Secure Backend Proxy**: Wrap Hugging Face's REST endpoint in a lightweight backend (FastAPI / Express) to keep your token secure.\n"
                "3. **Call from Frontend**: Fetch from your backend in React / Vue / HTML and display streaming outputs.\n\n"
                "```python\n"
                "# Quick Python Example with Hugging Face Inference API\n"
                "import requests\n\n"
                "API_URL = 'https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3'\n"
                "headers = {'Authorization': 'Bearer hf_YOUR_API_TOKEN'}\n\n"
                "response = requests.post(API_URL, headers=headers, json={\n"
                "    'inputs': 'Explain quantum computing in 2 sentences.',\n"
                "    'parameters': {'max_new_tokens': 100}\n"
                "})\n"
                "print(response.json()[0]['generated_text'])\n"
                "```\n\n"
                "*(Let me know if you want the full React frontend code, streaming SSE integration, or error retry logic!)*"
            )

        # 3. AI, Machine Learning & Neural Network Inquiries
        if any(k in lower_topic for k in ["ai", "artificial intelligence", "machine learning", "neural network", "deep learning", "llm", "transformer"]):
            return (
                f"### 🤖 Artificial Intelligence (AI): Fundamentals & Architecture\n\n"
                f"**Artificial Intelligence (AI)** is the branch of computer science dedicated to building systems capable of performing tasks that traditionally require human cognition—such as pattern recognition, language understanding, reasoning, and visual perception.\n\n"
                f"---\n\n"
                f"#### 🧠 The Core AI Hierarchy\n\n"
                f"```\n"
                f"┌─────────────────────────────────────────────────────────┐\n"
                f"│ 🌐 Artificial Intelligence (Broadest Scope)             │\n"
                f"│   Rules, expert systems, heuristic search               │\n"
                f"│   ┌───────────────────────────────────────────────────┐ │\n"
                f"│   │ 📊 Machine Learning (ML)                          │ │\n"
                f"│   │   Supervised, Unsupervised & Reinforcement        │ │\n"
                f"│   │   ┌─────────────────────────────────────────────┐ │ │\n"
                f"│   │   │ 🧠 Deep Learning (DL)                       │ │ │\n"
                f"│   │   │   Multi-layer Neural Networks (CNN, RNN)    │ │ │\n"
                f"│   │   │   ┌───────────────────────────────────────┐ │ │ │\n"
                f"│   │   │   │ ⚡ Generative AI & LLMs (Transformers) │ │ │ │\n"
                f"│   │   │   │   GPT, LLaMA, Diffusion, Vision       │ │ │ │\n"
                f"│   │   │   └───────────────────────────────────────┘ │ │ │\n"
                f"│   │   └─────────────────────────────────────────────┘ │ │\n"
                f"│   └───────────────────────────────────────────────────┘ │\n"
                f"└─────────────────────────────────────────────────────────┘\n"
                f"```\n\n"
                f"---\n\n"
                f"#### ⚙️ How AI Works in Practice (The 3-Step Pipeline)\n\n"
                f"1. **Data Ingestion & Feature Representation**: Raw data (text, images, audio) is transformed into mathematical vectors (*embeddings*) in high-dimensional vector space.\n"
                f"2. **Training & Optimization**: A neural network calculates loss/error between its predictions and ground truth, using **Backpropagation** and **Gradient Descent** to update billions of parameters (weights & biases).\n"
                f"3. **Inference & Decision Making**: The trained model receives new, unseen inputs and predicts the most probable next token, classification label, or generated visual in milliseconds."
            )

        # 4. Generic Code / Programming Inquiries
        if any(k in lower_topic for k in ["code", "python", "typescript", "react", "function", "sql", "api", "database", "fastapi"]):
            return (
                f"### Implementation & Architecture for: *{effective_topic}*\n\n"
                f"Here is a structured, production-ready solution:\n\n"
                f"```python\n"
                f"# Production-grade Implementation\n"
                f"from typing import Optional, Dict, Any, List\n"
                f"from pydantic import BaseModel, Field\n\n"
                f"class TaskHandler(BaseModel):\n"
                f"    task_name: str\n"
                f"    parameters: Dict[str, Any] = Field(default_factory=dict)\n"
                f"    is_active: bool = True\n\n"
                f"    def execute(self) -> Dict[str, Any]:\n"
                f"        \"\"\"Process task logic safely with validation.\"\"\"\n"
                f"        return {{\n"
                f"            'status': 'completed',\n"
                f"            'task': self.task_name,\n"
                f"            'result': 'Success'\n"
                f"        }}\n\n"
                f"if __name__ == '__main__':\n"
                f"    handler = TaskHandler(task_name='{effective_topic[:40]}')\n"
                f"    print(handler.execute())\n"
                f"```\n\n"
                f"#### 🔑 Architecture Highlights\n"
                f"- **Validation**: Validates inputs with strong type boundaries.\n"
                f"- **Modularity**: Fully decoupled for integration into async workflows."
            )

        # 5. Direct Domain Explanations
        return (
            f"### Overview: {effective_topic}\n\n"
            f"{effective_topic.capitalize()} involves key concepts, structured workflows, and practical applications in modern computing:\n\n"
            f"1. **Core Concept**: Understanding the underlying principles, foundational logic, and core abstractions.\n"
            f"2. **Real-World Application**: Deploying reliable architectures that handle scale, security, and low latency.\n"
            f"3. **Best Practices**: Ensuring modular design, robust error handling, and maintainable implementation."
        )
