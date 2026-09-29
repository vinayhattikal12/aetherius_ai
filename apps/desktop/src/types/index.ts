export interface CpuInfo {
  model: string;
  physical_cores: number;
  logical_cores: number;
  frequency_mhz?: number;
  architecture: string;
}

export interface GpuInfo {
  name: string;
  vendor: string;
  vram_total_gb: number;
  vram_free_gb?: number;
  cuda_supported: boolean;
  driver_version?: string;
}

export interface RamInfo {
  total_gb: number;
  available_gb: number;
  used_gb: number;
  percent_used: number;
}

export interface StorageInfo {
  total_gb: number;
  free_gb: number;
  used_gb: number;
  percent_used: number;
}

export interface HardwareProfile {
  os: string;
  os_release?: string;
  architecture: string;
  cpu: CpuInfo;
  ram: RamInfo;
  ram_gb: number;
  gpu: GpuInfo[];
  vram_gb: number;
  storage: StorageInfo;
  storage_free_gb: number;
  accelerators: string[];
  compute_tier: 'Ultra' | 'High' | 'Medium' | 'Low' | 'Minimum';
  detected_at: string;
  recommendations_summary: string;
}

export interface CompatibilityResult {
  model_name: string;
  compatibility: 'Compatible' | 'Maybe Compatible' | 'Not Recommended';
  score: number;
  estimated_memory_gb: number;
  recommended_quantization: string;
  recommended_execution: string;
  performance_tier: string;
  reasons: string[];
}

export interface ModelResponse {
  id: string;
  name: string;
  display_name: string;
  provider: string;
  model_family: string;
  parameters_b: number;
  quantization: string;
  context_size: number;
  min_ram_gb: number;
  min_vram_gb: number;
  recommended_vram_gb: number;
  cpu_compatible: boolean;
  gpu_compatible: boolean;
  vision_capable: boolean;
  coding_capable: boolean;
  reasoning_capable: boolean;
  tool_calling_capable: boolean;
  embedding_capable: boolean;
  category: string;
  description?: string;
  is_local: boolean;
  is_installed: boolean;
  is_recommended: boolean;
  is_active: boolean;
  compatibility?: CompatibilityResult;
}

export interface ModelPackageResponse {
  id: string;
  name: string;
  slug: string;
  description: string;
  target_audience: string;
  recommended_model_ids: string[];
  models?: ModelResponse[];
  estimated_storage_gb: number;
  required_ram_gb: number;
}

export interface HuggingFaceModelCard {
  repo_id: string;
  author: string;
  model_name: string;
  parameters_b: number;
  quantization_formats: string[];
  downloads: number;
  likes: number;
  category: string;
  description: string;
  is_gguf: boolean;
  ollama_pull_tag: string;
  recommended_quantization: string;
  estimated_size_gb: number;
  benchmark_highlight?: string;
  compatibility?: CompatibilityResult;
}

export interface HuggingFaceDatasetCard {
  repo_id: string;
  author: string;
  dataset_name: string;
  description: string;
  downloads: number;
  likes: number;
  category: string;
  tags: string[];
}

export interface ModelUpgradeSuggestion {
  current_model_id: string;
  current_model_name: string;
  suggested_repo_id: string;
  suggested_display_name: string;
  category: string;
  reason: string;
  benchmark_gain: string;
  estimated_disk_delta_gb: number;
  vram_fit_status: string;
  compatibility: CompatibilityResult;
}

export interface SmartSwapRequest {
  old_model_id: string;
  new_repo_id: string;
  quantization?: string;
}

export interface ModelInstallProgress {
  model_id: string;
  model_name: string;
  status: 'initializing' | 'downloading' | 'verifying' | 'registering' | 'completed' | 'failed';
  status_message: string;
  progress_percent: number;
  downloaded_bytes?: number;
  total_bytes?: number;
  speed_mbps?: number;
  eta_seconds?: number;
  error?: string;
  is_completed: boolean;
}

export interface WorkspaceResponse {
  id: string;
  name: string;
  slug: string;
  description?: string;
  icon: string;
  color: string;
  is_system: boolean;
  instructions: string;
  preferred_model?: string;
  enabled_tools: string[];
  ui_capabilities: Record<string, boolean>;
}

export interface UserSettingsResponse {
  id: string;
  user_id: string;
  theme: 'dark' | 'light' | 'system';
  privacy_mode: 'LOCAL_ONLY' | 'HYBRID' | 'CLOUD';
  default_workspace_slug: string;
  auto_routing_enabled: boolean;
  telemetry_enabled: boolean;
  onboarding_completed: boolean;
}

export interface ChatAttachment {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  storage_path?: string;
  is_image: boolean;
  preview_url?: string;
  extracted_text?: string;
}

// Phase 2 Chat & Conversation Types
export interface SourceCitation {
  source_type: 'document' | 'web' | 'memory' | 'workspace';
  title: string;
  url?: string;
  snippet: string;
  chunk_index?: number;
  similarity_score?: number;
}

export interface MessageResponse {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  model_id?: string;
  model_name?: string;
  sources?: SourceCitation[];
  citations?: SourceCitation[];
  attachments?: ChatAttachment[];
  extra_metadata?: Record<string, any>;
  generation_metadata?: Record<string, any>;
  created_at: string;
}

export interface ConversationResponse {
  id: string;
  title: string;
  workspace_slug: string;
  active_model_id?: string;
  model_name?: string;
  is_pinned: boolean;
  is_archived?: boolean;
  created_at: string;
  updated_at: string;
  messages: MessageResponse[];
}

export interface ChatCompletionRequest {
  message: string;
  attachments?: ChatAttachment[];
  conversation_id?: string;
  workspace_slug?: string;
  model_id?: string;
  model_name?: string;
  use_rag?: boolean;
  enable_knowledge_rag?: boolean;
  use_web_search?: boolean;
  enable_web_search?: boolean;
  knowledge_base_slugs?: string[];
  system_instruction?: string;
}

export interface ChatCompletionResponse {
  conversation_id: string;
  user_message: MessageResponse;
  assistant_message: MessageResponse;
  model_used: string;
  citations: SourceCitation[];
  web_searched?: boolean;
  rag_applied?: boolean;
}

// Phase 2 Knowledge & RAG Types
export interface DocumentResponse {
  id: string;
  knowledge_base_id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: 'pending' | 'parsing' | 'chunked' | 'embedded' | 'ready' | 'error';
  chunk_count: number;
  error_message?: string;
  doc_metadata: Record<string, any>;
  created_at: string;
}

export interface DocumentChunkResponse {
  id: string;
  document_id: string;
  knowledge_base_id: string;
  chunk_index: number;
  content: string;
  token_count: number;
  chunk_metadata: Record<string, any>;
  similarity_score?: number;
  created_at: string;
}

export interface KnowledgeBaseResponse {
  id: string;
  user_id?: string;
  name: string;
  slug: string;
  collection_type: string;
  description?: string;
  workspace_slug: string;
  documents: DocumentResponse[];
  document_count: number;
  total_chunks: number;
  created_at: string;
}

export interface KnowledgeBaseCreate {
  name: string;
  slug: string;
  collection_type?: string;
  description?: string;
  workspace_slug?: string;
}

export interface RAGSearchRequest {
  query: string;
  knowledge_base_slugs?: string[];
  workspace_slug?: string;
  top_k?: number;
  min_similarity?: number;
}

export interface RAGSearchResult {
  query: string;
  chunks: DocumentChunkResponse[];
  sources: Array<{ filename?: string; chunk_index?: number; similarity_score?: number }>;
}

// Phase 2 Web Search Types
export interface WebSearchItem {
  title: string;
  url: string;
  snippet: string;
}

export interface WebSearchResult {
  query: string;
  results: WebSearchItem[];
}

// Phase 3 Memory Types
export interface MemoryResponse {
  id: string;
  user_id?: string;
  workspace_slug: string;
  memory_type: string;
  content: string;
  source_conversation_id?: string;
  confidence_score: number;
  importance_weight: number;
  access_count: number;
  last_accessed_at?: string;
  similarity_score?: number;
  memory_metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface MemoryCreate {
  workspace_slug?: string;
  memory_type?: string;
  content: string;
  confidence_score?: number;
  importance_weight?: number;
  source_conversation_id?: string;
  memory_metadata?: Record<string, any>;
}

export interface MemorySearchRequest {
  query: string;
  workspace_slug?: string;
  memory_type?: string;
  top_k?: number;
  min_similarity?: number;
}

export interface MemorySearchResult {
  query: string;
  memories: MemoryResponse[];
}

// Phase 3 Router Types
export interface RouterEvaluationRequest {
  prompt: string;
  workspace_slug?: string;
  privacy_mode?: string;
  requires_coding?: boolean;
  requires_vision?: boolean;
  requires_reasoning?: boolean;
  requires_tools?: boolean;
  requires_rag?: boolean;
  explicit_model_id?: string;
}

export interface RouterEvaluationResponse {
  selected_model_id: string;
  selected_model_name: string;
  execution_mode: string;
  privacy_compliant: boolean;
  confidence_score: number;
  routing_reason: string;
  complexity_score: number;
  detected_intent: string;
  fallback_model_id?: string;
}

// Phase 3 Tool Types
export interface ToolParameter {
  name: string;
  type: string;
  description: string;
  required: boolean;
  default?: any;
}

export interface ToolDefinition {
  name: string;
  display_name: string;
  category: string;
  description: string;
  parameters: ToolParameter[];
  is_safe: boolean;
  workspace_types: string[];
}

export interface ToolExecutionRequest {
  tool_name: string;
  arguments: Record<string, any>;
  workspace_slug?: string;
}

export interface ToolExecutionResponse {
  tool_name: string;
  status: 'success' | 'error';
  result: any;
  error_message?: string;
  execution_time_ms: number;
}

// Phase 4 Agent & Task Types
export interface AgentDefinitionResponse {
  id: string;
  name: string;
  slug: string;
  role_type: string;
  workspace_slug: string;
  description: string;
  system_instructions: string;
  allowed_tools: string[];
  preferred_model_id: string;
  is_system: boolean;
  is_active: boolean;
  max_steps: number;
  created_at: string;
  updated_at: string;
}

export interface AgentTaskStepResponse {
  id: string;
  task_id: string;
  step_index: number;
  step_type: 'plan' | 'tool_call' | 'observation' | 'reflection' | 'final_output';
  content: string;
  tool_name?: string;
  tool_arguments: Record<string, any>;
  tool_result: Record<string, any>;
  duration_ms: number;
  created_at: string;
}

export interface AgentTaskCreate {
  agent_slug: string;
  goal_prompt: string;
  title?: string;
  workspace_slug?: string;
  use_rag?: boolean;
  use_web_search?: boolean;
}

export interface AgentTaskResponse {
  id: string;
  agent_id: string;
  agent_slug?: string;
  agent_name?: string;
  workspace_slug: string;
  title: string;
  goal_prompt: string;
  status: 'pending' | 'planning' | 'running' | 'completed' | 'failed';
  result_output?: string;
  error_message?: string;
  execution_metadata: Record<string, any>;
  steps: AgentTaskStepResponse[];
  completed_at?: string;
  created_at: string;
  updated_at: string;
}

// Phase 5 Audit & Diagnostics Types
export interface AuditLogResponse {
  id: string;
  event_type: string;
  user_id?: string;
  actor: string;
  details: Record<string, any>;
  ip_address?: string;
  created_at: string;
  updated_at: string;
}

export interface SystemDiagnosticsResponse {
  status: 'healthy' | 'degraded' | 'error';
  app_name: string;
  version: string;
  components: {
    database: {
      status: string;
      dialect: string;
      host: string;
      port: number;
      pgvector_ready: boolean;
      error?: string;
    };
    storage: {
      status: string;
      storage_path?: string;
      total_gb?: number;
      free_gb?: number;
      used_gb?: number;
      error?: string;
    };
    local_ai_server: {
      provider: string;
      status: string;
      endpoint: string;
      models_installed: string[];
    };
    hardware: {
      compute_tier: string;
      os: string;
      cpu: string;
      ram_gb: number;
      vram_gb: number;
      accelerators: string[];
    };
  };
}
