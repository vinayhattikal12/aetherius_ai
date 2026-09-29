import React, { useState } from 'react';
import {
  SquarePen,
  BookOpen,
  Layers,
  Bot,
  Wrench,
  Cpu,
  MoreHorizontal,
  Search,
  PanelLeftClose,
  PanelLeft,
  ChevronDown,
  ChevronRight,
  Trash2,
  Settings,
  Brain,
  ShieldCheck,
  Check,
  X,
} from 'lucide-react';
import { HardwareProfile, WorkspaceResponse, ConversationResponse } from '../../types';

export type NavItem =
  | 'chat'
  | 'chats'
  | 'knowledge'
  | 'memory'
  | 'tools'
  | 'workspaces'
  | 'agents'
  | 'models'
  | 'audit'
  | 'settings';

interface SidebarProps {
  activeNav: NavItem;
  onNavigate: (item: NavItem) => void;
  activeWorkspace: WorkspaceResponse | null;
  workspaces: WorkspaceResponse[];
  onSelectWorkspace: (slug: string) => void;
  hardwareProfile: HardwareProfile | null;
  conversations: ConversationResponse[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onCreateNewConversation: () => void;
  onDeleteConversation: (id: string, e: React.MouseEvent) => void;
  isOpen: boolean;
  onToggleOpen: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeNav,
  onNavigate,
  activeWorkspace,
  workspaces,
  onSelectWorkspace,
  hardwareProfile,
  conversations,
  activeConversationId,
  onSelectConversation,
  onCreateNewConversation,
  onDeleteConversation,
  isOpen,
  onToggleOpen,
}) => {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [showWorkspaceMenu, setShowWorkspaceMenu] = useState(false);
  const [recentsOpen, setRecentsOpen] = useState(true);
  const [activeMenuConvId, setActiveMenuConvId] = useState<string | null>(null);

  const filteredConversations = conversations.filter((c) =>
    (c.title || 'Untitled Session').toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Collapsed slim icon-only sidebar
  if (!isOpen) {
    return (
      <aside className="w-14 bg-[#000000] border-r border-[#2a2928] flex flex-col items-center justify-between py-3.5 select-none h-full flex-shrink-0 z-30">
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={onToggleOpen}
            className="p-2 rounded-[10px] hover:bg-[#171615] text-[#949494] hover:text-white transition-colors"
            title="Open Sidebar"
          >
            <PanelLeft className="w-5 h-5" />
          </button>

          <button
            onClick={() => {
              onCreateNewConversation();
              onNavigate('chat');
            }}
            className="p-2.5 rounded-[10px] bg-[#171615] hover:bg-[#201f1e] text-white border border-[#2a2928] hover:border-[#016A71]/60 transition-all"
            title="New Chat"
          >
            <SquarePen className="w-4 h-4 text-white" />
          </button>

          <div className="w-6 h-px bg-[#2a2928] my-1" />

          <button
            onClick={() => onNavigate('knowledge')}
            className={`p-2 rounded-[10px] transition-colors ${
              activeNav === 'knowledge'
                ? 'bg-[#171615] text-[#34888D]'
                : 'text-[#949494] hover:text-white'
            }`}
            title="Knowledge Base"
          >
            <BookOpen className="w-4 h-4" />
          </button>

          <button
            onClick={() => onNavigate('workspaces')}
            className={`p-2 rounded-[10px] transition-colors ${
              activeNav === 'workspaces'
                ? 'bg-[#171615] text-[#34888D]'
                : 'text-[#949494] hover:text-white'
            }`}
            title="Workspaces"
          >
            <Layers className="w-4 h-4" />
          </button>

          <button
            onClick={() => onNavigate('agents')}
            className={`p-2 rounded-[10px] transition-colors ${
              activeNav === 'agents'
                ? 'bg-[#171615] text-[#34888D]'
                : 'text-[#949494] hover:text-white'
            }`}
            title="Autonomous Agents"
          >
            <Bot className="w-4 h-4" />
          </button>

          <button
            onClick={() => onNavigate('tools')}
            className={`p-2 rounded-[10px] transition-colors ${
              activeNav === 'tools'
                ? 'bg-[#171615] text-[#34888D]'
                : 'text-[#949494] hover:text-white'
            }`}
            title="Tools Suite"
          >
            <Wrench className="w-4 h-4" />
          </button>

          <button
            onClick={() => onNavigate('models')}
            className={`p-2 rounded-[10px] transition-colors ${
              activeNav === 'models'
                ? 'bg-[#171615] text-[#34888D]'
                : 'text-[#949494] hover:text-white'
            }`}
            title="Model Registry"
          >
            <Cpu className="w-4 h-4" />
          </button>
        </div>

        <div className="flex flex-col items-center gap-2">
          <button
            onClick={() => onNavigate('settings')}
            className={`p-2 rounded-[10px] transition-colors ${
              activeNav === 'settings' ? 'bg-[#171615] text-white' : 'text-[#949494] hover:text-white'
            }`}
            title="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-64 bg-[#000000] border-r border-[#2a2928] flex flex-col justify-between select-none h-full overflow-hidden flex-shrink-0 z-30 font-sans">
      {/* Top Header & App Features Navigation */}
      <div className="p-3 pb-1 flex flex-col flex-shrink-0">
        {/* Brand Header Row with Search & Sidebar Collapse */}
        <div className="flex items-center justify-between px-2 pt-1 pb-2">
          <span className="font-bold text-base tracking-tight text-white flex items-center gap-2">
            <span>Aetherius</span>
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                setSearchOpen(!searchOpen);
                if (searchOpen) setSearchQuery('');
              }}
              className={`p-1.5 rounded-[8px] transition-colors ${
                searchOpen
                  ? 'bg-[#171615] text-white'
                  : 'text-[#949494] hover:text-white hover:bg-[#171615]'
              }`}
              title="Search Conversations"
            >
              <Search className="w-4 h-4" />
            </button>
            <button
              onClick={onToggleOpen}
              className="p-1.5 rounded-[8px] text-[#949494] hover:text-white hover:bg-[#171615] transition-colors"
              title="Close Sidebar"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Quick Search Bar (Toggled on Search button click) */}
        {searchOpen && (
          <div className="relative my-1 px-1 animate-in fade-in duration-150">
            <Search className="w-3.5 h-3.5 text-[#949494] absolute left-3.5 top-2.5" />
            <input
              type="text"
              placeholder="Search chats..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              autoFocus
              className="w-full bg-[#171615] border border-[#2a2928] rounded-[10px] pl-8 pr-7 py-1.5 text-xs text-white placeholder-[#949494] focus:outline-none focus:border-[#34888D]/70"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3.5 top-2 text-[#949494] hover:text-white"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        )}

        {/* New Chat Button */}
        <button
          onClick={() => {
            onCreateNewConversation();
            onNavigate('chat');
          }}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-[12px] bg-[#171615] hover:bg-[#201f1e] text-white text-sm font-medium transition-all my-1 border border-transparent hover:border-[#2a2928] active:scale-[0.99]"
        >
          <SquarePen className="w-4 h-4 text-white flex-shrink-0" />
          <span>New Chat</span>
        </button>

        {/* Primary Features Navigation List */}
        <div className="space-y-0.5 mt-1 text-sm text-zinc-300">
          {/* Knowledge Base */}
          <button
            onClick={() => onNavigate('knowledge')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-[10px] transition-colors text-left ${
              activeNav === 'knowledge'
                ? 'bg-[#171615] text-white font-medium'
                : 'hover:bg-[#171615]/70 hover:text-white'
            }`}
          >
            <BookOpen className="w-4 h-4 text-zinc-400 flex-shrink-0" />
            <span>Knowledge Base</span>
          </button>

          {/* Workspaces */}
          <div className="relative">
            <button
              onClick={() => setShowWorkspaceMenu(!showWorkspaceMenu)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-[10px] transition-colors text-left ${
                activeNav === 'workspaces'
                  ? 'bg-[#171615] text-white font-medium'
                  : 'hover:bg-[#171615]/70 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <Layers className="w-4 h-4 text-zinc-400 flex-shrink-0" />
                <span className="truncate">Workspaces</span>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-[#949494]" />
            </button>

            {/* Workspaces Dropdown */}
            {showWorkspaceMenu && (
              <div className="absolute top-full left-0 right-0 mt-1 z-50 bg-[#171615] border border-[#2a2928] rounded-[11px] shadow-2xl p-1.5 space-y-0.5 max-h-48 overflow-y-auto">
                <div className="px-2 py-1 text-[10px] font-semibold text-[#949494] uppercase tracking-wider flex items-center justify-between">
                  <span>Workspaces</span>
                  <button
                    onClick={() => {
                      onNavigate('workspaces');
                      setShowWorkspaceMenu(false);
                    }}
                    className="text-[#34888D] hover:underline"
                  >
                    View All
                  </button>
                </div>
                {workspaces.map((ws) => (
                  <button
                    key={ws.id}
                    onClick={() => {
                      onSelectWorkspace(ws.slug);
                      setShowWorkspaceMenu(false);
                      onNavigate('chat');
                    }}
                    className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-[8px] text-xs text-left transition-colors ${
                      activeWorkspace?.slug === ws.slug
                        ? 'bg-[#016A71]/20 text-[#34888D] font-medium'
                        : 'text-zinc-300 hover:text-white hover:bg-[#201f1e]'
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: ws.color }}
                      />
                      <span className="truncate">{ws.name}</span>
                    </div>
                    {activeWorkspace?.slug === ws.slug && (
                      <Check className="w-3.5 h-3.5 text-[#34888D]" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Autonomous Agents */}
          <button
            onClick={() => onNavigate('agents')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-[10px] transition-colors text-left ${
              activeNav === 'agents'
                ? 'bg-[#171615] text-white font-medium'
                : 'hover:bg-[#171615]/70 hover:text-white'
            }`}
          >
            <Bot className="w-4 h-4 text-zinc-400 flex-shrink-0" />
            <span>Autonomous Agents</span>
          </button>

          {/* Tools Suite */}
          <button
            onClick={() => onNavigate('tools')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-[10px] transition-colors text-left ${
              activeNav === 'tools'
                ? 'bg-[#171615] text-white font-medium'
                : 'hover:bg-[#171615]/70 hover:text-white'
            }`}
          >
            <Wrench className="w-4 h-4 text-zinc-400 flex-shrink-0" />
            <span>Tools Suite</span>
          </button>

          {/* Model Registry */}
          <button
            onClick={() => onNavigate('models')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-[10px] transition-colors text-left ${
              activeNav === 'models'
                ? 'bg-[#171615] text-white font-medium'
                : 'hover:bg-[#171615]/70 hover:text-white'
            }`}
          >
            <Cpu className="w-4 h-4 text-zinc-400 flex-shrink-0" />
            <span>Model Registry</span>
          </button>

          {/* More (Memory Bank & Audit Health) */}
          <div className="relative">
            <button
              onClick={() => setShowMoreMenu(!showMoreMenu)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-[10px] hover:bg-[#171615]/70 hover:text-white transition-colors text-left"
            >
              <div className="flex items-center gap-3">
                <MoreHorizontal className="w-4 h-4 text-zinc-400 flex-shrink-0" />
                <span>More</span>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-[#949494]" />
            </button>

            {showMoreMenu && (
              <div className="absolute top-full left-0 right-0 mt-1 z-50 bg-[#171615] border border-[#2a2928] rounded-[11px] shadow-2xl p-1.5 space-y-0.5">
                <button
                  onClick={() => {
                    onNavigate('memory');
                    setShowMoreMenu(false);
                  }}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-[8px] text-xs transition-colors ${
                    activeNav === 'memory'
                      ? 'bg-[#016A71]/20 text-[#34888D]'
                      : 'text-zinc-300 hover:text-white hover:bg-[#201f1e]'
                  }`}
                >
                  <Brain className="w-3.5 h-3.5 text-[#34888D]" />
                  <span>Memory Bank</span>
                </button>
                <button
                  onClick={() => {
                    onNavigate('audit');
                    setShowMoreMenu(false);
                  }}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-[8px] text-xs transition-colors ${
                    activeNav === 'audit'
                      ? 'bg-[#016A71]/20 text-[#34888D]'
                      : 'text-zinc-300 hover:text-white hover:bg-[#201f1e]'
                  }`}
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-[#34888D]" />
                  <span>Audit & Health</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Middle Scroll Area: Recents / Chat History (Single clean list like Image 2) */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        <button
          onClick={() => setRecentsOpen(!recentsOpen)}
          className="w-full flex items-center justify-between px-2 py-1 text-xs font-semibold text-[#949494] hover:text-white transition-colors"
        >
          <span>Recents</span>
          {recentsOpen ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" />
          )}
        </button>

        {recentsOpen && (
          <div className="space-y-0.5 mt-1">
            {filteredConversations.length === 0 ? (
              <div className="px-2 py-3 text-center text-[#949494] text-xs leading-relaxed">
                No conversations yet. Start a new chat!
              </div>
            ) : (
              filteredConversations.map((conv) => {
                const isActive = conv.id === activeConversationId && activeNav === 'chat';
                const isMenuOpen = activeMenuConvId === conv.id;

                return (
                  <div
                    key={conv.id}
                    onClick={() => {
                      onSelectConversation(conv.id);
                      onNavigate('chat');
                    }}
                    className={`group relative flex items-center justify-between px-3 py-2 rounded-[10px] text-xs cursor-pointer transition-all ${
                      isActive
                        ? 'bg-[#171615] text-white font-medium border border-[#2a2928]'
                        : 'text-zinc-200 hover:bg-[#171615]/80 hover:text-white'
                    }`}
                  >
                    <span className="truncate pr-2">{conv.title || 'Untitled Session'}</span>

                    {/* Right Action Menu on Hover */}
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveMenuConvId(isMenuOpen ? null : conv.id);
                        }}
                        className="p-1 hover:text-white text-[#949494] rounded transition-colors"
                        title="Chat Options"
                      >
                        <MoreHorizontal className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Chat Options Context Menu */}
                    {isMenuOpen && (
                      <div
                        onClick={(e) => e.stopPropagation()}
                        className="absolute right-2 top-8 z-50 bg-[#171615] border border-[#2a2928] rounded-[10px] shadow-2xl p-1.5 space-y-1 min-w-[120px]"
                      >
                        <button
                          onClick={(e) => {
                            onDeleteConversation(conv.id, e);
                            setActiveMenuConvId(null);
                          }}
                          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-[7px] text-xs text-rose-400 hover:bg-rose-500/10 text-left"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          <span>Delete</span>
                        </button>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* Bottom Profile / Workspace Footer */}
      <div className="p-3 border-t border-[#2a2928] bg-[#000000] flex items-center justify-between">
        <button
          onClick={() => onNavigate('settings')}
          className="flex items-center gap-3 min-w-0 flex-1 text-left p-1.5 rounded-[10px] hover:bg-[#171615] transition-colors group"
        >
          {/* User Avatar Circle */}
          <div className="w-8 h-8 rounded-full bg-[#016A71] text-white font-bold text-xs flex items-center justify-center flex-shrink-0 shadow-sm border border-[#34888D]/40">
            AE
          </div>

          <div className="flex flex-col min-w-0 flex-1">
            <span className="text-xs font-semibold text-white truncate group-hover:text-[#34888D] transition-colors">
              Aetherius User
            </span>
            <span className="text-[11px] text-[#949494] truncate">
              {activeWorkspace?.name || 'General'} • {hardwareProfile?.compute_tier || 'Ready'}
            </span>
          </div>
        </button>

        <button
          onClick={() => onNavigate('settings')}
          className="p-2 rounded-[9px] hover:bg-[#171615] text-[#949494] hover:text-white transition-colors"
          title="Settings"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
};
