import React, { useState, useEffect } from 'react';
import {
  MemoryResponse,
  WorkspaceResponse,
  MemorySearchResult
} from '../../types';
import { api } from '../../services/api';
import {
  Brain,
  Plus,
  Trash2,
  Search,
  Loader2,
  Eye,
  Star,
} from 'lucide-react';

interface MemoryViewProps {
  activeWorkspace: WorkspaceResponse | null;
}

export const MemoryView: React.FC<MemoryViewProps> = ({ activeWorkspace }) => {
  const [memories, setMemories] = useState<MemoryResponse[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchResults, setSearchResults] = useState<MemorySearchResult | null>(null);
  const [selectedType, setSelectedType] = useState<string>('all');
  const [showAddModal, setShowAddModal] = useState<boolean>(false);

  // Form State
  const [newContent, setNewContent] = useState<string>('');
  const [newType, setNewType] = useState<string>('preference');
  const [newImportance, setNewImportance] = useState<number>(3.0);

  useEffect(() => {
    loadMemories();
  }, [activeWorkspace?.slug, selectedType]);

  const loadMemories = async () => {
    setIsLoading(true);
    try {
      const typeFilter = selectedType === 'all' ? undefined : selectedType;
      const list = await api.getMemories(activeWorkspace?.slug, typeFilter);
      setMemories(list);
    } catch (err) {
      console.error('Failed to load memories:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim()) return;

    try {
      const created = await api.createMemory({
        workspace_slug: activeWorkspace?.slug || 'general',
        memory_type: newType,
        content: newContent.trim(),
        importance_weight: newImportance,
        confidence_score: 1.0,
      });
      setMemories((prev) => [created, ...prev]);
      setShowAddModal(false);
      setNewContent('');
      setNewImportance(3.0);
    } catch (err: any) {
      alert(`Failed to add memory: ${err.message}`);
    }
  };

  const handleDeleteMemory = async (memoryId: string) => {
    try {
      await api.deleteMemory(memoryId);
      setMemories((prev) => prev.filter((m) => m.id !== memoryId));
      if (searchResults) {
        setSearchResults({
          ...searchResults,
          memories: searchResults.memories.filter((m) => m.id !== memoryId),
        });
      }
    } catch (err: any) {
      alert(`Failed to delete memory: ${err.message}`);
    }
  };

  const handleSearchMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }

    setIsSearching(true);
    try {
      const result = await api.searchMemories({
        query: searchQuery.trim(),
        workspace_slug: activeWorkspace?.slug,
        top_k: 5,
        min_similarity: 0.05,
      });
      setSearchResults(result);
    } catch (err) {
      console.error('Memory vector search failed:', err);
    } finally {
      setIsSearching(false);
    }
  };

  const displayedMemories = searchResults ? searchResults.memories : memories;

  return (
    <div className="flex h-full bg-[#000000] text-white flex-col overflow-hidden">
      {/* Top Header */}
      <div className="p-6 border-b border-[#2a2928] bg-[#000000] flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-[11px] bg-[#016A71]/15 border border-[#016A71]/30 flex items-center justify-center">
              <Brain className="w-4 h-4 text-[#34888D]" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">Episodic & Semantic Memory</h2>
              <p className="text-xs text-[#949494]">
                Persistent user preferences, project standards, and verified facts stored in PostgreSQL.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-[11px] bg-[#016A71] hover:bg-[#01575d] text-white text-xs font-semibold shadow-[0_0_12px_rgba(1,106,113,0.3)] transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Memory</span>
          </button>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="p-4 border-b border-[#2a2928] bg-[#171615]/50 flex flex-col sm:flex-row items-center justify-between gap-3">
        <form onSubmit={handleSearchMemory} className="relative flex-1 w-full max-w-md">
          <Search className="w-3.5 h-3.5 text-[#949494] absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search memory semantics (e.g. 'coding preferences')..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#171615] border border-[#2a2928] rounded-[11px] pl-9 pr-8 py-1.5 text-xs text-white placeholder-[#949494] focus:outline-none focus:border-[#34888D]/70"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery('');
                setSearchResults(null);
              }}
              className="absolute right-2.5 top-2 text-[#949494] hover:text-white text-xs"
            >
              ✕
            </button>
          )}
        </form>

        {/* Type Filter */}
        <div className="flex items-center space-x-1.5">
          {['all', 'preference', 'fact', 'episodic', 'semantic'].map((type) => (
            <button
              key={type}
              onClick={() => {
                setSelectedType(type);
                setSearchResults(null);
              }}
              className={`px-3 py-1 rounded-[11px] text-xs font-medium capitalize transition-all ${
                selectedType === type
                  ? 'bg-[#016A71]/20 text-[#34888D] border border-[#016A71]/50'
                  : 'bg-[#171615] border border-[#2a2928] text-[#949494] hover:text-white'
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {/* Memory Cards Grid */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading || isSearching ? (
          <div className="flex flex-col items-center justify-center p-12 text-[#949494] text-xs space-y-2">
            <Loader2 className="w-5 h-5 animate-spin text-[#34888D]" />
            <span>Scanning PostgreSQL Memory Bank...</span>
          </div>
        ) : displayedMemories.length === 0 ? (
          <div className="text-center p-12 max-w-sm mx-auto space-y-3">
            <Brain className="w-10 h-10 text-[#949494]/40 mx-auto" />
            <h4 className="text-sm font-semibold text-white">No memories found</h4>
            <p className="text-xs text-[#949494]">
              Aetherius automatically learns facts and preferences during conversations, or you can add them manually.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {displayedMemories.map((mem) => (
              <div
                key={mem.id}
                className="p-4 rounded-[11px] bg-[#171615] border border-[#2a2928] hover:border-[#34888D]/60 transition-all flex flex-col justify-between space-y-3 group"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-[11px] font-mono uppercase font-semibold ${
                        mem.memory_type === 'preference'
                          ? 'bg-[#016A71]/20 text-[#34888D] border border-[#016A71]/35'
                          : mem.memory_type === 'fact'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-[#34888D]/15 text-[#34888D] border border-[#34888D]/30'
                      }`}
                    >
                      {mem.memory_type}
                    </span>

                    <div className="flex items-center space-x-2">
                      {mem.similarity_score !== undefined && (
                        <span className="text-[10px] text-[#34888D] font-mono">
                          {(mem.similarity_score * 100).toFixed(0)}% match
                        </span>
                      )}
                      <button
                        onClick={() => handleDeleteMemory(mem.id)}
                        className="opacity-0 group-hover:opacity-100 p-1 text-[#949494] hover:text-rose-400 rounded transition-opacity"
                        title="Delete Memory"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <p className="text-xs text-white leading-relaxed">{mem.content}</p>
                </div>

                <div className="border-t border-[#2a2928] pt-2.5 flex items-center justify-between text-[10px] text-[#949494] font-mono">
                  <div className="flex items-center space-x-1">
                    <Star className="w-3 h-3 text-amber-400" />
                    <span>Weight {mem.importance_weight}</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Eye className="w-3 h-3" />
                    <span>Accessed {mem.access_count}x</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Memory Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-[#171615] border border-[#2a2928] rounded-[11px] max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-white tracking-tight">Add Long-Term Memory</h3>
            <form onSubmit={handleCreateMemory} className="space-y-3">
              <div>
                <label className="text-xs font-medium text-[#949494] block mb-1">
                  Memory Type
                </label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                  className="w-full bg-[#201f1e] border border-[#2a2928] rounded-[11px] px-3 py-2 text-xs text-white focus:outline-none focus:border-[#34888D]/70"
                >
                  <option value="preference" className="bg-[#171615] text-white">User Preference (Coding style, language, etc.)</option>
                  <option value="fact" className="bg-[#171615] text-white">Project / System Fact</option>
                  <option value="episodic" className="bg-[#171615] text-white">Episodic Milestone</option>
                  <option value="semantic" className="bg-[#171615] text-white">Domain Knowledge Standard</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-[#949494] block mb-1">
                  Memory Content
                </label>
                <textarea
                  rows={3}
                  required
                  placeholder="e.g. Always write PostgreSQL migrations with strict rollback steps..."
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  className="w-full bg-[#201f1e] border border-[#2a2928] rounded-[11px] px-3 py-2 text-xs text-white placeholder-[#949494] focus:outline-none focus:border-[#34888D]/70 resize-none"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-[#949494] block mb-1">
                  Importance Weight: {newImportance.toFixed(1)}
                </label>
                <input
                  type="range"
                  min={1.0}
                  max={5.0}
                  step={0.5}
                  value={newImportance}
                  onChange={(e) => setNewImportance(parseFloat(e.target.value))}
                  className="w-full accent-[#016A71]"
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3.5 py-1.5 rounded-[11px] bg-[#222120] hover:bg-[#2c2b2a] text-[#949494] hover:text-white text-xs font-medium transition-colors border border-[#2a2928]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-[11px] bg-[#016A71] hover:bg-[#01575d] text-white text-xs font-semibold shadow-[0_0_12px_rgba(1,106,113,0.3)] transition-all"
                >
                  Save to PostgreSQL
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
