import {
  HardwareProfile,
  ModelResponse,
  ModelPackageResponse,
  WorkspaceResponse,
  UserSettingsResponse,
  ConversationResponse,
  ChatAttachment,
  ChatCompletionRequest,
  ChatCompletionResponse,
  KnowledgeBaseResponse,
  KnowledgeBaseCreate,
  DocumentResponse,
  RAGSearchRequest,
  RAGSearchResult,
  WebSearchResult,
  MemoryResponse,
  MemoryCreate,
  MemorySearchRequest,
  MemorySearchResult,
  RouterEvaluationRequest,
  RouterEvaluationResponse,
  ToolDefinition,
  ToolExecutionRequest,
  ToolExecutionResponse,
  AgentDefinitionResponse,
  AgentTaskCreate,
  AgentTaskResponse,
  AuditLogResponse,
  SystemDiagnosticsResponse,
  HuggingFaceModelCard,
  HuggingFaceDatasetCard,
  ModelUpgradeSuggestion,
  ModelInstallProgress,
} from '../types';

const API_BASE_URL = 'http://127.0.0.1:8000';

class ApiService {
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        ...options,
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`API Error ${response.status}: ${errText}`);
      }

      return await response.json();
    } catch (err: any) {
      console.warn(`Fetch error for ${endpoint}:`, err);
      throw err;
    }
  }

  async checkHealth(): Promise<{ status: string; app: string; version: string }> {
    return this.request('/health');
  }

  async detectSystem(): Promise<HardwareProfile> {
    return this.request<HardwareProfile>('/api/v1/system/detect');
  }

  async saveSystemProfile(): Promise<{ id: string; profile: HardwareProfile; status: string }> {
    return this.request('/api/v1/system/save-profile', { method: 'POST' });
  }

  async getModels(): Promise<ModelResponse[]> {
    return this.request<ModelResponse[]>('/api/v1/models/?evaluate_compatibility=true');
  }

  async getModelPackages(): Promise<ModelPackageResponse[]> {
    return this.request<ModelPackageResponse[]>('/api/v1/models/packages');
  }

  async toggleModelInstalled(modelId: string): Promise<ModelResponse> {
    return this.request<ModelResponse>(`/api/v1/models/${modelId}/toggle-installed`, {
      method: 'POST'
    });
  }

  async installModel(modelId: string): Promise<ModelInstallProgress> {
    return this.request<ModelInstallProgress>(`/api/v1/models/${encodeURIComponent(modelId)}/install`, {
      method: 'POST'
    });
  }

  async uninstallModel(modelId: string): Promise<ModelResponse> {
    return this.request<ModelResponse>(`/api/v1/models/${encodeURIComponent(modelId)}/uninstall`, {
      method: 'POST'
    });
  }

  async getModelInstallStatus(modelIdentifier: string): Promise<ModelInstallProgress | null> {
    try {
      return await this.request<ModelInstallProgress>(`/api/v1/models/install/status/${encodeURIComponent(modelIdentifier)}`);
    } catch {
      return null;
    }
  }

  async getActiveModelInstalls(): Promise<ModelInstallProgress[]> {
    try {
      return await this.request<ModelInstallProgress[]>('/api/v1/models/install/active');
    } catch {
      return [];
    }
  }

  streamModelInstallProgress(
    modelIdentifier: string,
    callbacks: {
      onProgress?: (data: ModelInstallProgress) => void;
      onDone?: (data: ModelInstallProgress) => void;
      onError?: (err: Error) => void;
    }
  ): () => void {
    const controller = new AbortController();
    const url = `${API_BASE_URL}/api/v1/models/install/progress/${encodeURIComponent(modelIdentifier)}`;

    (async () => {
      try {
        const response = await fetch(url, {
          signal: controller.signal,
          headers: { Accept: 'text/event-stream' },
        });

        if (!response.ok) {
          throw new Error(`SSE error status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) return;

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith('data:')) {
              const dataStr = trimmed.replace(/^data:\s*/, '').trim();
              if (!dataStr) continue;
              try {
                const parsed: ModelInstallProgress = JSON.parse(dataStr);
                callbacks.onProgress?.(parsed);
                if (parsed.is_completed || parsed.status === 'completed') {
                  callbacks.onDone?.(parsed);
                }
              } catch (e) {
                console.debug('Failed to parse install event:', e);
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          console.warn('Install progress stream error:', err);
          callbacks.onError?.(err);
        }
      }
    })();

    return () => controller.abort();
  }

  // --- Hugging Face Hub & Upgrade Advisor Endpoints ---
  async getHFTrendingModels(category?: string): Promise<HuggingFaceModelCard[]> {
    const q = category ? `?category=${encodeURIComponent(category)}` : '';
    return this.request<HuggingFaceModelCard[]>(`/api/v1/models/huggingface/trending${q}`);
  }

  async searchHFModels(query: string): Promise<HuggingFaceModelCard[]> {
    return this.request<HuggingFaceModelCard[]>(`/api/v1/models/huggingface/search?q=${encodeURIComponent(query)}`);
  }

  async getHFDatasets(query?: string): Promise<HuggingFaceDatasetCard[]> {
    const q = query ? `?q=${encodeURIComponent(query)}` : '';
    return this.request<HuggingFaceDatasetCard[]>(`/api/v1/models/huggingface/datasets${q}`);
  }

  async getModelUpgradeSuggestions(): Promise<ModelUpgradeSuggestion[]> {
    return this.request<ModelUpgradeSuggestion[]>('/api/v1/models/upgrade-suggestions');
  }

  async installHFModel(repoId: string, quantization: string = 'Q4_K_M'): Promise<ModelInstallProgress> {
    return this.request<ModelInstallProgress>(`/api/v1/models/huggingface/install?repo_id=${encodeURIComponent(repoId)}&quantization=${encodeURIComponent(quantization)}`, {
      method: 'POST'
    });
  }

  async smartSwapModel(oldModelId: string, newRepoId: string, quantization: string = 'Q4_K_M'): Promise<ModelInstallProgress> {
    return this.request<ModelInstallProgress>('/api/v1/models/smart-swap', {
      method: 'POST',
      body: JSON.stringify({ old_model_id: oldModelId, new_repo_id: newRepoId, quantization })
    });
  }

  async importHFDataset(repoId: string, workspaceSlug: string = 'general', collectionName?: string): Promise<KnowledgeBaseResponse> {
    return this.request<KnowledgeBaseResponse>('/api/v1/knowledge/datasets/import-hf', {
      method: 'POST',
      body: JSON.stringify({ repo_id: repoId, workspace_slug: workspaceSlug, collection_name: collectionName }),
    });
  }

  async generateImage(prompt: string, aspectRatio: string = '1:1', stylePreset?: string, workspaceSlug: string = 'general'): Promise<{
    image_url: string;
    preview_url?: string;
    prompt: string;
    revised_prompt?: string;
    aspect_ratio: string;
    provider: string;
    model_name: string;
    width: number;
    height: number;
    seed: number;
  }> {
    return this.request('/api/v1/chat/generate-image', {
      method: 'POST',
      body: JSON.stringify({
        prompt,
        aspect_ratio: aspectRatio,
        style_preset: stylePreset,
        workspace_slug: workspaceSlug,
      }),
    });
  }

  async getWorkspaces(): Promise<WorkspaceResponse[]> {
    return this.request<WorkspaceResponse[]>('/api/v1/workspaces/');
  }

  async getSettings(): Promise<UserSettingsResponse> {
    return this.request<UserSettingsResponse>('/api/v1/settings/');
  }

  async updateSettings(updates: Partial<UserSettingsResponse>): Promise<UserSettingsResponse> {
    return this.request<UserSettingsResponse>('/api/v1/settings/', {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  // --- Phase 2: Chat & Conversation Endpoints ---
  async getConversations(workspaceSlug?: string): Promise<ConversationResponse[]> {
    const query = workspaceSlug ? `?workspace_slug=${encodeURIComponent(workspaceSlug)}` : '';
    return this.request<ConversationResponse[]>(`/api/v1/conversations/${query}`);
  }

  async getConversation(id: string): Promise<ConversationResponse> {
    return this.request<ConversationResponse>(`/api/v1/conversations/${id}`);
  }

  async createConversation(title: string, workspaceSlug: string = 'general'): Promise<ConversationResponse> {
    return this.request<ConversationResponse>('/api/v1/conversations/', {
      method: 'POST',
      body: JSON.stringify({ title, workspace_slug: workspaceSlug }),
    });
  }

  async deleteConversation(id: string): Promise<{ status: string; id: string }> {
    return this.request(`/api/v1/conversations/${id}`, { method: 'DELETE' });
  }

  async uploadChatAttachment(file: File): Promise<ChatAttachment> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/v1/chat/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Upload error ${response.status}: ${errText}`);
    }

    return await response.json();
  }

  async sendChatMessage(payload: ChatCompletionRequest): Promise<ChatCompletionResponse> {
    return this.request<ChatCompletionResponse>('/api/v1/chat/completions', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async streamChatMessage(
    payload: ChatCompletionRequest,
    callbacks: {
      onInit?: (data: { conversation_id: string; citations: any[]; model_used?: string; routing_reason?: string; image_url?: string }) => void;
      onImage?: (data: { image_url: string; prompt?: string }) => void;
      onToken?: (token: string) => void;
      onDone?: (data: { message_id: string; content: string; conversation_id: string; citations: any[]; model_used?: string; image_url?: string }) => void;
      onError?: (error: Error) => void;
    }
  ): Promise<void> {
    const url = `${API_BASE_URL}/api/v1/chat/stream`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Stream error ${response.status}: ${errText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No readable stream available');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            try {
              const data = JSON.parse(trimmed.slice(6));
              if (data.type === 'init' && callbacks.onInit) {
                callbacks.onInit(data);
              } else if (data.type === 'image' && callbacks.onImage) {
                callbacks.onImage(data);
              } else if (data.type === 'token' && callbacks.onToken) {
                callbacks.onToken(data.token);
              } else if (data.type === 'done' && callbacks.onDone) {
                callbacks.onDone(data);
              }
            } catch (err) {
              console.debug('Failed to parse SSE line:', line);
            }
          }
        }
      }
    } catch (err: any) {
      if (callbacks.onError) callbacks.onError(err);
      else throw err;
    }
  }

  // --- Phase 2: Knowledge Base & RAG Endpoints ---
  async getKnowledgeBases(workspaceSlug: string = 'general'): Promise<KnowledgeBaseResponse[]> {
    return this.request<KnowledgeBaseResponse[]>(`/api/v1/knowledge/?workspace_slug=${encodeURIComponent(workspaceSlug)}`);
  }

  async createKnowledgeBase(data: KnowledgeBaseCreate): Promise<KnowledgeBaseResponse> {
    return this.request<KnowledgeBaseResponse>('/api/v1/knowledge/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async uploadDocument(kbSlug: string, file: File): Promise<DocumentResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const url = `${API_BASE_URL}/api/v1/knowledge/${encodeURIComponent(kbSlug)}/upload`;
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Upload error ${response.status}: ${errText}`);
    }

    return await response.json();
  }

  async searchKnowledge(request: RAGSearchRequest): Promise<RAGSearchResult> {
    return this.request<RAGSearchResult>('/api/v1/knowledge/search', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async deleteDocument(documentId: string): Promise<{ status: string; id: string }> {
    return this.request(`/api/v1/knowledge/documents/${documentId}`, { method: 'DELETE' });
  }

  // --- Phase 2: Web Search Endpoints ---
  async performWebSearch(query: string, maxResults: number = 5): Promise<WebSearchResult> {
    return this.request<WebSearchResult>('/api/v1/web-search/', {
      method: 'POST',
      body: JSON.stringify({ query, max_results: maxResults }),
    });
  }

  // --- Phase 3: Memory Engine Endpoints ---
  async getMemories(workspaceSlug?: string, memoryType?: string): Promise<MemoryResponse[]> {
    const params = new URLSearchParams();
    if (workspaceSlug) params.append('workspace_slug', workspaceSlug);
    if (memoryType) params.append('memory_type', memoryType);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return this.request<MemoryResponse[]>(`/api/v1/memory/${qs}`);
  }

  async createMemory(data: MemoryCreate): Promise<MemoryResponse> {
    return this.request<MemoryResponse>('/api/v1/memory/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async searchMemories(request: MemorySearchRequest): Promise<MemorySearchResult> {
    return this.request<MemorySearchResult>('/api/v1/memory/search', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async deleteMemory(memoryId: string): Promise<{ status: string; id: string }> {
    return this.request(`/api/v1/memory/${memoryId}`, { method: 'DELETE' });
  }

  // --- Phase 3: Intelligent Model Router ---
  async evaluateRouter(request: RouterEvaluationRequest): Promise<RouterEvaluationResponse> {
    return this.request<RouterEvaluationResponse>('/api/v1/router/evaluate', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // --- Phase 3: Workspace Tools ---
  async getWorkspaceTools(workspaceSlug?: string): Promise<ToolDefinition[]> {
    const query = workspaceSlug ? `?workspace_slug=${encodeURIComponent(workspaceSlug)}` : '';
    return this.request<ToolDefinition[]>(`/api/v1/tools/${query}`);
  }

  async executeTool(request: ToolExecutionRequest): Promise<ToolExecutionResponse> {
    return this.request<ToolExecutionResponse>('/api/v1/tools/execute', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // --- Phase 4: Autonomous Agents ---
  async getAgents(workspaceSlug?: string): Promise<AgentDefinitionResponse[]> {
    const query = workspaceSlug ? `?workspace_slug=${encodeURIComponent(workspaceSlug)}` : '';
    return this.request<AgentDefinitionResponse[]>(`/api/v1/agents/${query}`);
  }

  async createAgentTask(data: AgentTaskCreate): Promise<AgentTaskResponse> {
    return this.request<AgentTaskResponse>('/api/v1/agents/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getAgentTask(taskId: string): Promise<AgentTaskResponse> {
    return this.request<AgentTaskResponse>(`/api/v1/agents/tasks/${taskId}`);
  }

  async getAgentTasks(workspaceSlug?: string): Promise<AgentTaskResponse[]> {
    const query = workspaceSlug ? `?workspace_slug=${encodeURIComponent(workspaceSlug)}` : '';
    return this.request<AgentTaskResponse[]>(`/api/v1/agents/tasks${query}`);
  }

  // --- Phase 5: Audit, Export & Diagnostics ---
  async getAuditLogs(eventType?: string): Promise<AuditLogResponse[]> {
    const query = eventType ? `?event_type=${encodeURIComponent(eventType)}` : '';
    return this.request<AuditLogResponse[]>(`/api/v1/audit/${query}`);
  }

  async getDiagnostics(): Promise<SystemDiagnosticsResponse> {
    return this.request<SystemDiagnosticsResponse>('/api/v1/diagnostics/');
  }

  getExportUrl(conversationId: string, format: 'markdown' | 'json' | 'txt' = 'markdown'): string {
    return `${API_BASE_URL}/api/v1/export/conversation/${conversationId}?format=${format}`;
  }
}

export const api = new ApiService();
