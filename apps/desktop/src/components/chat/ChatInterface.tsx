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
  ArrowDown,
  Square,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Plus,
  Mic,
  MicOff,
  AudioWaveform,
  Search,
  Cpu,
  Cloud,
  Wand2,
} from 'lucide-react';

interface AssistantMessageBodyProps {
  content: string;
  modelName?: string;
  isGenerating?: boolean;
  onImageClick?: (url: string) => void;
}

const AssistantMessageBody: React.FC<AssistantMessageBodyProps> = ({
  content,
  modelName,
  isGenerating,
  onImageClick,
}) => {
  const [showThinking, setShowThinking] = useState<boolean>(true);

  if (!content) {
    return (
      <div className="flex items-center gap-2.5 py-2 px-3.5 rounded-[12px] bg-[#161615] border border-[#2a2928] text-xs text-[#34888D] w-fit shadow-sm animate-pulse">
        <Loader2 className="w-4 h-4 animate-spin text-[#34888D]" />
        <span className="font-medium text-white/90">
          {modelName ? `${modelName} reasoning & generating...` : 'Reasoning & generating response...'}
        </span>
      </div>
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
        <div className="rounded-[12px] border border-[#016A71]/35 bg-[#016A71]/10 overflow-hidden text-xs">
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
        <div className="relative">
          <MarkdownContent content={answer} onImageClick={onImageClick} />
          {isGenerating && (
            <span className="inline-block w-1.5 h-3.5 ml-1 bg-[#34888D] animate-pulse align-middle rounded-sm" />
          )}
        </div>
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
  const [useRAG, setUseRAG] = useState<boolean>(false);
  const [useWebSearch, setUseWebSearch] = useState<boolean>(false);
  const [useImageGen, setUseImageGen] = useState<boolean>(false);
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);

  const [isModelMenuOpen, setIsModelMenuOpen] = useState<boolean>(false);
  const [isPlusMenuOpen, setIsPlusMenuOpen] = useState<boolean>(false);
  const [modelSearchQuery, setModelSearchQuery] = useState<string>('');
  const [isListening, setIsListening] = useState<boolean>(false);
  const [showScrollBottomBtn, setShowScrollBottomBtn] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isUserScrolledUpRef = useRef<boolean>(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const modelMenuRef = useRef<HTMLDivElement>(null);
  const plusMenuRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const activeStreamingConvIdRef = useRef<string | null>(null);

  // Close menus on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modelMenuRef.current && !modelMenuRef.current.contains(e.target as Node)) {
        setIsModelMenuOpen(false);
      }
      if (plusMenuRef.current && !plusMenuRef.current.contains(e.target as Node)) {
        setIsPlusMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Close image modal on Escape key
  useEffect(() => {
    const handleKeyDownGlobal = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (previewImageModal) {
          setPreviewImageModal(null);
          setImageZoom(1);
        }
        setIsModelMenuOpen(false);
        setIsPlusMenuOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDownGlobal);
    return () => window.removeEventListener('keydown', handleKeyDownGlobal);
  }, [previewImageModal]);

  // Filter for models that are ready for chat inference:
  // 1. Must not be pure embedding models
  // 2. Local models must be DOWNLOADED on PC (is_installed === true)
  // 3. Cloud models only if API key is configured (is_installed === true)
  const chatModels = models.filter((m) => {
    const isEmbed =
      m.category?.toLowerCase() === 'embedding' ||
      m.name.toLowerCase().includes('embed') ||
      m.display_name?.toLowerCase().includes('embed');
    if (isEmbed) return false;

    // Only display downloaded local models or active cloud models with API keys
    return m.is_installed === true;
  });

  // Auto-resize textarea
  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputPrompt(e.target.value);
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 220)}px`;
    }
  };

  // Helper for Claude-style model button display
  const getModelDisplay = (id: string) => {
    if (!id || id === 'auto') {
      return {
        name: 'Auto Router',
        badge: 'Smart',
        desc: 'Sub-millisecond dynamic routing across your installed local models',
        isLocal: false,
        isInstalled: true,
      };
    }

    const match = chatModels.find(
      (m) =>
        m.id === id ||
        m.name === id ||
        m.name.toLowerCase() === id.toLowerCase() ||
        (m.display_name && m.display_name.toLowerCase() === id.toLowerCase())
    );

    if (match) {
      let name = match.display_name || match.name;
      let badge = match.is_local ? 'Local' : 'Cloud';

      if (name.includes('Claude 3.7 Sonnet') || name.includes('Claude 3.5')) {
        name = 'Sonnet 3.5';
        badge = 'Medium';
      } else if (name.includes('Qwen 2.5 Coder 7B')) {
        name = 'Qwen 2.5 Coder';
        badge = '7B Local';
      } else if (name.includes('Llama 3.2 3B')) {
        name = 'Llama 3.2';
        badge = '3B Local';
      } else if (name.includes('DeepSeek R1')) {
        name = 'DeepSeek R1';
        badge = 'Reasoning';
      } else if (name.includes('Mistral 7B')) {
        name = 'Mistral 7B';
        badge = 'Local';
      }

      return {
        name,
        badge,
        desc: match.description || (match.is_local ? 'Local downloaded model' : 'Frontier cloud model'),
        isLocal: match.is_local,
        isInstalled: match.is_installed,
      };
    }

    return {
      name: 'Auto Router',
      badge: 'Smart',
      desc: 'Sub-millisecond dynamic routing across your installed local models',
      isLocal: false,
      isInstalled: true,
    };
  };

  const currentDisplay = getModelDisplay(selectedModelId);

  // Web Speech API Voice Dictation
  const handleToggleVoiceDictation = () => {
    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser/environment.');
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          transcript += event.results[i][0].transcript;
        }
        if (transcript) {
          setInputPrompt((prev) => (prev ? `${prev} ${transcript}` : transcript));
        }
      };

      recognition.onerror = (event: any) => {
        console.warn('Speech recognition notice:', event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.warn('Speech recognition init error:', err);
      setIsListening(false);
    }
  };

  useEffect(() => {
    if (activeConversationId) {
      // Do not wipe out in-flight streaming messages if the ID was just assigned by the current stream
      if (activeConversationId !== activeStreamingConvIdRef.current) {
        loadMessages(activeConversationId);
      }
    } else {
      setMessages([]);
    }
  }, [activeConversationId]);

  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    const isUp = distanceFromBottom > 90;
    isUserScrolledUpRef.current = isUp;
    setShowScrollBottomBtn(isUp);
  };

  const scrollToBottom = (force = false) => {
    if (!force && isUserScrolledUpRef.current) return;
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleScrollToBottomClick = () => {
    isUserScrolledUpRef.current = false;
    setShowScrollBottomBtn(false);
    scrollToBottom(true);
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsGenerating(false);
    activeStreamingConvIdRef.current = null;
  };

  useEffect(() => {
    if (!isUserScrolledUpRef.current) {
      scrollToBottom();
    }
  }, [messages, isGenerating]);

  const loadMessages = async (convId: string) => {
    try {
      const conv = await api.getConversation(convId);
      if (convId !== activeStreamingConvIdRef.current) {
        setMessages(conv.messages || []);
        if (conv.model_name) {
          setSelectedModelId(conv.model_name);
        }
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

  const handleSelectModel = (modelId: string) => {
    setSelectedModelId(modelId);
    setIsModelMenuOpen(false);
  };

  const handleSendMessage = async () => {
    const text = inputPrompt.trim();
    if ((!text && attachments.length === 0) || isGenerating || isUploadingFile) return;

    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
    }

    const activeAttachments = [...attachments];
    setInputPrompt('');
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }
    setAttachments([]);
    setIsGenerating(true);
    activeStreamingConvIdRef.current = activeConversationId || 'pending_stream';

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
        activeStreamingConvIdRef.current = null;
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
    isUserScrolledUpRef.current = false;
    setShowScrollBottomBtn(false);
    setTimeout(() => scrollToBottom(true), 50);

    const controller = new AbortController();
    abortControllerRef.current = controller;

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
            if (data.conversation_id) {
              activeStreamingConvIdRef.current = data.conversation_id;
              if (activeConversationId !== data.conversation_id) {
                setActiveConversationId(data.conversation_id);
              }
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
            activeStreamingConvIdRef.current = null;
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
            activeStreamingConvIdRef.current = null;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAssistantId
                  ? {
                      ...m,
                      content: `⚠️ Error communicating with AI engine: ${
                        err.message || 'Check PostgreSQL & model service.'
                      }`,
                      generation_metadata: { error: true },
                    }
                  : m
              )
            );
          },
        },
        controller.signal
      );
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error('Chat error:', err);
      }
    } finally {
      setIsGenerating(false);
      abortControllerRef.current = null;
      activeStreamingConvIdRef.current = null;
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

  // Filter models for popup list
  const filteredModels = chatModels.filter((m) => {
    const q = modelSearchQuery.toLowerCase();
    return (
      m.name.toLowerCase().includes(q) ||
      (m.display_name && m.display_name.toLowerCase().includes(q)) ||
      (m.category && m.category.toLowerCase().includes(q))
    );
  });

  return (
    <div className="flex flex-col h-full bg-[#000000] text-white relative select-none">
      {/* Sleek Minimalist Top Bar */}
      <header className="h-12 px-4 flex items-center justify-between bg-[#000000] flex-shrink-0 z-10">
        <div className="flex items-center gap-2">
          {!isSidebarOpen && onToggleSidebar && (
            <button
              onClick={onToggleSidebar}
              className="p-1.5 rounded-[9px] hover:bg-[#1c1b1a] text-[#949494] hover:text-white transition-colors"
              title="Open Sidebar"
            >
              <PanelLeft className="w-4 h-4" />
            </button>
          )}

          <div className="flex items-center gap-2 text-xs font-semibold text-[#c4c4c4]">
            <span
              className="w-2 h-2 rounded-full ring-2 ring-[#016A71]/40"
              style={{ backgroundColor: activeWorkspace?.color || '#016A71' }}
            />
            <span>{activeWorkspace?.name || 'Aetherius'}</span>
          </div>
        </div>

        {/* Right Action: Export Button */}
        <div className="flex items-center gap-2">
          {activeConversationId && (
            <a
              href={api.getExportUrl(activeConversationId, 'markdown')}
              target="_blank"
              rel="noreferrer"
              download={`session-${activeConversationId}.md`}
              className="p-1.5 rounded-[9px] text-[#949494] hover:text-white hover:bg-[#1c1b1a] transition-colors"
              title="Export Conversation"
            >
              <Download className="w-4 h-4" />
            </a>
          )}
        </div>
      </header>

      {/* Main Conversation Stream (Centered Max-W-3XL layout) */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className="flex-1 overflow-y-auto px-4 md:px-6 py-4 select-text relative"
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
              <div className="w-12 h-12 rounded-[14px] bg-[#016A71]/15 border border-[#016A71]/30 flex items-center justify-center mb-4 shadow-[0_0_24px_rgba(1,106,113,0.25)]">
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
                    onClick={() => {
                      setInputPrompt(sug.prompt);
                      if (inputRef.current) inputRef.current.focus();
                    }}
                    className="p-4 rounded-[14px] bg-[#161615] border border-[#262524] hover:border-[#34888D]/60 hover:bg-[#1c1b1a] transition-all text-left group"
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
                    className={`w-full rounded-[14px] p-4 text-sm leading-relaxed ${
                      isUser
                        ? 'bg-[#18181b] border border-[#2a2928] text-white shadow-sm max-w-[85%]'
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
                              className="relative rounded-[12px] overflow-hidden border border-[#2a2928] cursor-pointer group max-w-[260px] max-h-[180px] bg-black/40"
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
                              className="flex items-center gap-2.5 px-3 py-2 rounded-[11px] bg-[#161615] border border-[#2a2928] text-xs text-white"
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
                        modelName={msg.model_id || selectedModelId}
                        isGenerating={isGenerating && idx === messages.length - 1}
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
                              className="p-3 rounded-[11px] bg-[#161615] border border-[#2a2928] text-xs flex flex-col justify-between"
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

        {/* Floating Scroll to Bottom Button */}
        {showScrollBottomBtn && (
          <div className="sticky bottom-4 inset-x-0 flex justify-center pointer-events-none z-30">
            <button
              type="button"
              onClick={handleScrollToBottomClick}
              className="pointer-events-auto px-3.5 py-1.5 rounded-full bg-[#1e1d1c]/95 hover:bg-[#2c2b29] border border-[#3e3d3a] text-white shadow-2xl backdrop-blur-md transition-all flex items-center gap-2 text-xs group animate-in fade-in slide-in-from-bottom-2"
              title="Scroll to bottom"
            >
              <ArrowDown className="w-3.5 h-3.5 text-[#34888D] group-hover:translate-y-0.5 transition-transform" />
              <span className="text-[11px] text-[#c4c4c4] font-medium">Scroll to bottom</span>
            </button>
          </div>
        )}
      </div>

      {/* Claude-Style Chat Input Dock (Image 2 format) */}
      <div className="p-4 bg-[#000000] flex-shrink-0">
        <div className="max-w-3xl mx-auto">
          {/* Attachment Preview Chips */}
          {(attachments.length > 0 || isUploadingFile) && (
            <div className="flex flex-wrap gap-2 mb-2 px-1">
              {attachments.map((att) => (
                <div
                  key={att.id}
                  className="flex items-center gap-2 pl-2.5 pr-1.5 py-1 rounded-[10px] bg-[#18181b] border border-[#2e2d2c] text-xs text-white shadow-sm"
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
                    className="p-1 hover:bg-[#282725] rounded-[6px] text-[#949494] hover:text-white transition-colors"
                    title="Remove attachment"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
              {isUploadingFile && (
                <div className="flex items-center gap-2 px-3 py-1 rounded-[10px] bg-[#016A71]/20 border border-[#016A71]/40 text-xs text-[#34888D]">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Processing file...</span>
                </div>
              )}
            </div>
          )}

          {/* Active Feature Indicators (Web, Image Gen) */}
          {(useWebSearch || useImageGen) && (
            <div className="flex items-center gap-2 mb-2 px-1 text-[11px]">
              {useWebSearch && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#016A71]/25 text-[#34888D] border border-[#016A71]/40">
                  <Globe className="w-3 h-3" /> Live Web Search Active
                </span>
              )}
              {useImageGen && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/40">
                  <Wand2 className="w-3 h-3" /> Image / Diagram Mode Active
                </span>
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

          {/* Claude Card Container matching Image 2 */}
          <div className="relative rounded-[22px] bg-[#1a1918] border border-[#2e2d2c] focus-within:border-[#4a4947] shadow-[0_8px_30px_rgba(0,0,0,0.45)] transition-all p-3 flex flex-col justify-between min-h-[96px]">
            {/* Top Textarea */}
            <textarea
              ref={inputRef}
              rows={1}
              value={inputPrompt}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              placeholder="How can I help you today?"
              className="w-full bg-transparent px-2.5 pt-1 pb-2 text-[15px] text-white placeholder-[#787775] resize-none focus:outline-none leading-relaxed overflow-y-auto"
              style={{ maxHeight: '200px' }}
            />

            {/* Bottom Row Inside Input Box (matching Image 2) */}
            <div className="flex items-center justify-between pt-1.5 px-1 relative">
              {/* Left Side: Plus (+) Button with Popup Menu */}
              <div className="relative" ref={plusMenuRef}>
                <button
                  type="button"
                  onClick={() => setIsPlusMenuOpen(!isPlusMenuOpen)}
                  className="p-1.5 rounded-full hover:bg-[#292827] text-[#9c9b98] hover:text-white transition-colors flex items-center justify-center"
                  title="Add attachments & capabilities"
                >
                  <Plus className="w-5 h-5 stroke-[2.2]" />
                </button>

                {/* Plus Action Popup Menu */}
                {isPlusMenuOpen && (
                  <div className="absolute bottom-full left-0 mb-3 w-64 rounded-[16px] bg-[#1a1918] border border-[#2e2d2c] shadow-[0_12px_40px_rgba(0,0,0,0.8)] backdrop-blur-xl p-2 z-50 animate-in fade-in slide-in-from-bottom-2 duration-150">
                    <div className="text-[11px] font-semibold text-[#787775] px-2 py-1 uppercase tracking-wider">
                      Capabilities & Attachments
                    </div>

                    <button
                      type="button"
                      onClick={() => {
                        setIsPlusMenuOpen(false);
                        fileInputRef.current?.click();
                      }}
                      className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-[10px] hover:bg-[#262524] text-xs text-white transition-colors text-left"
                    >
                      <Paperclip className="w-4 h-4 text-[#34888D]" />
                      <div>
                        <div className="font-medium">Attach File / Image</div>
                        <div className="text-[10px] text-[#949494]">PDF, Docs, Code, CSV, Images</div>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setUseWebSearch(!useWebSearch);
                        setIsPlusMenuOpen(false);
                      }}
                      className="w-full flex items-center justify-between px-2.5 py-2 rounded-[10px] hover:bg-[#262524] text-xs text-white transition-colors text-left"
                    >
                      <div className="flex items-center gap-2.5">
                        <Globe className="w-4 h-4 text-[#34888D]" />
                        <div>
                          <div className="font-medium">Web Search</div>
                          <div className="text-[10px] text-[#949494]">Retrieve live web intelligence</div>
                        </div>
                      </div>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                          useWebSearch ? 'bg-[#016A71] text-white' : 'bg-[#292827] text-[#949494]'
                        }`}
                      >
                        {useWebSearch ? 'ON' : 'OFF'}
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setUseRAG(!useRAG);
                        setIsPlusMenuOpen(false);
                      }}
                      className="w-full flex items-center justify-between px-2.5 py-2 rounded-[10px] hover:bg-[#262524] text-xs text-white transition-colors text-left"
                    >
                      <div className="flex items-center gap-2.5">
                        <Database className="w-4 h-4 text-[#34888D]" />
                        <div>
                          <div className="font-medium">Knowledge Base RAG</div>
                          <div className="text-[10px] text-[#949494]">Query indexed workspace documents</div>
                        </div>
                      </div>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                          useRAG ? 'bg-[#016A71] text-white' : 'bg-[#292827] text-[#949494]'
                        }`}
                      >
                        {useRAG ? 'ON' : 'OFF'}
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setUseImageGen(!useImageGen);
                        setIsPlusMenuOpen(false);
                      }}
                      className="w-full flex items-center justify-between px-2.5 py-2 rounded-[10px] hover:bg-[#262524] text-xs text-white transition-colors text-left"
                    >
                      <div className="flex items-center gap-2.5">
                        <Wand2 className="w-4 h-4 text-rose-400" />
                        <div>
                          <div className="font-medium">Visual Generation</div>
                          <div className="text-[10px] text-[#949494]">Render diagrams & illustrations</div>
                        </div>
                      </div>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                          useImageGen ? 'bg-rose-600 text-white' : 'bg-[#292827] text-[#949494]'
                        }`}
                      >
                        {useImageGen ? 'ON' : 'OFF'}
                      </span>
                    </button>
                  </div>
                )}
              </div>

              {/* Right Side: Claude-style Model Selector + Mic + Waveform/Send */}
              <div className="flex items-center gap-1.5 sm:gap-2">
                {/* Model Selector Dropdown Trigger Button */}
                <div className="relative" ref={modelMenuRef}>
                  <button
                    type="button"
                    onClick={() => setIsModelMenuOpen(!isModelMenuOpen)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-[12px] text-xs font-medium text-[#c4c4c4] hover:text-white hover:bg-[#292827] transition-all cursor-pointer border border-transparent hover:border-[#383735]"
                    title="Change Model"
                  >
                    <span>{currentDisplay.name}</span>
                    <span className="text-[10px] text-[#949494] font-normal px-1 py-0.5 rounded bg-white/5">
                      {currentDisplay.badge}
                    </span>
                    <ChevronDown className="w-3.5 h-3.5 text-[#949494]" />
                  </button>

                  {/* Claude Model Selection Dropdown Popup */}
                  {isModelMenuOpen && (
                    <div className="absolute bottom-full right-0 mb-3 w-80 max-h-96 rounded-[18px] bg-[#1a1918] border border-[#2e2d2c] shadow-[0_16px_50px_rgba(0,0,0,0.85)] backdrop-blur-xl p-2.5 z-50 flex flex-col animate-in fade-in slide-in-from-bottom-2 duration-150">
                      {/* Search bar inside model menu */}
                      <div className="relative mb-2">
                        <Search className="w-3.5 h-3.5 text-[#787775] absolute left-3 top-2.5" />
                        <input
                          type="text"
                          value={modelSearchQuery}
                          onChange={(e) => setModelSearchQuery(e.target.value)}
                          placeholder="Search models..."
                          className="w-full bg-[#262524] rounded-[10px] pl-8 pr-3 py-1.5 text-xs text-white placeholder-[#787775] focus:outline-none border border-transparent focus:border-[#34888D]"
                        />
                      </div>

                      <div className="overflow-y-auto max-h-72 space-y-1 pr-1 custom-scrollbar">
                        {/* Auto Smart Router Option */}
                        <button
                          type="button"
                          onClick={() => handleSelectModel('auto')}
                          className={`w-full flex items-center justify-between p-2.5 rounded-[12px] text-left transition-all ${
                            selectedModelId === 'auto'
                              ? 'bg-[#016A71]/25 border border-[#016A71]/50 text-white'
                              : 'hover:bg-[#262524] text-[#c4c4c4]'
                          }`}
                        >
                          <div className="flex items-center gap-2.5">
                            <Sparkles className="w-4 h-4 text-[#34888D] flex-shrink-0" />
                            <div>
                              <div className="text-xs font-semibold text-white flex items-center gap-1.5">
                                <span>Auto (Sub-ms Smart Router)</span>
                                <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#016A71]/30 text-[#34888D] font-mono">
                                  Default
                                </span>
                              </div>
                              <div className="text-[10px] text-[#949494] mt-0.5">
                                Intelligently selects best model per query
                              </div>
                            </div>
                          </div>
                          {selectedModelId === 'auto' && (
                            <Check className="w-4 h-4 text-[#34888D] flex-shrink-0" />
                          )}
                        </button>

                        {/* Local & Cloud Models */}
                        <div className="pt-2 pb-1 text-[10px] font-semibold text-[#787775] uppercase tracking-wider px-2">
                          Available Models ({filteredModels.length})
                        </div>

                        {filteredModels.map((m) => {
                          const isSelected =
                            selectedModelId === m.id ||
                            selectedModelId === m.name ||
                            (m.name && selectedModelId.toLowerCase() === m.name.toLowerCase());
                          return (
                            <button
                              key={m.id}
                              type="button"
                              onClick={() => handleSelectModel(m.name || m.id)}
                              className={`w-full flex items-center justify-between p-2.5 rounded-[12px] text-left transition-all ${
                                isSelected
                                  ? 'bg-[#016A71]/25 border border-[#016A71]/50 text-white'
                                  : 'hover:bg-[#262524] text-[#c4c4c4]'
                              }`}
                            >
                              <div className="flex items-center gap-2.5 min-w-0">
                                {m.is_local ? (
                                  <Cpu className="w-4 h-4 text-[#34888D] flex-shrink-0" />
                                ) : (
                                  <Cloud className="w-4 h-4 text-purple-400 flex-shrink-0" />
                                )}
                                <div className="min-w-0">
                                  <div className="text-xs font-medium text-white truncate flex items-center gap-1.5">
                                    <span className="truncate">{m.display_name || m.name}</span>
                                    <span
                                      className={`text-[9px] px-1.5 py-0.2 rounded font-mono ${
                                        m.is_local
                                          ? m.is_installed
                                            ? 'bg-emerald-500/20 text-emerald-300'
                                            : 'bg-amber-500/20 text-amber-300'
                                          : 'bg-purple-500/20 text-purple-300'
                                      }`}
                                    >
                                      {m.is_local ? (m.is_installed ? 'Local' : 'Pull') : 'Cloud'}
                                    </span>
                                  </div>
                                  <div className="text-[10px] text-[#949494] truncate mt-0.5">
                                    {m.description || m.category || 'General language model'}
                                  </div>
                                </div>
                              </div>
                              {isSelected && (
                                <Check className="w-4 h-4 text-[#34888D] flex-shrink-0 ml-2" />
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Microphone / Voice Dictation Button */}
                <button
                  type="button"
                  onClick={handleToggleVoiceDictation}
                  className={`p-1.5 rounded-full transition-all ${
                    isListening
                      ? 'bg-rose-500/30 text-rose-400 animate-pulse ring-2 ring-rose-500/50'
                      : 'hover:bg-[#292827] text-[#9c9b98] hover:text-white'
                  }`}
                  title={isListening ? 'Stop voice recording' : 'Voice dictation'}
                >
                  {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>

                {/* Audio Waveform / Mode Icon & Send Arrow / Stop Button */}
                {isGenerating ? (
                  <button
                    type="button"
                    onClick={handleStopGeneration}
                    className="p-1.5 rounded-full bg-white text-black hover:bg-white/90 shadow-[0_0_12px_rgba(255,255,255,0.3)] transition-all flex items-center justify-center group"
                    title="Stop generation"
                  >
                    <Square className="w-3.5 h-3.5 fill-black group-hover:scale-90 transition-transform" />
                  </button>
                ) : inputPrompt.trim() || attachments.length > 0 ? (
                  <button
                    type="button"
                    onClick={handleSendMessage}
                    disabled={isUploadingFile}
                    className={`p-1.5 rounded-full transition-all flex items-center justify-center ${
                      !isUploadingFile
                        ? 'bg-white text-black hover:bg-white/90 shadow-[0_0_12px_rgba(255,255,255,0.25)]'
                        : 'bg-[#292827] text-[#787775] cursor-not-allowed'
                    }`}
                    title="Send Message (Enter)"
                  >
                    <ArrowUp className="w-4 h-4 stroke-[2.5]" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleToggleVoiceDictation}
                    className="flex items-center gap-0.5 p-1.5 rounded-full hover:bg-[#292827] text-[#9c9b98] hover:text-white transition-colors"
                    title="Audio mode"
                  >
                    <AudioWaveform className="w-4 h-4" />
                    <ChevronDown className="w-3 h-3 text-[#787775]" />
                  </button>
                )}
              </div>
            </div>
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
            className="absolute top-4 inset-x-4 max-w-3xl mx-auto flex items-center justify-between z-10 px-4 py-2 rounded-[14px] bg-[#18181b]/90 border border-[#2e2d2c] backdrop-blur-md text-white cursor-default shadow-xl"
          >
            <div className="flex items-center gap-2 text-xs font-semibold text-[#34888D]">
              <ImageIcon className="w-4 h-4" />
              <span>Aetherius Visual Preview</span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setImageZoom((prev) => Math.max(0.5, Number((prev - 0.25).toFixed(2))))}
                className="p-1.5 rounded-[8px] hover:bg-[#282725] text-[#949494] hover:text-white transition-colors"
                title="Zoom Out"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-xs font-mono text-[#949494] px-1 min-w-[42px] text-center">
                {Math.round(imageZoom * 100)}%
              </span>
              <button
                onClick={() => setImageZoom((prev) => Math.min(3, Number((prev + 0.25).toFixed(2))))}
                className="p-1.5 rounded-[8px] hover:bg-[#282725] text-[#949494] hover:text-white transition-colors"
                title="Zoom In"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                onClick={() => setImageZoom(1)}
                className="p-1.5 rounded-[8px] hover:bg-[#282725] text-[#949494] hover:text-white transition-colors"
                title="Reset Zoom (100%)"
              >
                <RotateCcw className="w-4 h-4" />
              </button>

              <div className="w-[1px] h-4 bg-[#2e2d2c] mx-1" />

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
                className="p-1.5 rounded-[8px] hover:bg-[#282725] text-[#949494] hover:text-white transition-colors"
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
              className="max-w-full max-h-[75vh] object-contain rounded-[14px] shadow-2xl transition-transform duration-150"
            />
          </div>
        </div>
      )}
    </div>
  );
};
