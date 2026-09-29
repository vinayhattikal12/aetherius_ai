import React, { useState, useEffect, useRef } from 'react';
import {
  WorkspaceResponse,
  ModelResponse,
  MessageResponse,
  ChatAttachment,
} from '../../types';
import { api } from '../../services/api';
import { MarkdownContent } from './MarkdownContent';
import {
  Globe,
  Database,
  Sparkles,
  ExternalLink,
  Check,
  Copy,
  FileText,
  Download,
  Paperclip,
  Image as ImageIcon,
  X,
  Loader2,
  ChevronDown,
  ChevronRight,
  PanelLeft,
  ArrowUp,
  ZoomIn,
  ZoomOut,
  RotateCcw,
} from 'lucide-react';

interface AssistantMessageBodyProps {
  content: string;
  onImageClick?: (url: string) => void;
}

const AssistantMessageBody: React.FC<AssistantMessageBodyProps> = ({ content, onImageClick }) => {
  const [showThinking, setShowThinking] = useState<boolean>(false);

  if (!content) {
    return (
      <span className="inline-flex items-center gap-1.5 py-1 text-[#949494]">
        <span className="w-2 h-2 rounded-full bg-[#34888D] animate-bounce" />
        <span className="w-2 h-2 rounded-full bg-[#34888D] animate-bounce delay-150" />
        <span className="w-2 h-2 rounded-full bg-[#34888D] animate-bounce delay-300" />
      </span>
    );
  }

  // Parse <think> tags (e.g. DeepSeek R1 / Reasoning models)
  let thinking: string | null = null;
  let answer = content;

  if (content.includes('<think>')) {
    if (content.includes('</think>')) {
      const parts = content.split('</think>');
      thinking = parts[0].replace('<think>', '').trim();
      answer = parts.slice(1).join('</think>').trim();
    } else {
      // Actively streaming thinking block
      thinking = content.replace('<think>', '').trim();
      answer = '';
    }
  }

  return (
    <div className="space-y-3">
      {thinking !== null && (
        <div className="rounded-[11px] border border-[#016A71]/35 bg-[#016A71]/10 overflow-hidden text-xs">
          <button
            type="button"
            onClick={() => setShowThinking(!showThinking)}
            className="w-full flex items-center justify-between px-3.5 py-2 text-[#34888D] hover:bg-[#016A71]/20 transition-colors select-none font-medium"
          >
            <span className="flex items-center space-x-2">
              <Sparkles className="w-3.5 h-3.5 text-[#34888D] animate-pulse" />
              <span>
                Thinking Process{' '}
                {thinking.length > 0
                  ? `(${thinking.split(/\s+/).filter(Boolean).length} words)`
                  : '...'}
              </span>
            </span>
            {showThinking ? (
              <ChevronDown className="w-3.5 h-3.5 text-[#34888D]" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-[#34888D]" />
            )}
          </button>
          {showThinking && (
            <div className="p-3.5 pt-2 text-[#949494] font-mono text-[11px] leading-relaxed border-t border-[#016A71]/20 whitespace-pre-wrap max-h-64 overflow-y-auto bg-black/40">
              {thinking || 'Reasoning in progress...'}
            </div>
          )}
        </div>
      )}

      {answer ? (
        <MarkdownContent content={answer} onImageClick={onImageClick} />
      ) : thinking !== null ? (
        <div className="flex items-center space-x-2 text-xs text-[#34888D] py-1">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          <span>Generating reasoning response...</span>
        </div>
      ) : null}
    </div>
  );
};


interface ChatInterfaceProps {
  activeWorkspace: WorkspaceResponse | null;
  models: ModelResponse[];
  activeConversationId: string | null;
  setActiveConversationId: (id: string | null) => void;
  onRefreshConversations?: () => void;
  isSidebarOpen?: boolean;
  onToggleSidebar?: () => void;
  onOpenModels?: () => void;
  onOpenKnowledge?: () => void;
  onOpenMemory?: () => void;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  activeWorkspace,
  models,
  activeConversationId,
  setActiveConversationId,
  onRefreshConversations,
  isSidebarOpen = true,
  onToggleSidebar,
}) => {
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [inputPrompt, setInputPrompt] = useState<string>('');
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [isUploadingFile, setIsUploadingFile] = useState<boolean>(false);
  const [isDraggingOver, setIsDraggingOver] = useState<boolean>(false);
  const [previewImageModal, setPreviewImageModal] = useState<string | null>(null);
  const [imageZoom, setImageZoom] = useState<number>(1);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [selectedModelId, setSelectedModelId] = useState<string>('auto');
  const [useRAG, setUseRAG] = useState<boolean>(true);
  const [useWebSearch, setUseWebSearch] = useState<boolean>(false);
  const [useImageGen, setUseImageGen] = useState<boolean>(false);
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);

  // Close image modal on Escape key
  useEffect(() => {
    const handleKeyDownGlobal = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && previewImageModal) {
        setPreviewImageModal(null);
        setImageZoom(1);
      }
    };
    window.addEventListener('keydown', handleKeyDownGlobal);
    return () => window.removeEventListener('keydown', handleKeyDownGlobal);
  }, [previewImageModal]);


  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Filter out pure embedding models from chat selector
  const chatModels = models.filter((m) => {
    const isEmbed =
      m.category?.toLowerCase() === 'embedding' ||
      m.name.toLowerCase().includes('embed') ||
      m.display_name?.toLowerCase().includes('embed');
    return !isEmbed;
  });

  // Initialize selected chat model
  useEffect(() => {
    if (chatModels.length > 0) {
      const isCurrentValid = chatModels.some((m) => m.id === selectedModelId);
      if (!isCurrentValid) {
        const localInstalled = chatModels.find((m) => m.is_local && m.is_installed);
        const anyInstalled = chatModels.find((m) => m.is_installed);
        const candidate = localInstalled || anyInstalled || chatModels[0];
        if (candidate) {
          setSelectedModelId(candidate.id);
        }
      }
    }
  }, [models, selectedModelId]);

  useEffect(() => {
    if (activeConversationId) {
      loadMessages(activeConversationId);
    } else {
      setMessages([]);
    }
  }, [activeConversationId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isGenerating]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadMessages = async (convId: string) => {
    try {
      const conv = await api.getConversation(convId);
      setMessages(conv.messages || []);
      if (conv.active_model_id) {
        setSelectedModelId(conv.active_model_id);
      }
    } catch (err) {
      console.error('Failed to load messages for conversation:', err);
    }
  };

  const handleFileSelect = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setIsUploadingFile(true);
    try {
      const uploadPromises = Array.from(files).map((f) => api.uploadChatAttachment(f));
      const newAttachments = await Promise.all(uploadPromises);
      setAttachments((prev) => [...prev, ...newAttachments]);
    } catch (err) {
      console.error('Failed to upload file(s):', err);
    } finally {
      setIsUploadingFile(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleRemoveAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingOver(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await handleFileSelect(e.dataTransfer.files);
    }
  };

  const handleSendMessage = async () => {
    const text = inputPrompt.trim();
    if ((!text && attachments.length === 0) || isGenerating || isUploadingFile) return;

    const activeAttachments = [...attachments];
    setInputPrompt('');
    setAttachments([]);
    setIsGenerating(true);

    const isImageRequest =
      useImageGen ||
      text.toLowerCase().startsWith('/image') ||
      /^(generate|create|draw|paint|make|show|render)\s+(an?|the|its|this|a)?\s*(image|picture|diagram|photo|illustration|visual)/i.test(text) ||
      /\b(generate|draw|show)\s+(its|this)\s+(image|picture|diagram|visual)\b/i.test(text);

    if (isImageRequest) {
      let promptClean = text
        .replace(/^\/image/i, '')
        .replace(/^(generate|create|draw|paint|make|show|render)\s+(an?|the|its|this|a)?\s*(image|picture|diagram|photo|illustration|visual)\s*(of|for|about)?/i, '')
        .replace(/^draw/i, '')
        .trim() || text;

      if (!promptClean || ['its', 'it', 'this', 'its image', 'this image'].includes(promptClean.toLowerCase())) {
        const lastMsg = [...messages].reverse().find((m) => m.content && !m.content.startsWith('🎨'));
        if (lastMsg) {
          const firstLine = lastMsg.content.split('\n')[0].replace(/[#*`_]/g, '').trim();
          promptClean = firstLine ? `${firstLine} visual diagram` : 'Artificial Intelligence architecture';
        }
      }

      const tempUserMsg: MessageResponse = {
        id: `temp-${Date.now()}`,
        conversation_id: activeConversationId || '',
        role: 'user',
        content: text,
        attachments: activeAttachments,
        sources: [],
        generation_metadata: {},
        created_at: new Date().toISOString(),
      };

      const tempAssistantId = `temp-ast-${Date.now()}`;
      const tempAssistantMsg: MessageResponse = {
        id: tempAssistantId,
        conversation_id: activeConversationId || '',
        role: 'assistant',
        content: '🎨 Generating visual diagram & rendering...',
        model_id: 'FLUX.1-Turbo / SD-Turbo',
        sources: [],
        attachments: [],
        generation_metadata: {},
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, tempUserMsg, tempAssistantMsg]);

      try {
        const imgResult = await api.generateImage(
          promptClean,
          '1:1',
          undefined,
          activeWorkspace?.slug || 'general'
        );

        const displayUrl = imgResult.preview_url || imgResult.image_url;
        const imgMarkdown = `![${promptClean}](${displayUrl})\n\n**Visual Generated:** ${promptClean}\n*Model:* ${imgResult.model_name} • *Resolution:* ${imgResult.width}x${imgResult.height}`;

        setMessages((prev) =>
          prev.map((m) =>
            m.id === tempAssistantId
              ? {
                  ...m,
                  content: imgMarkdown,
                  attachments: [],
                }
              : m
          )
        );
      } catch (err: any) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === tempAssistantId
              ? {
                  ...m,
                  content: `Error generating image: ${err.message || 'Check network / image engine.'}`,
                }
              : m
          )
        );
      } finally {
        setIsGenerating(false);
        if (useImageGen) setUseImageGen(false);
      }
      return;
    }

    // Optimistic user message & assistant stream placeholder insertion
    const tempUserMsg: MessageResponse = {
      id: `temp-${Date.now()}`,
      conversation_id: activeConversationId || '',
      role: 'user',
      content:
        text ||
        (activeAttachments.length > 0
          ? `Please inspect and analyze the attached ${activeAttachments
              .map((a) => a.filename)
              .join(', ')}`
          : ''),
      attachments: activeAttachments,
      sources: [],
      generation_metadata: {},
      created_at: new Date().toISOString(),
    };

    const tempAssistantId = `temp-ast-${Date.now()}`;
    const tempAssistantMsg: MessageResponse = {
      id: tempAssistantId,
      conversation_id: activeConversationId || '',
      role: 'assistant',
      content: '',
      model_id: selectedModelId,
      sources: [],
      attachments: [],
      generation_metadata: {},
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMsg, tempAssistantMsg]);

    try {
      let currentContent = '';

      await api.streamChatMessage(
        {
          message:
            text ||
            `Analyze the attached file(s): ${activeAttachments.map((a) => a.filename).join(', ')}`,
          attachments: activeAttachments,
          conversation_id: activeConversationId || undefined,
          workspace_slug: activeWorkspace?.slug || 'general',
          model_id: selectedModelId || undefined,
          model_name: selectedModelId || undefined,
          use_rag: useRAG,
          enable_knowledge_rag: useRAG,
          use_web_search: useWebSearch,
          enable_web_search: useWebSearch,
        },
        {
          onInit: (data) => {
            if (!activeConversationId && data.conversation_id) {
              setActiveConversationId(data.conversation_id);
              if (onRefreshConversations) onRefreshConversations();
            }
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAssistantId
                  ? {
                      ...m,
                      sources: data.citations && data.citations.length > 0 ? data.citations : m.sources,
                      model_id: data.model_used || m.model_id,
                      generation_metadata: {
                        ...m.generation_metadata,
                        routing_reason: data.routing_reason,
                      },
                    }
                  : m
              )
            );
          },
          onImage: (data) => {
            if (data.image_url) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === tempAssistantId
                    ? {
                        ...m,
                        attachments: [
                          ...(m.attachments || []),
                          {
                            id: `img-${Date.now()}`,
                            filename: `${(data.prompt || 'visual_diagram').slice(0, 20)}.png`,
                            file_type: 'image/png',
                            file_size_bytes: 1024 * 512,
                            is_image: true,
                            preview_url: data.image_url,
                          },
                        ],
                      }
                    : m
                )
              );
            }
          },
          onToken: (token) => {
            currentContent += token;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAssistantId ? { ...m, content: currentContent } : m
              )
            );
          },
          onDone: (data) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAssistantId
                  ? {
                      ...m,
                      id: data.message_id || m.id,
                      content: data.content || currentContent,
                      sources:
                        data.citations && data.citations.length > 0
                          ? data.citations
                          : m.sources,
                      model_id: data.model_used || selectedModelId,
                    }
                  : m
              )
            );
            if (onRefreshConversations) onRefreshConversations();
          },
          onError: (err) => {
            console.error('Chat streaming error:', err);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAssistantId
                  ? {
                      ...m,
                      content: `Error communicating with AI engine: ${
                        err.message || 'Check PostgreSQL & model service.'
                      }`,
                      generation_metadata: { error: true },
                    }
                  : m
              )
            );
          },
        }
      );
    } catch (err: any) {
      console.error('Chat error:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleCopyMessage = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedMsgId(id);
    setTimeout(() => setCopiedMsgId(null), 2000);
  };

  const getWorkspaceSuggestions = () => {
    const slug = activeWorkspace?.slug;
    switch (slug) {
      case 'hr':
        return [
          {
            title: 'Draft Job Description',
            desc: 'Create structured roles & ATS competencies',
            prompt:
              'Draft a comprehensive Senior Software Engineer job description with key technical competencies, responsibilities, and qualifications.',
          },
          {
            title: 'STAR Interview Guide',
            desc: 'Generate structured behavioral scorecard',
            prompt:
              'Create a structured STAR interview scorecard for evaluating a candidate on leadership, technical problem-solving, and communication.',
          },
        ];
      case 'finance':
        return [
          {
            title: 'Financial Analysis',
            desc: 'Evaluate margins, DCF & EBITDA metrics',
            prompt:
              'Analyze our balance sheet and break down EBITDA margins, free cash flow, and DCF valuation metrics in a structured table.',
          },
          {
            title: 'Scenario Forecast',
            desc: 'Bull, Base & Bear revenue projections',
            prompt:
              'Build a financial sensitivity matrix comparing Bull Case, Base Case, and Bear Case revenue growth scenarios with risk assumptions.',
          },
        ];
      case 'student':
        return [
          {
            title: 'Feynman Technique',
            desc: 'Explain complex topic using intuitive analogies',
            prompt:
              'Explain how neural networks and gradient descent work using the Feynman technique with clear everyday real-world analogies.',
          },
          {
            title: 'Active Recall Quiz',
            desc: 'Generate interactive 5-question review quiz',
            prompt:
              'Create a 5-question active recall quiz on data structures and algorithms with step-by-step explanations for each answer.',
          },
        ];
      case 'developer':
        return [
          {
            title: 'System Architecture',
            desc: 'Design production components & patterns',
            prompt:
              'Design a clean, modular backend architecture in TypeScript with repository pattern, unit tests, and error handling.',
          },
          {
            title: 'Code Optimization',
            desc: 'Analyze Big-O complexity & bottlenecks',
            prompt:
              'Review and optimize algorithms for high concurrency, memory efficiency, and Big-O time and space complexity.',
          },
        ];
      case 'sales':
        return [
          {
            title: 'SPIN Sales Pitch',
            desc: 'Structure executive value proposition',
            prompt:
              'Draft an executive enterprise sales pitch using the SPIN selling framework to position our AI software with clear ROI metrics.',
          },
          {
            title: 'Objection Handling',
            desc: 'Playbook for security & privacy concerns',
            prompt:
              'Create a playbook for handling customer objections around data privacy, on-premise deployment, and implementation timelines.',
          },
        ];
      case 'content':
        return [
          {
            title: 'Thought Leadership',
            desc: 'Write pattern-interrupt article hook',
            prompt:
              'Write an engaging thought leadership article with a pattern-interrupt hook on the future of local AI on personal devices.',
          },
          {
            title: 'Content Strategy',
            desc: 'Multi-platform narrative calendar',
            prompt:
              'Draft a 30-day content calendar and distribution strategy tailored for LinkedIn and technical blogs.',
          },
        ];
      default:
        return [
          {
            title: 'Knowledge Base Inquiry',
            desc: 'Summarize internal documents via pgvector RAG',
            prompt:
              'Summarize key requirements and architectural insights from our uploaded knowledge base documents.',
          },
          {
            title: 'Deep Research',
            desc: 'Analyze trends in local AI and open-source models',
            prompt:
              'Search latest developments in local AI execution, open-source models, and hardware acceleration.',
          },
        ];
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#000000] text-white relative select-none">
      {/* Sleek Minimalist Top Bar (ChatGPT / Claude style) */}
      <header className="h-14 px-4 flex items-center justify-between bg-[#000000] flex-shrink-0 z-10">
        <div className="flex items-center gap-2">
          {!isSidebarOpen && onToggleSidebar && (
            <button
              onClick={onToggleSidebar}
              className="p-2 rounded-[10px] hover:bg-[#171615] text-[#949494] hover:text-white transition-colors mr-1"
              title="Open Sidebar"
            >
              <PanelLeft className="w-4 h-4" />
            </button>
          )}

          {/* Model Selector Dropdown - Clean & Sleek like ChatGPT */}
          <div className="relative flex items-center">
            <select
              value={selectedModelId}
              onChange={(e) => setSelectedModelId(e.target.value)}
              className="appearance-none bg-transparent hover:bg-[#171615] text-sm font-semibold text-white pl-2 pr-7 py-1.5 rounded-[10px] focus:outline-none cursor-pointer transition-colors"
            >
              <option value="auto" className="bg-[#171615] text-[#34888D] font-bold">
                ⚡ Auto (Sub-ms Smart Router)
              </option>
              {chatModels.map((m) => (
                <option key={m.id} value={m.name || m.id} className="bg-[#171615] text-white">
                  {m.display_name} {m.is_local ? (m.is_installed ? '⚡ Local' : '📥 Download') : '☁️ Cloud'}
                </option>
              ))}
            </select>
            <ChevronDown className="w-4 h-4 text-[#949494] absolute right-2 pointer-events-none" />
          </div>
        </div>

        {/* Right Action: Clean Export Button */}
        <div className="flex items-center gap-2">
          {activeConversationId && (
            <a
              href={api.getExportUrl(activeConversationId, 'markdown')}
              target="_blank"
              rel="noreferrer"
              download={`session-${activeConversationId}.md`}
              className="p-2 rounded-[10px] text-[#949494] hover:text-white hover:bg-[#171615] transition-colors"
              title="Export Conversation"
            >
              <Download className="w-4 h-4" />
            </a>
          )}
        </div>
      </header>

      {/* Main Conversation Stream (Centered Max-W-3XL layout like Claude/ChatGPT) */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className="flex-1 overflow-y-auto px-4 md:px-6 py-6 select-text"
      >
        {/* Drag & Drop Overlay */}
        {isDraggingOver && (
          <div className="fixed inset-0 z-50 bg-black/80 border-2 border-dashed border-[#34888D] backdrop-blur-md flex flex-col items-center justify-center pointer-events-none">
            <Paperclip className="w-12 h-12 text-[#34888D] animate-bounce mb-3" />
            <p className="text-base font-semibold text-white">Drop files to attach to conversation</p>
            <p className="text-xs text-[#949494] mt-1.5">PDF, Docs, CSV, Images, Code files supported</p>
          </div>
        )}

        <div className="max-w-3xl mx-auto space-y-6">
          {messages.length === 0 ? (
            <div className="py-12 flex flex-col items-center justify-center text-center">
              <div className="w-12 h-12 rounded-[12px] bg-[#016A71]/15 border border-[#016A71]/30 flex items-center justify-center mb-4 shadow-[0_0_24px_rgba(1,106,113,0.25)]">
                <Sparkles className="w-6 h-6 text-[#34888D]" />
              </div>
              <h2 className="text-2xl font-bold text-white tracking-tight">
                {activeWorkspace?.name || 'Aetherius Intelligence'}
              </h2>
              <p className="text-sm text-[#949494] mt-2 leading-relaxed max-w-md">
                {activeWorkspace?.description ||
                  'Your private AI environment with PostgreSQL RAG, multi-model intelligence, and adaptive memory.'}
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-8 w-full text-left">
                {getWorkspaceSuggestions().map((sug, sIdx) => (
                  <button
                    key={sIdx}
                    onClick={() => setInputPrompt(sug.prompt)}
                    className="p-4 rounded-[11px] bg-[#171615] border border-[#2a2928] hover:border-[#34888D]/60 hover:bg-[#1f1e1d] transition-all text-left group"
                  >
                    <div className="text-xs font-semibold text-[#34888D] group-hover:text-white transition-colors mb-1">
                      {sug.title}
                    </div>
                    <div className="text-[12px] text-[#949494] leading-snug">
                      {sug.desc}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={msg.id || idx}
                  className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} space-y-1.5`}
                >
                  {/* Sender Header */}
                  <div className="flex items-center gap-2 px-1 text-[11px] text-[#949494]">
                    <span className="font-medium">
                      {isUser ? 'You' : 'Aetherius'}
                    </span>
                    {msg.generation_metadata?.duration_ms && (
                      <span className="text-[10px] text-[#949494]/70 font-mono">
                        {msg.generation_metadata.duration_ms}ms
                      </span>
                    )}
                    {!isUser && (
                      <button
                        onClick={() => handleCopyMessage(msg.content, msg.id)}
                        className="p-1 text-[#949494] hover:text-white transition-colors"
                        title="Copy message"
                      >
                        {copiedMsgId === msg.id ? (
                          <Check className="w-3 h-3 text-emerald-400" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                      </button>
                    )}
                  </div>

                  {/* Message Bubble */}
                  <div
                    className={`w-full rounded-[12px] p-4 text-sm leading-relaxed ${
                      isUser
                        ? 'bg-[#171615] border border-[#2a2928] text-white shadow-sm max-w-[85%]'
                        : 'bg-transparent text-white'
                    }`}
                  >
                    {/* Attachments inside bubble */}
                    {msg.attachments && msg.attachments.length > 0 && (
                      <div className="flex flex-wrap gap-2.5 mb-3">
                        {msg.attachments.map((att) =>
                          att.is_image && att.preview_url ? (
                            <div
                              key={att.id}
                              onClick={() => setPreviewImageModal(att.preview_url || null)}
                              className="relative rounded-[11px] overflow-hidden border border-[#2a2928] cursor-pointer group max-w-[260px] max-h-[180px] bg-black/40"
                              title="Click to enlarge image"
                            >
                              <img
                                src={att.preview_url}
                                alt={att.filename}
                                className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                              />
                              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-xs font-medium">
                                Enlarge
                              </div>
                            </div>
                          ) : (
                            <div
                              key={att.id}
                              className="flex items-center gap-2.5 px-3 py-2 rounded-[11px] bg-[#171615] border border-[#2a2928] text-xs text-white"
                            >
                              <FileText className="w-4 h-4 text-[#34888D] flex-shrink-0" />
                              <div className="flex flex-col min-w-0">
                                <span className="font-medium truncate max-w-[180px]">
                                  {att.filename}
                                </span>
                                <span className="text-[10px] text-[#949494] font-mono">
                                  {(att.file_size_bytes / 1024).toFixed(1)} KB
                                </span>
                              </div>
                            </div>
                          )
                        )}
                      </div>
                    )}

                    {isUser ? (
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    ) : (
                      <AssistantMessageBody
                        content={msg.content}
                        onImageClick={(url) => {
                          setPreviewImageModal(url);
                          setImageZoom(1);
                        }}
                      />
                    )}

                    {/* Source Citations */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-4 pt-3.5 border-t border-[#2a2928]">
                        <div className="text-[11px] font-semibold text-[#949494] mb-2.5 flex items-center gap-1.5">
                          <Database className="w-3.5 h-3.5 text-[#34888D]" />
                          <span>Sources & Evidence ({msg.sources.length})</span>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                          {msg.sources.map((src, sIdx) => (
                            <div
                              key={sIdx}
                              className="p-3 rounded-[11px] bg-[#171615] border border-[#2a2928] text-xs flex flex-col justify-between"
                            >
                              <div className="flex items-center justify-between mb-1.5">
                                <span className="font-medium text-white truncate flex items-center gap-1.5">
                                  {src.source_type === 'web' ? (
                                    <Globe className="w-3 h-3 text-[#34888D] flex-shrink-0" />
                                  ) : (
                                    <FileText className="w-3 h-3 text-[#34888D] flex-shrink-0" />
                                  )}
                                  <span className="truncate">{src.title}</span>
                                </span>
                                {src.similarity_score !== undefined && (
                                  <span className="text-[10px] text-[#34888D] font-mono">
                                    {(src.similarity_score * 100).toFixed(0)}%
                                  </span>
                                )}
                              </div>
                              <p className="text-[#949494] line-clamp-2 text-[11px] leading-relaxed">
                                {src.snippet}
                              </p>
                              {src.url && (
                                <a
                                  href={src.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-[11px] text-[#34888D] hover:underline flex items-center gap-1 mt-2"
                                >
                                  <span>Source link</span>
                                  <ExternalLink className="w-3 h-3" />
                                </a>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Floating Bottom Input Dock (Centered max-w-3xl) */}
      <div className="p-4 bg-[#000000] border-t border-[#2a2928] flex-shrink-0">
        <div className="max-w-3xl mx-auto">
          {/* Attachment Preview Chips */}
          {(attachments.length > 0 || isUploadingFile) && (
            <div className="flex flex-wrap gap-2 mb-2 px-1">
              {attachments.map((att) => (
                <div
                  key={att.id}
                  className="flex items-center gap-2 pl-2.5 pr-1.5 py-1 rounded-[11px] bg-[#171615] border border-[#2a2928] text-xs text-white shadow-sm"
                >
                  {att.is_image ? (
                    <ImageIcon className="w-3.5 h-3.5 text-[#34888D] flex-shrink-0" />
                  ) : (
                    <FileText className="w-3.5 h-3.5 text-[#34888D] flex-shrink-0" />
                  )}
                  <span className="truncate max-w-[140px] font-medium">{att.filename}</span>
                  <span className="text-[10px] text-[#949494] font-mono">
                    {(att.file_size_bytes / 1024).toFixed(1)} KB
                  </span>
                  <button
                    onClick={() => handleRemoveAttachment(att.id)}
                    className="p-1 hover:bg-[#201f1e] rounded-[6px] text-[#949494] hover:text-white transition-colors"
                    title="Remove attachment"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
              {isUploadingFile && (
                <div className="flex items-center gap-2 px-3 py-1 rounded-[11px] bg-[#016A71]/20 border border-[#016A71]/40 text-xs text-[#34888D]">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Processing file...</span>
                </div>
              )}
            </div>
          )}

          {/* Hidden File Input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*,.pdf,.docx,.doc,.txt,.md,.csv,.json,.py,.js,.ts,.tsx"
            className="hidden"
            onChange={(e) => handleFileSelect(e.target.files)}
          />

          {/* Clean Floating Input Box */}
          <div className="rounded-[12px] bg-[#171615] border border-[#2a2928] focus-within:border-[#34888D]/70 focus-within:ring-1 focus-within:ring-[#34888D]/50 transition-all p-2.5">
            <textarea
              ref={inputRef}
              rows={2}
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Ask ${activeWorkspace?.name || 'Aetherius'}...`}
              className="w-full bg-transparent px-2 py-1 text-sm text-white placeholder-[#949494] resize-none focus:outline-none max-h-32"
            />

            {/* Bottom Actions Row inside Input Box */}
            <div className="flex items-center justify-between pt-2 border-t border-[#2a2928]/60 mt-1">
              <div className="flex items-center gap-1.5">
                {/* Upload attachment button */}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploadingFile || isGenerating}
                  className="p-1.5 rounded-[9px] hover:bg-[#222120] text-[#949494] hover:text-white transition-colors border border-transparent hover:border-[#2a2928]"
                  title="Attach file, doc or image"
                >
                  <Paperclip className="w-4 h-4" />
                </button>

                {/* Quick Web Toggle Chip */}
                <button
                  type="button"
                  onClick={() => setUseWebSearch(!useWebSearch)}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-[9px] text-[11px] font-medium transition-all ${
                    useWebSearch
                      ? 'bg-[#016A71]/30 text-[#34888D] border border-[#016A71]/60'
                      : 'text-[#949494] hover:text-white hover:bg-[#222120]'
                  }`}
                  title="Search the live web"
                >
                  <Globe className="w-3 h-3" />
                  <span>Search</span>
                </button>

                {/* Quick RAG Toggle Chip */}
                <button
                  type="button"
                  onClick={() => setUseRAG(!useRAG)}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-[9px] text-[11px] font-medium transition-all ${
                    useRAG
                      ? 'bg-[#016A71]/30 text-[#34888D] border border-[#016A71]/60'
                      : 'text-[#949494] hover:text-white hover:bg-[#222120]'
                  }`}
                  title="Semantic RAG from company knowledge"
                >
                  <Database className="w-3 h-3" />
                  <span>RAG</span>
                </button>

                {/* Quick Image Gen Toggle Chip */}
                <button
                  type="button"
                  onClick={() => setUseImageGen(!useImageGen)}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-[9px] text-[11px] font-medium transition-all ${
                    useImageGen
                      ? 'bg-rose-500/25 text-rose-400 border border-rose-500/50'
                      : 'text-[#949494] hover:text-white hover:bg-[#222120]'
                  }`}
                  title="Generate AI Image or Diagram"
                >
                  <ImageIcon className="w-3 h-3" />
                  <span>Image</span>
                </button>
              </div>

              {/* Send Message Button */}
              <button
                onClick={handleSendMessage}
                disabled={
                  (!inputPrompt.trim() && attachments.length === 0) ||
                  isGenerating ||
                  isUploadingFile
                }
                className={`p-2 rounded-[10px] transition-all ${
                  (inputPrompt.trim() || attachments.length > 0) &&
                  !isGenerating &&
                  !isUploadingFile
                    ? 'bg-[#016A71] hover:bg-[#01575d] text-white shadow-[0_0_12px_rgba(1,106,113,0.35)]'
                    : 'bg-[#222120] text-[#949494]/40 cursor-not-allowed'
                }`}
                title="Send Message (Enter)"
              >
                <ArrowUp className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between mt-2 px-1 text-[11px] text-[#949494]">
            <span>Aetherius Intelligence • PostgreSQL pgvector RAG</span>
            <span className="hidden sm:inline">Press Enter to send, Shift+Enter for new line</span>
          </div>
        </div>
      </div>

      {/* Enhanced Full-Screen Image Lightbox Modal */}
      {previewImageModal && (
        <div
          onClick={() => {
            setPreviewImageModal(null);
            setImageZoom(1);
          }}
          className="fixed inset-0 z-50 bg-black/95 backdrop-blur-md flex flex-col items-center justify-center p-4 cursor-pointer select-none animate-in fade-in duration-200"
        >
          {/* Top Control Bar */}
          <div
            onClick={(e) => e.stopPropagation()}
            className="absolute top-4 inset-x-4 max-w-3xl mx-auto flex items-center justify-between z-10 px-4 py-2 rounded-[12px] bg-[#171615]/90 border border-[#2a2928] backdrop-blur-md text-white cursor-default shadow-xl"
          >
            <div className="flex items-center gap-2 text-xs font-semibold text-[#34888D]">
              <ImageIcon className="w-4 h-4" />
              <span>Aetherius Visual Preview</span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setImageZoom((prev) => Math.max(0.5, Number((prev - 0.25).toFixed(2))))}
                className="p-1.5 rounded-[8px] hover:bg-[#222120] text-[#949494] hover:text-white transition-colors"
                title="Zoom Out"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-xs font-mono text-[#949494] px-1 min-w-[42px] text-center">
                {Math.round(imageZoom * 100)}%
              </span>
              <button
                onClick={() => setImageZoom((prev) => Math.min(3, Number((prev + 0.25).toFixed(2))))}
                className="p-1.5 rounded-[8px] hover:bg-[#222120] text-[#949494] hover:text-white transition-colors"
                title="Zoom In"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                onClick={() => setImageZoom(1)}
                className="p-1.5 rounded-[8px] hover:bg-[#222120] text-[#949494] hover:text-white transition-colors"
                title="Reset Zoom (100%)"
              >
                <RotateCcw className="w-4 h-4" />
              </button>

              <div className="w-[1px] h-4 bg-[#2a2928] mx-1" />

              <a
                href={previewImageModal}
                download="aetherius_generated_image.png"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-[8px] bg-[#016A71] hover:bg-[#01575d] text-white text-xs font-medium transition-colors"
                title="Download full-resolution image"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Save</span>
              </a>

              <button
                onClick={() => {
                  setPreviewImageModal(null);
                  setImageZoom(1);
                }}
                className="p-1.5 rounded-[8px] hover:bg-[#222120] text-[#949494] hover:text-white transition-colors"
                title="Close (Esc)"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Image Container with zoom scale */}
          <div
            onClick={(e) => e.stopPropagation()}
            className="max-w-5xl max-h-[80vh] overflow-auto p-4 flex items-center justify-center cursor-default"
          >
            <img
              src={previewImageModal}
              alt="Enlarged Preview"
              style={{ transform: `scale(${imageZoom})`, transformOrigin: 'center' }}
              className="max-w-full max-h-[75vh] object-contain rounded-[11px] shadow-2xl transition-transform duration-150"
            />
          </div>
        </div>
      )}
    </div>
  );
};
