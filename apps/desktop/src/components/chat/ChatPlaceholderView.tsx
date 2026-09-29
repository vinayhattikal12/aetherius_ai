import React, { useState } from 'react';
import { WorkspaceResponse, ModelResponse } from '../../types';
import {
  Sparkles,
  Paperclip,
  Globe,
  BookOpen,
  Cpu,
  ArrowUp,
} from 'lucide-react';

interface ChatPlaceholderViewProps {
  activeWorkspace: WorkspaceResponse | null;
  models: ModelResponse[];
  onOpenModels: () => void;
}

export const ChatPlaceholderView: React.FC<ChatPlaceholderViewProps> = ({
  activeWorkspace,
  models,
  onOpenModels,
}) => {
  const [input, setInput] = useState('');
  const [webEnabled, setWebEnabled] = useState(false);
  const [knowledgeEnabled, setKnowledgeEnabled] = useState(true);

  const activeModel =
    models.find((m) => m.name === activeWorkspace?.preferred_model) ||
    models.find((m) => m.is_installed) ||
    models[0];

  const startersByWorkspace: Record<string, string[]> = {
    general: [
      'Summarize key insights from this document',
      'Explain quantum computing in simple terms',
      'Draft a professional project status email',
    ],
    developer: [
      'Implement JWT authentication flow in FastAPI',
      'Refactor this function for O(n) performance',
      'Explain the difference between pgvector cosine and L2 distance',
    ],
    student: [
      'Create 5 practice flashcards on cell biology',
      'Explain Bayes Theorem with a real-world example',
      'Summarize chapter 4 of my textbook',
    ],
    hr: [
      'Generate 5 behavioral interview questions for Senior Engineer',
      'Analyze job description requirements vs resume',
      'Draft an offer letter template',
    ],
  };

  const currentStarters =
    startersByWorkspace[activeWorkspace?.slug || 'general'] || startersByWorkspace.general;

  return (
    <div className="flex-1 flex flex-col justify-between max-w-4xl w-full mx-auto p-6 md:p-10 h-[calc(100vh-3.5rem)] select-none">
      {/* Top Banner / Workspace Context */}
      <div className="flex-1 flex flex-col items-center justify-center text-center space-y-6">
        <div
          className="w-12 h-12 rounded-2xl flex items-center justify-center text-white shadow-lg animate-in zoom-in duration-300"
          style={{
            backgroundColor: activeWorkspace?.color || '#6366f1',
            boxShadow: `0 10px 25px -5px ${activeWorkspace?.color}40`,
          }}
        >
          <Sparkles className="w-6 h-6 text-white" />
        </div>

        <div className="space-y-2">
          <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-white">
            {activeWorkspace?.name || 'General'} Workspace
          </h2>
          <p className="text-xs md:text-sm text-zinc-400 max-w-md mx-auto">
            {activeWorkspace?.description || 'Ask anything or collaborate on tasks with AI.'}
          </p>
        </div>

        {/* Quick Starters */}
        <div className="flex flex-wrap justify-center gap-2 max-w-lg pt-2">
          {currentStarters.map((starter, idx) => (
            <button
              key={idx}
              onClick={() => setInput(starter)}
              className="text-xs px-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition-all text-left"
            >
              {starter}
            </button>
          ))}
        </div>
      </div>

      {/* Input Box Shell */}
      <div className="w-full space-y-2">
        <div className="rounded-2xl bg-[#121215] border border-zinc-800/90 shadow-2xl p-3.5 focus-within:border-purple-500/80 transition-all">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Ask ${activeWorkspace?.name || 'Aetherius'} anything...`}
            rows={3}
            className="w-full bg-transparent text-sm text-zinc-100 placeholder-zinc-500 resize-none focus:outline-none"
          />

          <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60">
            {/* Action Tools Buttons */}
            <div className="flex items-center gap-1.5">
              <button
                className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
                title="Attach Document"
              >
                <Paperclip className="w-4 h-4" />
              </button>

              <button
                onClick={() => setWebEnabled(!webEnabled)}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs transition-colors ${
                  webEnabled
                    ? 'bg-purple-950 text-purple-300 border border-purple-800'
                    : 'text-zinc-400 hover:bg-zinc-800'
                }`}
              >
                <Globe className="w-3.5 h-3.5" />
                <span>Web</span>
              </button>

              <button
                onClick={() => setKnowledgeEnabled(!knowledgeEnabled)}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs transition-colors ${
                  knowledgeEnabled
                    ? 'bg-indigo-950 text-indigo-300 border border-indigo-800'
                    : 'text-zinc-400 hover:bg-zinc-800'
                }`}
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Knowledge</span>
              </button>

              <button
                onClick={onOpenModels}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs text-zinc-300 font-mono transition-colors"
              >
                <Cpu className="w-3.5 h-3.5 text-purple-400" />
                <span>{activeModel?.display_name.split(' ')[0] || 'Auto'}</span>
              </button>
            </div>

            {/* Send Button */}
            <button
              disabled={!input.trim()}
              className="p-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 text-white disabled:opacity-40 disabled:pointer-events-none shadow-md shadow-purple-900/30 hover:opacity-90 active:scale-95 transition-all"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="text-[11px] text-zinc-500 text-center">
          Phase 1 Foundation: Hardware-aware intelligence • pgvector ready • Modular router
        </div>
      </div>
    </div>
  );
};
