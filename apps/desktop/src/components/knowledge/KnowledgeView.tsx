import React, { useState, useEffect, useRef } from 'react';
import {
  KnowledgeBaseResponse,
  WorkspaceResponse,
  RAGSearchResult,
  HuggingFaceDatasetCard,
} from '../../types';
import { api } from '../../services/api';
import {
  UploadCloud,
  FileText,
  Plus,
  Trash2,
  Search,
  AlertTriangle,
  Loader2,
  Sparkles,
  Globe,
  Download,
  HardDrive,
} from 'lucide-react';

interface KnowledgeViewProps {
  activeWorkspace: WorkspaceResponse | null;
}

export const KnowledgeView: React.FC<KnowledgeViewProps> = ({ activeWorkspace }) => {
  const [activeTab, setActiveTab] = useState<'collections' | 'hf_datasets' | 'search_test'>('collections');
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseResponse[]>([]);
  const [selectedKBSlug, setSelectedKBSlug] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);

  // Hugging Face Datasets State
  const [hfDatasets, setHfDatasets] = useState<HuggingFaceDatasetCard[]>([]);
  const [hfDatasetQuery, setHfDatasetQuery] = useState<string>('');
  const [isLoadingHfDatasets, setIsLoadingHfDatasets] = useState<boolean>(false);
  const [ingestingRepoId, setIngestingRepoId] = useState<string | null>(null);

  // New Collection Form State
  const [newKBName, setNewKBName] = useState<string>('');
  const [newKBSlug, setNewKBSlug] = useState<string>('');
  const [newKBType, setNewKBType] = useState<string>('Company');
  const [newKBDesc, setNewKBDesc] = useState<string>('');

  // Semantic Vector Search Playground State
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchResult, setSearchResult] = useState<RAGSearchResult | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadKnowledgeBases();
  }, [activeWorkspace?.slug]);

  useEffect(() => {
    if (activeTab === 'hf_datasets') {
      loadHfDatasets();
    }
  }, [activeTab]);

  const loadKnowledgeBases = async () => {
    try {
      const kbs = await api.getKnowledgeBases(activeWorkspace?.slug || 'general');
      setKnowledgeBases(kbs);
      if (kbs.length > 0 && !selectedKBSlug) {
        setSelectedKBSlug(kbs[0].slug);
      }
    } catch (err) {
      console.error('Failed to load knowledge bases:', err);
    }
  };

  const loadHfDatasets = async (query?: string) => {
    setIsLoadingHfDatasets(true);
    try {
      const datasets = await api.getHFDatasets(query || hfDatasetQuery);
      setHfDatasets(datasets);
    } catch (err) {
      console.error('Failed to fetch Hugging Face datasets:', err);
    } finally {
      setIsLoadingHfDatasets(false);
    }
  };

  const handleHfSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadHfDatasets(hfDatasetQuery);
  };

  const handleIngestHfDataset = async (dataset: HuggingFaceDatasetCard) => {
    try {
      setIngestingRepoId(dataset.repo_id);
      await api.importHFDataset(
        dataset.repo_id,
        activeWorkspace?.slug || 'general',
        `Dataset: ${dataset.dataset_name}`
      );
      await loadKnowledgeBases();
      setActiveTab('collections');
    } catch (err: any) {
      alert(`Error importing dataset: ${err.message}`);
    } finally {
      setIngestingRepoId(null);
    }
  };

  const activeKB = knowledgeBases.find((k) => k.slug === selectedKBSlug) || knowledgeBases[0] || null;

  const handleCreateCollection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKBName.trim()) return;

    const slug = (newKBSlug || newKBName).toLowerCase().replace(/[^a-z0-9]+/g, '-');
    try {
      const created = await api.createKnowledgeBase({
        name: newKBName,
        slug: slug,
        collection_type: newKBType,
        description: newKBDesc,
        workspace_slug: activeWorkspace?.slug || 'general',
      });
      setKnowledgeBases((prev) => [...prev, created]);
      setSelectedKBSlug(created.slug);
      setShowCreateModal(false);
      setNewKBName('');
      setNewKBSlug('');
      setNewKBDesc('');
    } catch (err: any) {
      alert(`Error creating collection: ${err.message}`);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !activeKB) return;

    const file = files[0];
    setIsUploading(true);
    setUploadError(null);

    try {
      await api.uploadDocument(activeKB.slug, file);
      await loadKnowledgeBases();
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload document');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeleteDocument = async (docId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.deleteDocument(docId);
      await loadKnowledgeBases();
    } catch (err) {
      console.error('Failed to delete document:', err);
    }
  };

  const handleTestSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      const res = await api.searchKnowledge({
        query: searchQuery,
        workspace_slug: activeWorkspace?.slug || 'general',
        knowledge_base_slugs: selectedKBSlug ? [selectedKBSlug] : undefined,
        top_k: 4,
      });
      setSearchResult(res);
    } catch (err) {
      console.error('Semantic search failed:', err);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6 animate-in fade-in duration-150">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-white tracking-tight">Knowledge Base & Datasets</h2>
            <span className="text-[10px] px-2.5 py-0.5 rounded-[8px] bg-[#016A71]/20 border border-[#016A71]/40 text-[#34888D] font-mono">
              pgvector RAG
            </span>
          </div>
          <p className="text-xs text-[#949494] mt-0.5">
            Indexed company documents and Hugging Face open datasets for{' '}
            <strong className="text-white capitalize">{activeWorkspace?.name || 'General'}</strong> workspace.
          </p>
        </div>

        {/* View Tabs */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('collections')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-[11px] text-xs font-semibold transition-all ${
              activeTab === 'collections'
                ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
            }`}
          >
            <HardDrive className="w-3.5 h-3.5" />
            <span>Document Collections</span>
          </button>

          <button
            onClick={() => setActiveTab('hf_datasets')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-[11px] text-xs font-semibold transition-all ${
              activeTab === 'hf_datasets'
                ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
            }`}
          >
            <Globe className="w-3.5 h-3.5 text-[#34888D]" />
            <span>Hugging Face Datasets 🌐</span>
          </button>

          <button
            onClick={() => setActiveTab('search_test')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-[11px] text-xs font-semibold transition-all ${
              activeTab === 'search_test'
                ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>RAG Query Sandbox</span>
          </button>
        </div>
      </div>

      {/* VIEW 1: Document Collections (Company Data) */}
      {activeTab === 'collections' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Collection List */}
          <div className="lg:col-span-1 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#949494] uppercase tracking-wider">
                Collections ({knowledgeBases.length})
              </span>
              <button
                onClick={() => setShowCreateModal(true)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-[8px] bg-[#016A71] hover:bg-[#01575d] text-white text-xs font-medium transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>New</span>
              </button>
            </div>

            <div className="space-y-2">
              {knowledgeBases.length === 0 ? (
                <div className="p-6 rounded-[11px] bg-[#171615] border border-[#2a2928] text-center text-xs text-[#949494]">
                  No collections yet. Create one or import a Hugging Face dataset!
                </div>
              ) : (
                knowledgeBases.map((kb) => {
                  const isSelected = kb.slug === selectedKBSlug;
                  return (
                    <div
                      key={kb.id}
                      onClick={() => setSelectedKBSlug(kb.slug)}
                      className={`p-3.5 rounded-[11px] cursor-pointer transition-all border ${
                        isSelected
                          ? 'bg-[#171615] border-[#016A71]/60 shadow-[0_0_12px_rgba(1,106,113,0.2)] text-white'
                          : 'bg-[#171615]/70 border-[#2a2928] text-[#949494] hover:border-[#34888D]/40 hover:text-white'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-xs text-white truncate">{kb.name}</span>
                        <span className="text-[10px] px-2 py-0.5 rounded-[6px] bg-black/40 text-[#34888D] font-mono">
                          {kb.collection_type}
                        </span>
                      </div>
                      <p className="text-[11px] text-[#949494] line-clamp-2 leading-relaxed">
                        {kb.description || 'No description provided.'}
                      </p>
                      <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#2a2928]/60 text-[10px] text-[#949494]">
                        <span>{kb.document_count} files</span>
                        <span className="font-mono">{kb.total_chunks} chunks</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Right Column: Files & Upload Area */}
          <div className="lg:col-span-2 space-y-4">
            {activeKB ? (
              <div className="p-5 rounded-[12px] bg-[#171615] border border-[#2a2928] space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#2a2928] pb-3">
                  <div>
                    <h3 className="text-base font-bold text-white tracking-tight">{activeKB.name}</h3>
                    <p className="text-xs text-[#949494]">{activeKB.description}</p>
                  </div>

                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.docx,.doc,.txt,.md,.csv,.json,.py,.ts"
                    className="hidden"
                    onChange={handleFileUpload}
                  />

                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                    className="flex items-center justify-center gap-2 px-4 py-2 rounded-[11px] bg-[#016A71] hover:bg-[#01575d] text-white text-xs font-semibold transition-all shadow-[0_0_12px_rgba(1,106,113,0.3)] disabled:opacity-50"
                  >
                    {isUploading ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Indexing Vectors...</span>
                      </>
                    ) : (
                      <>
                        <UploadCloud className="w-4 h-4" />
                        <span>Upload Files / Spreadsheets</span>
                      </>
                    )}
                  </button>
                </div>

                {uploadError && (
                  <div className="p-3 rounded-[11px] bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>{uploadError}</span>
                  </div>
                )}

                {/* Document List */}
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-[#949494] uppercase tracking-wider block">
                    Indexed Documents ({activeKB.documents?.length || 0})
                  </span>

                  {!activeKB.documents || activeKB.documents.length === 0 ? (
                    <div className="p-8 rounded-[11px] bg-black/40 border border-[#2a2928] text-center text-xs text-[#949494] space-y-2">
                      <FileText className="w-8 h-8 text-[#34888D]/40 mx-auto" />
                      <p>No documents uploaded in this collection yet.</p>
                      <p className="text-[11px] text-[#949494]/70">
                        Upload PDF, Word, CSV, Spreadsheets, JSON, or code files to index them for AI queries.
                      </p>
                    </div>
                  ) : (
                    activeKB.documents.map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center justify-between p-3 rounded-[11px] bg-black/30 border border-[#2a2928] hover:border-[#34888D]/40 transition-colors"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <FileText className="w-4 h-4 text-[#34888D] flex-shrink-0" />
                          <div className="min-w-0">
                            <span className="font-medium text-xs text-white truncate block">{doc.filename}</span>
                            <span className="text-[10px] text-[#949494] font-mono">
                              {(doc.file_size_bytes / 1024).toFixed(1)} KB • {doc.chunk_count} vector chunks
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-[10px] px-2 py-0.5 rounded-[6px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            Ready
                          </span>
                          <button
                            onClick={(e) => handleDeleteDocument(doc.id, e)}
                            className="p-1.5 rounded-[7px] text-[#949494] hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                            title="Delete Document"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ) : (
              <div className="p-12 rounded-[12px] bg-[#171615] border border-[#2a2928] text-center text-xs text-[#949494]">
                Select or create a collection to manage documents.
              </div>
            )}
          </div>
        </div>
      )}

      {/* VIEW 2: Hugging Face Datasets Hub */}
      {activeTab === 'hf_datasets' && (
        <div className="space-y-4">
          <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
            <form onSubmit={handleHfSearchSubmit} className="relative w-full md:w-96">
              <Search className="w-4 h-4 text-[#949494] absolute left-3 top-2.5" />
              <input
                type="text"
                value={hfDatasetQuery}
                onChange={(e) => setHfDatasetQuery(e.target.value)}
                placeholder="Search Hugging Face datasets (e.g. sales, finance, code)..."
                className="w-full bg-[#171615] border border-[#2a2928] rounded-[11px] pl-9 pr-20 py-2 text-xs text-white placeholder-[#949494] focus:outline-none focus:border-[#34888D]/70"
              />
              <button
                type="submit"
                className="absolute right-2 top-1.5 px-2.5 py-1 rounded-[8px] bg-[#016A71] hover:bg-[#01575d] text-white text-[11px] font-medium transition-colors"
              >
                Search
              </button>
            </form>

            <span className="text-xs text-[#949494]">
              Over 150,000+ public datasets ready for 1-click vector ingestion into PostgreSQL
            </span>
          </div>

          {isLoadingHfDatasets ? (
            <div className="py-16 text-center text-xs text-[#949494] flex flex-col items-center justify-center gap-2">
              <Loader2 className="w-5 h-5 text-[#34888D] animate-spin" />
              <span>Fetching datasets from Hugging Face...</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {hfDatasets.map((ds) => {
                const isIngesting = ingestingRepoId === ds.repo_id;
                return (
                  <div
                    key={ds.repo_id}
                    className="p-4 rounded-[12px] bg-[#171615] border border-[#2a2928] hover:border-[#34888D]/50 transition-all flex flex-col justify-between space-y-3"
                  >
                    <div className="space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h4 className="text-sm font-semibold text-white leading-tight">
                            {ds.dataset_name}
                          </h4>
                          <span className="text-[11px] text-[#949494] font-mono">
                            {ds.author} • {ds.category}
                          </span>
                        </div>
                        <span className="text-[10px] px-2 py-0.5 rounded-[6px] bg-[#016A71]/20 text-[#34888D] font-mono">
                          HF Dataset
                        </span>
                      </div>

                      <p className="text-xs text-zinc-300 line-clamp-2 leading-relaxed">
                        {ds.description}
                      </p>

                      {/* Tags */}
                      {ds.tags && ds.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 pt-1">
                          {ds.tags.slice(0, 4).map((tag, tIdx) => (
                            <span
                              key={tIdx}
                              className="text-[10px] px-2 py-0.5 rounded-[6px] bg-black/40 text-[#949494] font-mono"
                            >
                              #{tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-[#2a2928]/80 text-xs">
                      <span className="text-[11px] text-[#949494] font-mono">
                        ↓ {ds.downloads.toLocaleString()} downloads • ♥ {ds.likes.toLocaleString()}
                      </span>

                      <button
                        onClick={() => handleIngestHfDataset(ds)}
                        disabled={isIngesting}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-[9px] bg-[#016A71] hover:bg-[#01575d] text-white text-xs font-medium transition-all shadow-[0_0_10px_rgba(1,106,113,0.25)] disabled:opacity-50"
                      >
                        {isIngesting ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            <span>Ingesting Vectors...</span>
                          </>
                        ) : (
                          <>
                            <Download className="w-3.5 h-3.5" />
                            <span>Ingest to Workspace</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* VIEW 3: Semantic Vector Search Playground */}
      {activeTab === 'search_test' && (
        <div className="space-y-4">
          <form onSubmit={handleTestSearch} className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Ask or test a semantic query against your pgvector database..."
              className="flex-1 bg-[#171615] border border-[#2a2928] rounded-[11px] px-4 py-2.5 text-xs text-white placeholder-[#949494] focus:outline-none focus:border-[#34888D]/70"
            />
            <button
              type="submit"
              disabled={isSearching}
              className="px-5 py-2.5 rounded-[11px] bg-[#016A71] hover:bg-[#01575d] text-white text-xs font-semibold transition-all shadow-[0_0_12px_rgba(1,106,113,0.3)] disabled:opacity-50 flex items-center gap-2"
            >
              {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              <span>Test Query</span>
            </button>
          </form>

          {searchResult && (
            <div className="space-y-3 pt-2">
              <div className="text-xs font-semibold text-[#949494]">
                Top Semantic Vector Matches ({searchResult.chunks.length})
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {searchResult.chunks.map((chunk, cIdx) => (
                  <div
                    key={cIdx}
                    className="p-4 rounded-[11px] bg-[#171615] border border-[#2a2928] space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-semibold text-white truncate">
                        {chunk.chunk_metadata?.filename || 'Document Chunk'}
                      </span>
                      <span className="text-[#34888D] font-mono">
                        {chunk.similarity_score ? `${(chunk.similarity_score * 100).toFixed(1)}%` : 'Match'}
                      </span>
                    </div>
                    <p className="text-zinc-300 leading-relaxed line-clamp-4 font-mono text-[11px] bg-black/40 p-2.5 rounded-[8px]">
                      {chunk.content}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Create Collection Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-4">
          <div className="bg-[#171615] border border-[#2a2928] rounded-[12px] p-6 max-w-md w-full shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-white tracking-tight">Create Knowledge Collection</h3>
            <form onSubmit={handleCreateCollection} className="space-y-3">
              <div>
                <label className="text-xs font-medium text-[#949494] block mb-1">Collection Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Sales Pipeline 2026, HR Policy"
                  value={newKBName}
                  onChange={(e) => setNewKBName(e.target.value)}
                  className="w-full bg-black/40 border border-[#2a2928] rounded-[9px] px-3 py-2 text-xs text-white focus:outline-none focus:border-[#34888D]/70"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-[#949494] block mb-1">Category / Type</label>
                <select
                  value={newKBType}
                  onChange={(e) => setNewKBType(e.target.value)}
                  className="w-full bg-black/40 border border-[#2a2928] rounded-[9px] px-3 py-2 text-xs text-white focus:outline-none focus:border-[#34888D]/70"
                >
                  <option value="Company">Company Data</option>
                  <option value="Sales">Sales & Clients</option>
                  <option value="Financial">Financial Reports</option>
                  <option value="Technical">Technical Docs & Code</option>
                  <option value="HR">HR & Team Policies</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-[#949494] block mb-1">Description</label>
                <textarea
                  rows={2}
                  placeholder="Brief description of what documents this collection contains..."
                  value={newKBDesc}
                  onChange={(e) => setNewKBDesc(e.target.value)}
                  className="w-full bg-black/40 border border-[#2a2928] rounded-[9px] px-3 py-2 text-xs text-white focus:outline-none focus:border-[#34888D]/70 resize-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-[10px] text-xs font-medium bg-[#222120] hover:bg-[#2c2b2a] text-[#949494] hover:text-white transition-colors border border-[#2a2928]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-[10px] text-xs font-semibold bg-[#016A71] hover:bg-[#01575d] text-white transition-all shadow-[0_0_12px_rgba(1,106,113,0.3)]"
                >
                  Create Collection
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
