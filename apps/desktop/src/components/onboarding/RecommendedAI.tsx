import React, { useState, useEffect } from 'react';
import {
  ModelResponse,
  ModelPackageResponse,
  HardwareProfile,
  HuggingFaceModelCard,
  HuggingFaceDatasetCard,
} from '../../types';
import { api } from '../../services/api';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';
import {
  Sparkles,
  Check,
  Download,
  Box,
  Code2,
  Brain,
  Zap,
  Cloud,
  RefreshCw,
  Search,
  Database,
  Globe,
  CheckCircle2,
  Flame,
} from 'lucide-react';

interface RecommendedAIProps {
  models: ModelResponse[];
  packages: ModelPackageResponse[];
  profile: HardwareProfile | null;
  onToggleInstall: (modelId: string) => Promise<void>;
  onNext: () => void;
  onBack: () => void;
}

export const RecommendedAI: React.FC<RecommendedAIProps> = ({
  models,
  packages,
  profile,
  onToggleInstall,
  onNext,
  onBack,
}) => {
  const [selectedTab, setSelectedTab] = useState<'packages' | 'models' | 'hf_hub' | 'datasets'>('packages');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [installingPkgId, setInstallingPkgId] = useState<string | null>(null);

  // Daily Open-Source Hub Data
  const [hfModels, setHfModels] = useState<HuggingFaceModelCard[]>([]);
  const [hfDatasets, setHfDatasets] = useState<HuggingFaceDatasetCard[]>([]);
  const [isLoadingFeed, setIsLoadingFeed] = useState<boolean>(false);
  const [isSyncingDaily, setIsSyncingDaily] = useState<boolean>(false);
  const [lastSyncedTime, setLastSyncedTime] = useState<string>('Today (Live)');
  const [syncNotice, setSyncNotice] = useState<string | null>(null);

  useEffect(() => {
    loadDailyCatalog();
  }, []);

  const loadDailyCatalog = async () => {
    setIsLoadingFeed(true);
    try {
      const feed = await api.getDailyFeed();
      if (feed) {
        setHfModels(feed.models || []);
        setHfDatasets(feed.datasets || []);
        if (feed.last_updated) {
          const date = new Date(feed.last_updated);
          setLastSyncedTime(date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        }
      }
    } catch (err) {
      console.debug('Failed to load daily open-source feed:', err);
    } finally {
      setIsLoadingFeed(false);
    }
  };

  const handleSyncDaily = async () => {
    setIsSyncingDaily(true);
    try {
      const res = await api.syncDailyModels();
      setSyncNotice(`Synced ${res.models_count} open-source models and ${res.datasets_count} datasets!`);
      await loadDailyCatalog();
      setTimeout(() => setSyncNotice(null), 4000);
    } catch (err) {
      console.error('Failed to sync daily open-source catalog:', err);
    } finally {
      setIsSyncingDaily(false);
    }
  };

  const handleInstall = async (modelId: string) => {
    try {
      setInstallingId(modelId);
      await onToggleInstall(modelId);
    } finally {
      setInstallingId(null);
    }
  };

  const handleInstallPackage = async (pkg: ModelPackageResponse) => {
    try {
      setInstallingPkgId(pkg.id);
      for (const modelId of pkg.recommended_model_ids) {
        const target = models.find((m) => m.id === modelId || m.name === modelId);
        if (target && !target.is_installed) {
          await onToggleInstall(target.id);
        }
      }
    } finally {
      setInstallingPkgId(null);
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'Coding':
        return <Code2 className="w-4 h-4 text-emerald-400" />;
      case 'Reasoning':
        return <Brain className="w-4 h-4 text-purple-400" />;
      case 'Fast':
        return <Zap className="w-4 h-4 text-amber-400" />;
      case 'Image Generation':
        return <Flame className="w-4 h-4 text-rose-400" />;
      default:
        return <Sparkles className="w-4 h-4 text-[#34888D]" />;
    }
  };

  // Filter local models
  const filteredLocalModels = models.filter((m) => {
    const matchesCat = categoryFilter === 'all' || m.category?.toLowerCase() === categoryFilter.toLowerCase();
    const matchesSearch =
      !searchQuery.trim() ||
      m.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (m.description && m.description.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesCat && matchesSearch;
  });

  // Filter HF models
  const filteredHfModels = hfModels.filter((m) => {
    const matchesCat = categoryFilter === 'all' || m.category?.toLowerCase() === categoryFilter.toLowerCase();
    const matchesSearch =
      !searchQuery.trim() ||
      m.model_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.repo_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (m.description && m.description.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesCat && matchesSearch;
  });

  // Filter Datasets
  const filteredDatasets = hfDatasets.filter((d) => {
    const matchesSearch =
      !searchQuery.trim() ||
      d.dataset_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      d.repo_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (d.description && d.description.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (d.category && d.category.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesSearch;
  });

  // Filter Packages
  const filteredPackages = packages.filter((pkg) => {
    return (
      !searchQuery.trim() ||
      pkg.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      pkg.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      pkg.target_audience.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  return (
    <div className="h-full w-full overflow-y-auto flex flex-col items-center px-4 md:px-6 py-6 md:py-8 bg-[#000000] relative">
      <div className="max-w-5xl w-full space-y-6 animate-in fade-in duration-300 pb-20">
        
        {/* Header Section */}
        <div className="text-center space-y-3">
          <div className="flex flex-wrap items-center justify-center gap-2">
            <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-[11px] bg-[#016A71]/20 border border-[#016A71]/40 text-[#34888D] text-xs font-medium">
              <Sparkles className="w-3.5 h-3.5 text-[#34888D]" />
              <span>Hardware Matched ({profile?.ram.total_gb ?? 16} GB RAM • {profile?.vram_gb ?? 0} GB VRAM)</span>
            </div>
            <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-[11px] bg-[#222120] border border-[#2e2d2c] text-[#a0a0a0] text-xs font-mono">
              <Globe className="w-3.5 h-3.5 text-emerald-400" />
              <span>Daily Hub Sync: {lastSyncedTime}</span>
              <button
                onClick={handleSyncDaily}
                disabled={isSyncingDaily}
                className="hover:text-white transition-colors ml-1 p-0.5"
                title="Check for newly released models & versions"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isSyncingDaily ? 'animate-spin text-[#34888D]' : ''}`} />
              </button>
            </div>
          </div>

          <h2 className="text-3xl font-bold tracking-tight text-white">
            Recommended AI for Your System
          </h2>
          <p className="text-sm text-[#949494] max-w-2xl mx-auto">
            Explore hardware-optimized Ollama engines, daily released Hugging Face open-source weights, curated multi-model packages, and open datasets.
          </p>

          {syncNotice && (
            <div className="p-2.5 rounded-[12px] bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-xs font-medium flex items-center justify-center gap-2 max-w-lg mx-auto animate-in fade-in">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>{syncNotice}</span>
            </div>
          )}

          {/* Navigation Mode Tabs */}
          <div className="flex flex-wrap justify-center gap-2 pt-2">
            <button
              onClick={() => { setSelectedTab('packages'); setCategoryFilter('all'); }}
              className={`px-4 py-2 rounded-[11px] text-xs font-medium flex items-center gap-2 transition-all ${
                selectedTab === 'packages'
                  ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                  : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
              }`}
            >
              <Box className="w-3.5 h-3.5" />
              <span>Curated AI Packages ({packages.length})</span>
            </button>
            <button
              onClick={() => { setSelectedTab('models'); setCategoryFilter('all'); }}
              className={`px-4 py-2 rounded-[11px] text-xs font-medium flex items-center gap-2 transition-all ${
                selectedTab === 'models'
                  ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                  : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
              }`}
            >
              <Zap className="w-3.5 h-3.5" />
              <span>Local Ollama Models ({models.length})</span>
            </button>
            <button
              onClick={() => { setSelectedTab('hf_hub'); setCategoryFilter('all'); }}
              className={`px-4 py-2 rounded-[11px] text-xs font-medium flex items-center gap-2 transition-all ${
                selectedTab === 'hf_hub'
                  ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                  : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
              }`}
            >
              <Globe className="w-3.5 h-3.5 text-amber-400" />
              <span>Hugging Face GGUF Hub ({hfModels.length})</span>
            </button>
            <button
              onClick={() => { setSelectedTab('datasets'); setCategoryFilter('all'); }}
              className={`px-4 py-2 rounded-[11px] text-xs font-medium flex items-center gap-2 transition-all ${
                selectedTab === 'datasets'
                  ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                  : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
              }`}
            >
              <Database className="w-3.5 h-3.5 text-cyan-400" />
              <span>Open-Source Datasets ({hfDatasets.length})</span>
            </button>
          </div>

          {/* Search & Category Filter Bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 max-w-4xl mx-auto">
            <div className="relative w-full sm:w-72">
              <Search className="w-4 h-4 text-[#666] absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search models, packages, datasets..."
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-[11px] bg-[#141312] border border-[#2a2928] text-white placeholder-[#666] focus:outline-none focus:border-[#34888D]"
              />
            </div>

            {(selectedTab === 'models' || selectedTab === 'hf_hub') && (
              <div className="flex flex-wrap gap-1.5">
                {['all', 'Reasoning', 'Coding', 'Fast', 'Image Generation', 'General'].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setCategoryFilter(cat)}
                    className={`px-3 py-1 text-[11px] font-medium rounded-[8px] transition-colors ${
                      categoryFilter.toLowerCase() === cat.toLowerCase()
                        ? 'bg-[#34888D]/20 text-[#34888D] border border-[#34888D]/50'
                        : 'bg-[#171615] text-[#888] hover:text-white border border-[#2a2928]'
                    }`}
                  >
                    {cat === 'all' ? 'All Categories' : cat}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Tab 1: Curated Packages */}
        {selectedTab === 'packages' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredPackages.map((pkg) => {
              const isPkgInstalled = pkg.recommended_model_ids.every((mid) => {
                const m = models.find((mod) => mod.id === mid || mod.name === mid);
                return m ? m.is_installed : false;
              });

              return (
                <Card
                  key={pkg.id}
                  className="flex flex-col justify-between space-y-4 hover:border-[#34888D]/50 transition-all bg-[#121110] border-[#222120]"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="p-2.5 rounded-[12px] bg-[#016A71]/20 border border-[#016A71]/40 text-[#34888D]">
                          <Box className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-white">{pkg.name}</div>
                          <div className="text-xs text-[#34888D]">{pkg.target_audience}</div>
                        </div>
                      </div>
                      <Badge variant="blue" size="sm">
                        Curated Suite
                      </Badge>
                    </div>

                    <p className="text-xs text-[#949494] leading-relaxed">{pkg.description}</p>

                    <div className="p-3 rounded-[12px] bg-black/50 border border-[#222120] text-xs space-y-2">
                      <div className="text-[#888] font-medium text-[11px] flex items-center justify-between">
                        <span>Bundled Model Components:</span>
                        <span className="font-mono text-white">Min {pkg.required_ram_gb} GB RAM</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {pkg.recommended_model_ids.map((mid, idx) => {
                          const m = models.find((mod) => mod.id === mid || mod.name === mid);
                          return (
                            <span
                              key={idx}
                              className={`px-2.5 py-0.5 rounded-[8px] font-mono text-[11px] flex items-center gap-1.5 ${
                                m?.is_installed
                                  ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-800/50'
                                  : 'bg-[#1c1b1a] text-[#aaa] border border-[#2a2928]'
                              }`}
                            >
                              {m?.is_installed ? (
                                <Check className="w-3 h-3 text-emerald-400" />
                              ) : (
                                <Download className="w-3 h-3 text-[#666]" />
                              )}
                              <span>{mid}</span>
                            </span>
                          );
                        })}
                      </div>
                      <div className="flex justify-between text-[11px] text-[#777] pt-1 border-t border-[#222120]">
                        <span>Est. Disk Footprint: ~{pkg.estimated_storage_gb} GB</span>
                        <span className="text-[#34888D]">1-Click Sequential Setup</span>
                      </div>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-[#222120] flex justify-end">
                    <Button
                      size="sm"
                      variant={isPkgInstalled ? 'outline' : 'primary'}
                      onClick={() => handleInstallPackage(pkg)}
                      isLoading={installingPkgId === pkg.id}
                      className="min-w-40"
                    >
                      {isPkgInstalled ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Package Installed</span>
                        </>
                      ) : (
                        <>
                          <Download className="w-3.5 h-3.5" />
                          <span>Install Entire Suite</span>
                        </>
                      )}
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        )}

        {/* Tab 2: Individual Local Ollama Models */}
        {selectedTab === 'models' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredLocalModels.map((model) => {
              const isInstalled = model.is_installed;

              return (
                <Card
                  key={model.id}
                  className="flex flex-col justify-between space-y-4 hover:border-[#34888D]/60 transition-colors bg-[#121110] border-[#222120]"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="p-2 rounded-[11px] bg-[#1c1b1a] border border-[#2a2928]">
                          {getCategoryIcon(model.category)}
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-white flex items-center gap-2">
                            {model.display_name}
                            {!model.is_local && (
                              <Badge variant="blue" size="sm">
                                <Cloud className="w-3 h-3" /> Cloud
                              </Badge>
                            )}
                          </div>
                          <div className="text-xs text-[#949494] font-mono">
                            {model.parameters_b > 0 ? `${model.parameters_b}B Params` : 'Cloud API'} •{' '}
                            {model.quantization}
                          </div>
                        </div>
                      </div>

                      {model.compatibility && (
                        <Badge
                          variant={
                            model.compatibility.compatibility === 'Compatible'
                              ? 'success'
                              : model.compatibility.compatibility === 'Maybe Compatible'
                              ? 'warning'
                              : 'danger'
                          }
                          size="sm"
                        >
                          {model.compatibility.compatibility}
                        </Badge>
                      )}
                    </div>

                    <p className="text-xs text-[#949494] line-clamp-2 leading-relaxed">
                      {model.description}
                    </p>

                    {/* Compatibility metrics */}
                    {model.compatibility && (
                      <div className="p-3 rounded-[11px] bg-black/40 border border-[#222120] text-[11px] space-y-1.5 text-[#949494]">
                        <div className="flex justify-between">
                          <span>Est. Memory Footprint:</span>
                          <span className="text-white font-medium font-mono">
                            {model.compatibility.estimated_memory_gb} GB
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Recommended Engine:</span>
                          <span className="text-white font-medium">
                            {model.compatibility.recommended_execution}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Performance Tier:</span>
                          <span className="text-[#34888D] font-medium">
                            {model.compatibility.performance_tier}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-[#222120]">
                    <span className="text-xs text-[#949494]">
                      {model.is_local ? 'Local Offline Ollama' : 'Cloud Hybrid API'}
                    </span>
                    <Button
                      size="sm"
                      variant={isInstalled ? 'outline' : 'primary'}
                      onClick={() => handleInstall(model.id)}
                      isLoading={installingId === model.id}
                      className="min-w-28"
                    >
                      {isInstalled ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Ready</span>
                        </>
                      ) : (
                        <>
                          <Download className="w-3.5 h-3.5" />
                          <span>Install</span>
                        </>
                      )}
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        )}

        {/* Tab 3: Hugging Face GGUF Hub */}
        {selectedTab === 'hf_hub' && (
          isLoadingFeed ? (
            <div className="p-12 text-center text-xs text-[#949494] flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-[#34888D]" />
              <span>Fetching daily open-source GGUF releases...</span>
            </div>
          ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredHfModels.map((hf) => {
              const isInstalled = models.some(
                (m) => (m.name.includes(hf.model_name.toLowerCase()) || m.name === hf.ollama_pull_tag) && m.is_installed
              );

              return (
                <Card
                  key={hf.repo_id}
                  className="flex flex-col justify-between space-y-4 hover:border-amber-500/50 transition-all bg-[#121110] border-[#222120]"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="p-2 rounded-[11px] bg-amber-950/20 border border-amber-800/40 text-amber-400">
                          {getCategoryIcon(hf.category)}
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-white">{hf.model_name}</div>
                          <div className="text-xs text-[#888] font-mono">{hf.repo_id}</div>
                        </div>
                      </div>
                      <Badge variant="warning" size="sm">
                        {hf.category}
                      </Badge>
                    </div>

                    <p className="text-xs text-[#949494] line-clamp-2 leading-relaxed">{hf.description}</p>

                    {hf.benchmark_highlight && (
                      <div className="px-3 py-1.5 rounded-[8px] bg-amber-950/30 border border-amber-800/40 text-[11px] text-amber-300 font-medium">
                        ⭐ {hf.benchmark_highlight}
                      </div>
                    )}

                    <div className="p-3 rounded-[11px] bg-black/40 border border-[#222120] text-[11px] space-y-1 text-[#949494]">
                      <div className="flex justify-between">
                        <span>Downloads / Community:</span>
                        <span className="text-white font-mono">{hf.downloads.toLocaleString()} downloads • {hf.likes} likes</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Est. Download Size:</span>
                        <span className="text-white font-mono">~{hf.estimated_size_gb} GB ({hf.recommended_quantization})</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Ollama Native Tag:</span>
                        <span className="text-[#34888D] font-mono text-[10px] truncate max-w-[200px]">{hf.ollama_pull_tag}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-[#222120]">
                    <span className="text-xs text-amber-400/80 font-mono">Open-Source GGUF</span>
                    <Button
                      size="sm"
                      variant={isInstalled ? 'outline' : 'primary'}
                      onClick={() => handleInstall(hf.ollama_pull_tag)}
                      isLoading={installingId === hf.ollama_pull_tag}
                      className="min-w-28"
                    >
                      {isInstalled ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Installed</span>
                        </>
                      ) : (
                        <>
                          <Download className="w-3.5 h-3.5" />
                          <span>Pull GGUF</span>
                        </>
                      )}
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
          )
        )}

        {/* Tab 4: Open-Source Datasets */}
        {selectedTab === 'datasets' && (
          isLoadingFeed ? (
            <div className="p-12 text-center text-xs text-[#949494] flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-[#34888D]" />
              <span>Fetching open-source datasets...</span>
            </div>
          ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredDatasets.map((dataset) => (
              <Card
                key={dataset.repo_id}
                className="flex flex-col justify-between space-y-4 hover:border-cyan-500/50 transition-all bg-[#121110] border-[#222120]"
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-[11px] bg-cyan-950/20 border border-cyan-800/40 text-cyan-400">
                        <Database className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-white">{dataset.dataset_name}</div>
                        <div className="text-xs text-[#888] font-mono">{dataset.repo_id}</div>
                      </div>
                    </div>
                    <Badge variant="blue" size="sm">
                      {dataset.category}
                    </Badge>
                  </div>

                  <p className="text-xs text-[#949494] line-clamp-2 leading-relaxed">{dataset.description}</p>

                  <div className="p-3 rounded-[11px] bg-black/40 border border-[#222120] text-[11px] space-y-1.5 text-[#949494]">
                    <div className="flex justify-between">
                      <span>Hub Downloads:</span>
                      <span className="text-white font-mono">{dataset.downloads.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Community Likes:</span>
                      <span className="text-white font-mono">{dataset.likes.toLocaleString()}</span>
                    </div>
                    <div className="flex flex-wrap gap-1 pt-1">
                      {dataset.tags.slice(0, 4).map((tag, idx) => (
                        <span key={idx} className="px-2 py-0.5 rounded-[6px] bg-[#1c1b1a] text-[#888] text-[10px] border border-[#2a2928]">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-[#222120]">
                  <span className="text-xs text-cyan-400/80 font-mono">Hugging Face Dataset</span>
                  <a
                    href={`https://huggingface.co/datasets/${dataset.repo_id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] bg-[#1a1918] hover:bg-[#252423] text-white text-xs font-medium border border-[#2e2d2c] transition-colors"
                  >
                    <span>View on Hub</span>
                    <Globe className="w-3 h-3 text-[#34888D]" />
                  </a>
                </div>
              </Card>
            ))}
          </div>
          )
        )}


        {/* Navigation Actions */}
        <div className="flex justify-between pt-6 border-t border-[#222120] pb-12">
          <Button variant="ghost" onClick={onBack}>
            ← Back to Hardware
          </Button>
          <Button size="lg" onClick={onNext} className="w-56 shadow-[0_0_16px_rgba(1,106,113,0.3)]">
            Choose Workspace →
          </Button>
        </div>
      </div>
    </div>
  );
};
