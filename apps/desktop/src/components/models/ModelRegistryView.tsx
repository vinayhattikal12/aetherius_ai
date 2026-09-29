import React, { useState, useEffect, useRef } from 'react';
import {
  ModelResponse,
  ModelPackageResponse,
  HardwareProfile,
  HuggingFaceModelCard,
  ModelUpgradeSuggestion,
  ModelInstallProgress,
} from '../../types';
import { api } from '../../services/api';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { HardwareTelemetryCard } from '../hardware/HardwareTelemetryCard';
import {
  Download,
  Check,
  Sparkles,
  Cloud,
  Code2,
  Brain,
  Zap,
  Trash2,
  AlertTriangle,
  Globe,
  Search,
  ArrowUpRight,
  HardDrive,
  RefreshCw,
  Image as ImageIcon,
  Flame,
  CheckCircle2,
  X,
} from 'lucide-react';

interface ModelRegistryViewProps {
  models: ModelResponse[];
  packages: ModelPackageResponse[];
  profile: HardwareProfile | null;
  onToggleInstall?: (modelId: string) => Promise<void>;
  onInstall?: (modelId: string) => Promise<void>;
  onUninstall?: (modelId: string) => Promise<void>;
  onReloadModels?: () => Promise<void>;
}

export const ModelRegistryView: React.FC<ModelRegistryViewProps> = ({
  models,
  profile,
  onToggleInstall,
  onInstall,
  onUninstall,
  onReloadModels,
}) => {
  const [activeTab, setActiveTab] = useState<'installed_local' | 'huggingface_hub' | 'cloud'>('installed_local');
  const [localFilter, setLocalFilter] = useState<'all' | 'installed' | 'recommended'>('all');
  const [hfCategory, setHfCategory] = useState<string>('all');
  const [hfSearchQuery, setHfSearchQuery] = useState<string>('');
  const [hfModels, setHfModels] = useState<HuggingFaceModelCard[]>([]);
  const [upgradeSuggestions, setUpgradeSuggestions] = useState<ModelUpgradeSuggestion[]>([]);
  const [isLoadingHf, setIsLoadingHf] = useState<boolean>(false);
  const [deleteTargetModel, setDeleteTargetModel] = useState<ModelResponse | null>(null);
  const [isSwapping, setIsSwapping] = useState<string | null>(null);
  
  // Real-time Installation State Map: key -> ModelInstallProgress
  const [installProgressMap, setInstallProgressMap] = useState<Record<string, ModelInstallProgress>>({});
  const [recentSuccessBanner, setRecentSuccessBanner] = useState<string | null>(null);
  const streamUnsubscribes = useRef<Record<string, () => void>>({});

  useEffect(() => {
    loadUpgradeSuggestions();
    loadActiveInstalls();

    return () => {
      // Clean up all active SSE streams on unmount
      Object.values(streamUnsubscribes.current).forEach((unsub) => unsub());
    };
  }, []);

  useEffect(() => {
    if (activeTab === 'huggingface_hub') {
      loadHfModels();
    }
  }, [activeTab, hfCategory]);

  const loadActiveInstalls = async () => {
    try {
      const active = await api.getActiveModelInstalls();
      active.forEach((p) => {
        if (!p.is_completed) {
          trackLiveProgress(p.model_id, p.model_name);
        }
      });
    } catch (err) {
      console.debug('No active installs detected:', err);
    }
  };

  const loadUpgradeSuggestions = async () => {
    try {
      const list = await api.getModelUpgradeSuggestions();
      setUpgradeSuggestions(list);
    } catch (err) {
      console.warn('Failed to load upgrade suggestions:', err);
    }
  };

  const loadHfModels = async () => {
    setIsLoadingHf(true);
    try {
      if (hfSearchQuery.trim()) {
        const results = await api.searchHFModels(hfSearchQuery);
        setHfModels(results);
      } else {
        const trending = await api.getHFTrendingModels(hfCategory);
        setHfModels(trending);
      }
    } catch (err) {
      console.error('Failed to load Hugging Face models:', err);
    } finally {
      setIsLoadingHf(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadHfModels();
  };

  const trackLiveProgress = (targetId: string, displayName: string) => {
    // Unsubscribe existing if any
    if (streamUnsubscribes.current[targetId]) {
      streamUnsubscribes.current[targetId]();
    }

    const unsub = api.streamModelInstallProgress(targetId, {
      onProgress: (data) => {
        setInstallProgressMap((prev) => ({
          ...prev,
          [targetId]: data,
          [`hf.co/${targetId}`]: data,
        }));
      },
      onDone: async (data) => {
        setInstallProgressMap((prev) => ({
          ...prev,
          [targetId]: { ...data, progress_percent: 100, is_completed: true, status: 'completed' },
          [`hf.co/${targetId}`]: { ...data, progress_percent: 100, is_completed: true, status: 'completed' },
        }));

        setRecentSuccessBanner(`🎉 ${displayName} installed successfully and is ready for inference!`);
        setTimeout(() => setRecentSuccessBanner(null), 6000);

        if (onInstall) {
          await onInstall(targetId);
        } else if (onReloadModels) {
          await onReloadModels();
        }
        await loadUpgradeSuggestions();
      },
      onError: (err) => {
        console.warn('SSE stream error for', targetId, err);
      },
    });

    streamUnsubscribes.current[targetId] = unsub;
  };

  const handleInstallLocal = async (model: ModelResponse) => {
    const key = model.name;
    setInstallProgressMap((prev) => ({
      ...prev,
      [model.id]: {
        model_id: model.id,
        model_name: model.display_name,
        status: 'initializing',
        status_message: 'Starting local engine installation...',
        progress_percent: 10,
        is_completed: false,
      },
      [key]: {
        model_id: model.id,
        model_name: model.display_name,
        status: 'initializing',
        status_message: 'Starting local engine installation...',
        progress_percent: 10,
        is_completed: false,
      },
    }));

    trackLiveProgress(model.name, model.display_name);

    try {
      await api.installModel(model.id);
    } catch (err) {
      console.error('Failed to trigger install:', err);
    }
  };

  const handleInstallHfModel = async (hfModel: HuggingFaceModelCard) => {
    const key = hfModel.repo_id;
    setInstallProgressMap((prev) => ({
      ...prev,
      [key]: {
        model_id: key,
        model_name: hfModel.model_name,
        status: 'initializing',
        status_message: 'Allocating local disk buffer & contacting Hugging Face Hub...',
        progress_percent: 10,
        is_completed: false,
      },
      [`hf.co/${key}`]: {
        model_id: key,
        model_name: hfModel.model_name,
        status: 'initializing',
        status_message: 'Allocating local disk buffer & contacting Hugging Face Hub...',
        progress_percent: 10,
        is_completed: false,
      },
    }));

    trackLiveProgress(`hf.co/${key}`, hfModel.model_name);

    try {
      await api.installHFModel(hfModel.repo_id, hfModel.recommended_quantization);
    } catch (err) {
      console.error('Failed to start Hugging Face model install:', err);
    }
  };

  const handleSmartSwap = async (suggestion: ModelUpgradeSuggestion) => {
    try {
      setIsSwapping(suggestion.current_model_id);
      const targetTag = `hf.co/${suggestion.suggested_repo_id}`;
      
      setInstallProgressMap((prev) => ({
        ...prev,
        [suggestion.suggested_repo_id]: {
          model_id: suggestion.suggested_repo_id,
          model_name: suggestion.suggested_display_name,
          status: 'initializing',
          status_message: `Swapping ${suggestion.current_model_name} with ${suggestion.suggested_display_name}...`,
          progress_percent: 10,
          is_completed: false,
        },
      }));

      trackLiveProgress(targetTag, suggestion.suggested_display_name);
      await api.smartSwapModel(suggestion.current_model_id, suggestion.suggested_repo_id);
    } catch (err) {
      console.error('Smart swap failed:', err);
    } finally {
      setIsSwapping(null);
    }
  };

  const handleConfirmUninstall = async () => {
    if (!deleteTargetModel) return;
    try {
      if (onUninstall) {
        await onUninstall(deleteTargetModel.id);
      } else if (onToggleInstall) {
        await onToggleInstall(deleteTargetModel.id);
      }
      if (onReloadModels) {
        await onReloadModels();
      }
    } finally {
      setDeleteTargetModel(null);
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
        return <ImageIcon className="w-4 h-4 text-rose-400" />;
      default:
        return <Sparkles className="w-4 h-4 text-indigo-400" />;
    }
  };

  const filteredLocalModels = models.filter((m) => {
    if (activeTab === 'cloud') return !m.is_local;
    if (!m.is_local) return false;
    if (localFilter === 'installed') return m.is_installed;
    if (localFilter === 'recommended') return m.is_recommended;
    return true;
  });

  const freeStorageGb = profile?.storage?.free_gb ?? 45.0;

  // Active downloads count
  const activeInstallsList = Object.values(installProgressMap).filter(
    (p) => !p.is_completed && p.status !== 'failed' && p.progress_percent < 100
  );

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6 animate-in fade-in duration-150">
      {/* Telemetry Header */}
      <HardwareTelemetryCard profile={profile} />

      {/* Global Success Banner */}
      {recentSuccessBanner && (
        <div className="p-4 rounded-[12px] bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-medium flex items-center justify-between shadow-[0_0_20px_rgba(16,185,129,0.2)] animate-in slide-in-from-top-2">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span>{recentSuccessBanner}</span>
          </div>
          <button
            onClick={() => setRecentSuccessBanner(null)}
            className="p-1 hover:bg-emerald-500/20 rounded-md transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Active Global Download Tracker Tray */}
      {activeInstallsList.length > 0 && (
        <div className="p-4 rounded-[12px] bg-[#016A71]/15 border border-[#016A71]/40 space-y-2.5 shadow-[0_0_20px_rgba(1,106,113,0.2)] animate-in fade-in">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 text-white font-semibold">
              <RefreshCw className="w-3.5 h-3.5 text-[#34888D] animate-spin" />
              <span>Active Model Installation in Progress ({activeInstallsList.length})</span>
            </div>
            <span className="text-[11px] text-zinc-400 font-mono">Live Sync</span>
          </div>
          <div className="space-y-2">
            {activeInstallsList.map((inst, iIdx) => (
              <div key={iIdx} className="space-y-1">
                <div className="flex justify-between text-[11px] text-zinc-300">
                  <span className="font-semibold text-white truncate max-w-[300px]">{inst.model_name}</span>
                  <span className="font-mono text-[#34888D] font-bold">{Math.round(inst.progress_percent)}%</span>
                </div>
                <div className="w-full h-2 bg-black/60 rounded-full overflow-hidden border border-[#2a2928] p-0.5">
                  <div
                    className="h-full bg-gradient-to-r from-[#016A71] via-[#34888D] to-emerald-400 rounded-full transition-all duration-300"
                    style={{ width: `${Math.max(inst.progress_percent, 6)}%` }}
                  />
                </div>
                <p className="text-[10px] text-zinc-400 truncate">{inst.status_message}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Storage Awareness Bar */}
      <div className="flex items-center justify-between px-4 py-3 rounded-[11px] bg-[#171615] border border-[#2a2928] text-xs">
        <div className="flex items-center gap-2 text-[#949494]">
          <HardDrive className="w-4 h-4 text-[#34888D]" />
          <span>
            Free Disk Space: <strong className="text-white font-mono">{freeStorageGb.toFixed(1)} GB</strong>
          </span>
          {freeStorageGb < 15.0 && (
            <span className="text-amber-400 flex items-center gap-1 font-medium ml-2">
              <AlertTriangle className="w-3.5 h-3.5" /> Storage Low (&lt;15 GB)
            </span>
          )}
        </div>
        <div className="text-[11px] text-[#949494] hidden sm:block">
          Smart Guardrail: Recommending optimal quantizations (<span className="text-[#34888D] font-mono">Q4_K_M</span>) to prevent disk bloat
        </div>
      </div>

      {/* Smart Model Upgrade Advisor Banner */}
      {upgradeSuggestions.length > 0 && (
        <div className="space-y-3">
          {upgradeSuggestions.map((sug, sIdx) => {
            const swapProg = installProgressMap[sug.suggested_repo_id] || installProgressMap[`hf.co/${sug.suggested_repo_id}`];
            const isSwapInstalling = swapProg && !swapProg.is_completed && swapProg.status !== 'failed';

            return (
              <div
                key={sIdx}
                className="p-4 rounded-[12px] bg-[#016A71]/15 border border-[#016A71]/40 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-[0_0_20px_rgba(1,106,113,0.15)]"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-0.5 rounded-[8px] bg-[#016A71] text-white text-[10px] font-bold uppercase tracking-wider">
                      Smart Upgrade Advisor
                    </span>
                    <span className="text-xs font-semibold text-white truncate">
                      Superior Alternative Available for {sug.current_model_name}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-300 leading-relaxed">
                    {sug.reason} <strong className="text-emerald-400 font-semibold">{sug.benchmark_gain}</strong>.
                  </p>
                  <div className="flex items-center gap-3 text-[11px] text-[#949494] pt-0.5 font-mono">
                    <span>Fits VRAM: <strong className="text-emerald-400">{sug.vram_fit_status}</strong></span>
                    <span>•</span>
                    <span>Disk Delta: <strong className="text-white">{sug.estimated_disk_delta_gb > 0 ? `+${sug.estimated_disk_delta_gb}` : sug.estimated_disk_delta_gb} GB</strong></span>
                  </div>
                </div>

                <div className="flex-shrink-0 md:min-w-64">
                  {isSwapInstalling ? (
                    <div className="space-y-1 bg-black/40 p-2.5 rounded-[11px] border border-[#2a2928]">
                      <div className="flex justify-between text-[11px] text-zinc-300">
                        <span className="flex items-center gap-1 text-[#34888D]">
                          <RefreshCw className="w-3 h-3 animate-spin" />
                          <span>Swapping...</span>
                        </span>
                        <span className="font-mono text-white font-bold">{Math.round(swapProg.progress_percent)}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-black/60 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-[#016A71] to-emerald-400 rounded-full transition-all duration-300"
                          style={{ width: `${Math.max(swapProg.progress_percent, 8)}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-zinc-400 truncate">{swapProg.status_message}</p>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleSmartSwap(sug)}
                      disabled={isSwapping === sug.current_model_id}
                      className="w-full px-4 py-2 rounded-[11px] bg-[#016A71] hover:bg-[#01575d] text-white text-xs font-semibold shadow-md transition-all flex items-center justify-center gap-2 whitespace-nowrap active:scale-[0.98] disabled:opacity-50"
                    >
                      <ArrowUpRight className="w-4 h-4" />
                      <span>1-Click Smart Swap to {sug.suggested_display_name}</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Main Registry Navigation Tabs */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pt-2 border-t border-[#2a2928]">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('installed_local')}
            className={`flex items-center gap-2 px-4 py-2 rounded-[11px] text-xs font-semibold transition-all ${
              activeTab === 'installed_local'
                ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
            }`}
          >
            <HardDrive className="w-3.5 h-3.5" />
            <span>Local AI Engines</span>
          </button>

          <button
            onClick={() => setActiveTab('huggingface_hub')}
            className={`flex items-center gap-2 px-4 py-2 rounded-[11px] text-xs font-semibold transition-all ${
              activeTab === 'huggingface_hub'
                ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
            }`}
          >
            <Globe className="w-3.5 h-3.5 text-[#34888D]" />
            <span>Hugging Face Hub 🌐</span>
          </button>

          <button
            onClick={() => setActiveTab('cloud')}
            className={`flex items-center gap-2 px-4 py-2 rounded-[11px] text-xs font-semibold transition-all ${
              activeTab === 'cloud'
                ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
            }`}
          >
            <Cloud className="w-3.5 h-3.5" />
            <span>Cloud APIs</span>
          </button>
        </div>

        {/* Sub-filters depending on active tab */}
        {activeTab === 'installed_local' && (
          <div className="flex items-center gap-1.5 p-1 rounded-[11px] bg-[#171615] border border-[#2a2928] text-xs">
            {(['all', 'recommended', 'installed'] as const).map((sub) => (
              <button
                key={sub}
                onClick={() => setLocalFilter(sub)}
                className={`px-3 py-1 rounded-[9px] font-medium capitalize transition-all ${
                  localFilter === sub
                    ? 'bg-[#016A71] text-white shadow-sm'
                    : 'text-[#949494] hover:text-white'
                }`}
              >
                {sub}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Hugging Face Hub Explorer View */}
      {activeTab === 'huggingface_hub' && (
        <div className="space-y-4">
          {/* Search and Category Filters */}
          <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
            <form onSubmit={handleSearchSubmit} className="relative w-full md:w-96">
              <Search className="w-4 h-4 text-[#949494] absolute left-3 top-2.5" />
              <input
                type="text"
                value={hfSearchQuery}
                onChange={(e) => setHfSearchQuery(e.target.value)}
                placeholder="Search any Hugging Face model or GGUF repo..."
                className="w-full bg-[#171615] border border-[#2a2928] rounded-[11px] pl-9 pr-20 py-2 text-xs text-white placeholder-[#949494] focus:outline-none focus:border-[#34888D]/70"
              />
              <button
                type="submit"
                className="absolute right-2 top-1.5 px-2.5 py-1 rounded-[8px] bg-[#016A71] hover:bg-[#01575d] text-white text-[11px] font-medium transition-colors"
              >
                Search
              </button>
            </form>

            <div className="flex flex-wrap gap-1.5">
              {(['all', 'Coding', 'Reasoning', 'Fast', 'Image Generation'] as const).map((cat) => (
                <button
                  key={cat}
                  onClick={() => {
                    setHfCategory(cat);
                    setHfSearchQuery('');
                  }}
                  className={`px-3 py-1.5 rounded-[10px] text-xs font-medium transition-all ${
                    hfCategory.toLowerCase() === cat.toLowerCase() && !hfSearchQuery
                      ? 'bg-[#016A71] text-white'
                      : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
                  }`}
                >
                  {cat === 'all' ? 'All Trending' : cat}
                </button>
              ))}
            </div>
          </div>

          {/* Hugging Face Model Grid */}
          {isLoadingHf ? (
            <div className="py-16 text-center text-xs text-[#949494] flex flex-col items-center justify-center gap-2">
              <RefreshCw className="w-5 h-5 text-[#34888D] animate-spin" />
              <span>Fetching live models from Hugging Face Hub...</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {hfModels.map((hf) => {
                const compat = hf.compatibility;
                
                const prog =
                  installProgressMap[hf.repo_id] ||
                  installProgressMap[`hf.co/${hf.repo_id}`] ||
                  installProgressMap[hf.ollama_pull_tag];
                
                const isCurrentlyInstalling = prog && !prog.is_completed && prog.status !== 'failed' && prog.progress_percent < 100;

                const isInstalled =
                  !isCurrentlyInstalling &&
                  models.some(
                    (m) =>
                      m.is_installed &&
                      (m.name === hf.ollama_pull_tag ||
                        m.name === `hf.co/${hf.repo_id}` ||
                        m.name === hf.repo_id ||
                        m.name.toLowerCase().includes(hf.repo_id.toLowerCase()))
                  );

                return (
                  <Card
                    key={hf.repo_id}
                    className="flex flex-col justify-between space-y-3.5 hover:border-[#34888D]/60 transition-all duration-150"
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <div className="p-2 rounded-[11px] bg-[#222120] border border-[#2a2928] flex-shrink-0">
                            {getCategoryIcon(hf.category)}
                          </div>
                          <div className="min-w-0">
                            <h4 className="text-sm font-semibold text-white leading-tight truncate">
                              {hf.model_name}
                            </h4>
                            <div className="text-[11px] text-[#949494] font-mono mt-0.5 truncate">
                              {hf.author} • {hf.parameters_b}B
                            </div>
                          </div>
                        </div>

                        {compat && (
                          <Badge
                            variant={
                              compat.compatibility === 'Compatible'
                                ? 'success'
                                : compat.compatibility === 'Maybe Compatible'
                                ? 'warning'
                                : 'danger'
                            }
                            size="sm"
                          >
                            {compat.compatibility}
                          </Badge>
                        )}
                      </div>

                      <p className="text-xs text-[#949494] line-clamp-2 leading-relaxed">
                        {hf.description}
                      </p>

                      {/* Benchmark & Quantization Stats */}
                      <div className="p-2.5 rounded-[11px] bg-black/40 border border-[#2a2928] text-[11px] space-y-1.5">
                        {hf.benchmark_highlight && (
                          <div className="text-emerald-400 font-medium flex items-center gap-1.5 text-[11px]">
                            <Flame className="w-3.5 h-3.5 flex-shrink-0" />
                            <span className="truncate">{hf.benchmark_highlight}</span>
                          </div>
                        )}
                        <div className="flex justify-between text-[#949494]">
                          <span>Est. Disk Size:</span>
                          <span className="text-white font-mono font-medium">{hf.estimated_size_gb} GB</span>
                        </div>
                        <div className="flex justify-between text-[#949494]">
                          <span>Downloads / Likes:</span>
                          <span className="text-white font-mono font-medium flex items-center gap-2">
                            <span>↓ {hf.downloads.toLocaleString()}</span>
                            <span>♥ {hf.likes.toLocaleString()}</span>
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-[#2a2928]">
                      {isCurrentlyInstalling ? (
                        <div className="w-full space-y-1.5 py-1">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="text-[#34888D] font-mono font-medium flex items-center gap-1.5 truncate">
                              <RefreshCw className="w-3 h-3 animate-spin text-[#34888D] flex-shrink-0" />
                              <span className="truncate">{prog.status_message}</span>
                            </span>
                            <span className="text-white font-mono font-bold text-xs flex-shrink-0 ml-2">
                              {Math.round(prog.progress_percent)}%
                            </span>
                          </div>
                          <div className="w-full h-2 bg-black/60 rounded-full overflow-hidden border border-[#2a2928] p-0.5">
                            <div
                              className="h-full bg-gradient-to-r from-[#016A71] via-[#34888D] to-emerald-400 rounded-full transition-all duration-300"
                              style={{ width: `${Math.max(prog.progress_percent, 8)}%` }}
                            />
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] text-[#34888D] font-mono truncate max-w-[140px]">
                            {hf.recommended_quantization}
                          </span>

                          {isInstalled ? (
                            <span className="flex items-center gap-1 text-xs text-emerald-400 font-medium px-3 py-1 bg-emerald-500/10 rounded-[10px] border border-emerald-500/20">
                              <Check className="w-3.5 h-3.5 text-emerald-400" />
                              <span>Installed</span>
                            </span>
                          ) : (
                            <Button
                              size="sm"
                              variant="primary"
                              onClick={() => handleInstallHfModel(hf)}
                              className="min-w-24 text-xs font-semibold shadow-md active:scale-95 transition-all"
                            >
                              <Download className="w-3.5 h-3.5" />
                              <span>Install</span>
                            </Button>
                          )}
                        </div>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Local Installed Models Grid */}
      {activeTab !== 'huggingface_hub' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredLocalModels.map((model) => {
            const isInstalled = model.is_installed;
            const compat = model.compatibility;

            const prog = installProgressMap[model.id] || installProgressMap[model.name];
            const isCurrentlyInstalling = prog && !prog.is_completed && prog.status !== 'failed' && prog.progress_percent < 100;

            return (
              <Card
                key={model.id}
                className="flex flex-col justify-between space-y-3.5 hover:border-[#34888D]/60 transition-all duration-150"
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="p-2 rounded-[11px] bg-[#222120] border border-[#2a2928] flex-shrink-0">
                        {getCategoryIcon(model.category)}
                      </div>
                      <div className="min-w-0">
                        <h4 className="text-sm font-semibold text-white leading-tight truncate">
                          {model.display_name}
                        </h4>
                        <div className="text-[11px] text-[#949494] font-mono mt-0.5 truncate">
                          {model.provider} • {model.quantization}
                        </div>
                      </div>
                    </div>

                    {!model.is_local ? (
                      <Badge variant="blue" size="sm">
                        <Cloud className="w-3 h-3" /> Cloud
                      </Badge>
                    ) : compat ? (
                      <Badge
                        variant={
                          compat.compatibility === 'Compatible'
                            ? 'success'
                            : compat.compatibility === 'Maybe Compatible'
                            ? 'warning'
                            : 'danger'
                        }
                        size="sm"
                      >
                        {compat.compatibility}
                      </Badge>
                    ) : null}
                  </div>

                  <p className="text-xs text-[#949494] line-clamp-2 leading-relaxed">{model.description}</p>

                  {compat && (
                    <div className="p-3 rounded-[11px] bg-black/40 border border-[#2a2928] text-[11px] space-y-1 text-[#949494]">
                      <div className="flex justify-between">
                        <span>Memory Footprint:</span>
                        <span className="text-white font-mono font-medium">
                          {compat.estimated_memory_gb} GB
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>Execution:</span>
                        <span className="text-white font-medium">{compat.recommended_execution}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Performance Tier:</span>
                        <span className="text-[#34888D] font-medium">{compat.performance_tier}</span>
                      </div>
                    </div>
                  )}
                </div>

                <div className="pt-2 border-t border-[#2a2928]">
                  {isCurrentlyInstalling ? (
                    <div className="w-full space-y-1.5 py-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-[#34888D] font-mono font-medium flex items-center gap-1.5 truncate">
                          <RefreshCw className="w-3 h-3 animate-spin text-[#34888D] flex-shrink-0" />
                          <span className="truncate">{prog.status_message}</span>
                        </span>
                        <span className="text-white font-mono font-bold text-xs flex-shrink-0 ml-2">
                          {Math.round(prog.progress_percent)}%
                        </span>
                      </div>
                      <div className="w-full h-2 bg-black/60 rounded-full overflow-hidden border border-[#2a2928] p-0.5">
                        <div
                          className="h-full bg-gradient-to-r from-[#016A71] via-[#34888D] to-emerald-400 rounded-full transition-all duration-300"
                          style={{ width: `${Math.max(prog.progress_percent, 8)}%` }}
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] text-[#949494] font-mono">
                        {model.context_size.toLocaleString()} Tokens
                      </span>

                      {isInstalled ? (
                        <div className="flex items-center space-x-1.5">
                          <span className="flex items-center space-x-1 text-xs text-emerald-400 font-medium px-2.5 py-1 bg-emerald-500/10 rounded-[11px] border border-emerald-500/20">
                            <Check className="w-3.5 h-3.5" />
                            <span>Ready</span>
                          </span>
                          {model.is_local && (
                            <button
                              onClick={() => setDeleteTargetModel(model)}
                              className="p-1.5 text-[#949494] hover:text-rose-400 hover:bg-rose-500/10 rounded-[11px] transition-colors"
                              title="Uninstall Model"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      ) : (
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => handleInstallLocal(model)}
                          className="min-w-24 text-xs font-semibold shadow-md active:scale-95 transition-all"
                        >
                          <Download className="w-3 h-3" />
                          <span>Install</span>
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Confirmation Modal Dialog for Uninstalling */}
      {deleteTargetModel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-4 animate-in fade-in duration-150">
          <div className="bg-[#171615] border border-[#2a2928] rounded-[11px] p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center space-x-3 text-rose-400">
              <div className="w-10 h-10 rounded-[11px] bg-rose-500/10 border border-rose-500/20 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-5 h-5 text-rose-400" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white tracking-tight">Uninstall Model?</h3>
                <p className="text-xs text-[#949494]">Remove model weights from disk</p>
              </div>
            </div>

            <p className="text-xs text-[#949494] bg-black/40 p-3 rounded-[11px] border border-[#2a2928] leading-relaxed">
              Are you sure you want to delete <strong className="text-white font-semibold">{deleteTargetModel.display_name}</strong>? This will delete the local GGUF weights to reclaim disk space. You can reinstall it anytime from the registry.
            </p>

            <div className="flex justify-end space-x-2.5 pt-2">
              <button
                onClick={() => setDeleteTargetModel(null)}
                className="px-4 py-2 rounded-[11px] text-xs font-medium bg-[#222120] hover:bg-[#2c2b2a] text-[#949494] hover:text-white transition-colors border border-[#2a2928]"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmUninstall}
                className="px-4 py-2 rounded-[11px] text-xs font-semibold bg-rose-700 hover:bg-rose-600 text-white transition-all flex items-center space-x-1.5 shadow-lg shadow-rose-950/40"
              >
                <span>Yes, Uninstall</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
