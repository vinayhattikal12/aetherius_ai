import React, { useState, useEffect, useRef } from 'react';
import {
  ModelResponse,
  ModelPackageResponse,
  HardwareProfile,
  HuggingFaceModelCard,
  HuggingFaceDatasetCard,
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
  CheckCircle2,
  X,
  Box,
  Database,
  KeyRound,
  Eye,
  EyeOff,
  Save,
} from 'lucide-react';

interface ModelRegistryViewProps {
  models: ModelResponse[];
  packages?: ModelPackageResponse[];
  profile: HardwareProfile | null;
  onToggleInstall?: (modelId: string) => Promise<void>;
  onInstall?: (modelId: string) => Promise<void>;
  onUninstall?: (modelId: string) => Promise<void>;
  onReloadModels?: () => Promise<void>;
}

export const ModelRegistryView: React.FC<ModelRegistryViewProps> = ({
  models,
  packages = [],
  profile,
  onToggleInstall,
  onInstall,
  onUninstall,
  onReloadModels,
}) => {
  const [activeTab, setActiveTab] = useState<'installed_local' | 'packages' | 'huggingface_hub' | 'datasets' | 'cloud'>('installed_local');
  const [localFilter, setLocalFilter] = useState<'all' | 'installed' | 'recommended'>('all');
  const [hfCategory, setHfCategory] = useState<string>('all');
  const [hfSearchQuery, setHfSearchQuery] = useState<string>('');
  const [datasetSearchQuery, setDatasetSearchQuery] = useState<string>('');
  const [hfModels, setHfModels] = useState<HuggingFaceModelCard[]>([]);
  const [hfDatasets, setHfDatasets] = useState<HuggingFaceDatasetCard[]>([]);
  const [upgradeSuggestions, setUpgradeSuggestions] = useState<ModelUpgradeSuggestion[]>([]);
  const [isLoadingHf, setIsLoadingHf] = useState<boolean>(false);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState<boolean>(false);
  const [isSyncingDaily, setIsSyncingDaily] = useState<boolean>(false);
  const [lastSyncedTime, setLastSyncedTime] = useState<string>('Today (Live)');
  const [deleteTargetModel, setDeleteTargetModel] = useState<ModelResponse | null>(null);
  const [isSwapping, setIsSwapping] = useState<string | null>(null);
  const [installingPkgId, setInstallingPkgId] = useState<string | null>(null);

  // Cloud API Keys Management State
  const [anthropicKey, setAnthropicKey] = useState<string>('');
  const [openaiKey, setOpenaiKey] = useState<string>('');
  const [groqKey, setGroqKey] = useState<string>('');
  const [hfToken, setHfToken] = useState<string>('');
  const [isSavingKeys, setIsSavingKeys] = useState<boolean>(false);
  const [keysSavedMessage, setKeysSavedMessage] = useState<string | null>(null);
  const [showKeys, setShowKeys] = useState<boolean>(false);

  // Real-time Installation State Map: key -> ModelInstallProgress
  const [installProgressMap, setInstallProgressMap] = useState<Record<string, ModelInstallProgress>>({});
  const [recentSuccessBanner, setRecentSuccessBanner] = useState<string | null>(null);
  const streamUnsubscribes = useRef<Record<string, () => void>>({});

  useEffect(() => {
    loadUpgradeSuggestions();
    loadActiveInstalls();
    loadSettingsKeys();
    loadDailyFeed();

    return () => {
      // Clean up all active SSE streams on unmount
      Object.values(streamUnsubscribes.current).forEach((unsub) => unsub());
    };
  }, []);

  const loadSettingsKeys = async () => {
    try {
      const s = await api.getSettings();
      if (s.custom_settings) {
        if (s.custom_settings.anthropic_api_key) setAnthropicKey(s.custom_settings.anthropic_api_key);
        if (s.custom_settings.openai_api_key) setOpenaiKey(s.custom_settings.openai_api_key);
        if (s.custom_settings.groq_api_key) setGroqKey(s.custom_settings.groq_api_key);
        if (s.custom_settings.hf_token) setHfToken(s.custom_settings.hf_token);
      }
    } catch (e) {
      console.debug('Failed to load settings keys:', e);
    }
  };

  const handleSaveApiKeys = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingKeys(true);
    try {
      await api.updateSettings({
        custom_settings: {
          anthropic_api_key: anthropicKey.trim(),
          openai_api_key: openaiKey.trim(),
          groq_api_key: groqKey.trim(),
          hf_token: hfToken.trim(),
        },
      });
      if (onReloadModels) {
        await onReloadModels();
      }
      setKeysSavedMessage('Cloud API Keys saved successfully! Configured cloud models are now ready for chat.');
      setTimeout(() => setKeysSavedMessage(null), 5000);
    } catch (err: any) {
      console.error('Failed to save API keys:', err);
    } finally {
      setIsSavingKeys(false);
    }
  };

  const loadDailyFeed = async () => {
    try {
      const feed = await api.getDailyFeed();
      if (feed) {
        if (feed.models && feed.models.length > 0) setHfModels(feed.models);
        if (feed.datasets && feed.datasets.length > 0) setHfDatasets(feed.datasets);
        if (feed.last_updated) {
          const d = new Date(feed.last_updated);
          setLastSyncedTime(d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        }
      }
    } catch (e) {
      console.debug('Failed to load daily feed:', e);
    }
  };

  const handleSyncDailyHub = async () => {
    setIsSyncingDaily(true);
    try {
      const res = await api.syncDailyModels();
      setRecentSuccessBanner(`🔄 Synced ${res.models_count} open-source models and ${res.datasets_count} datasets!`);
      setTimeout(() => setRecentSuccessBanner(null), 5000);
      await loadDailyFeed();
      if (onReloadModels) await onReloadModels();
    } catch (err) {
      console.error('Daily sync error:', err);
    } finally {
      setIsSyncingDaily(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'huggingface_hub') {
      loadHfModels();
    } else if (activeTab === 'datasets') {
      loadDatasets();
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

  const [hfLimit, setHfLimit] = useState<number>(36);
  const [datasetLimit, setDatasetLimit] = useState<number>(36);
  const [isLoadingMoreHf, setIsLoadingMoreHf] = useState<boolean>(false);
  const [isLoadingMoreDatasets, setIsLoadingMoreDatasets] = useState<boolean>(false);

  const formatNumber = (num: number): string => {
    if (!num) return '0';
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
    }
    if (num >= 1000) {
      return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
    }
    return num.toLocaleString();
  };

  const loadHfModels = async (limitToUse: number = 36) => {
    setIsLoadingHf(true);
    try {
      if (hfSearchQuery.trim()) {
        const results = await api.searchHFModels(hfSearchQuery, limitToUse);
        setHfModels(results);
      } else {
        const trending = await api.getHFTrendingModels(hfCategory, limitToUse);
        setHfModels(trending);
      }
    } catch (err) {
      console.error('Failed to load Hugging Face models:', err);
    } finally {
      setIsLoadingHf(false);
    }
  };

  const handleLoadMoreHf = async () => {
    const nextLimit = hfLimit + 36;
    setHfLimit(nextLimit);
    setIsLoadingMoreHf(true);
    try {
      if (hfSearchQuery.trim()) {
        const results = await api.searchHFModels(hfSearchQuery, nextLimit);
        setHfModels(results);
      } else {
        const trending = await api.getHFTrendingModels(hfCategory, nextLimit);
        setHfModels(trending);
      }
    } catch (err) {
      console.error('Failed to load more models:', err);
    } finally {
      setIsLoadingMoreHf(false);
    }
  };

  const loadDatasets = async (limitToUse: number = 36) => {
    setIsLoadingDatasets(true);
    try {
      const results = await api.getHFDatasets(datasetSearchQuery, limitToUse);
      setHfDatasets(results);
    } catch (err) {
      console.error('Failed to load datasets:', err);
    } finally {
      setIsLoadingDatasets(false);
    }
  };

  const handleLoadMoreDatasets = async () => {
    const nextLimit = datasetLimit + 36;
    setDatasetLimit(nextLimit);
    setIsLoadingMoreDatasets(true);
    try {
      const results = await api.getHFDatasets(datasetSearchQuery, nextLimit);
      setHfDatasets(results);
    } catch (err) {
      console.error('Failed to load more datasets:', err);
    } finally {
      setIsLoadingMoreDatasets(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setHfLimit(36);
    loadHfModels(36);
  };

  const handleDatasetSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setDatasetLimit(36);
    loadDatasets(36);
  };

  const trackLiveProgress = (targetId: string, displayName: string) => {
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

  const handleInstallPackage = async (pkg: ModelPackageResponse) => {
    try {
      setInstallingPkgId(pkg.id);
      for (const modelId of pkg.recommended_model_ids) {
        const target = models.find((m) => m.id === modelId || m.name === modelId);
        if (target && !target.is_installed) {
          await handleInstallLocal(target);
        }
      }
    } finally {
      setInstallingPkgId(null);
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
        return <Sparkles className="w-4 h-4 text-[#34888D]" />;
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
            {activeInstallsList.map((prog, idx) => (
              <div key={idx} className="p-3 bg-black/60 rounded-[10px] border border-[#2a2928] space-y-1.5">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold text-white truncate">{prog.model_name}</span>
                  <span className="font-mono text-[#34888D] font-bold text-xs">{Math.round(prog.progress_percent)}%</span>
                </div>
                <div className="w-full h-2 bg-[#222120] rounded-full overflow-hidden border border-[#2a2928]">
                  <div
                    className="h-full bg-gradient-to-r from-[#016A71] to-emerald-400 rounded-full transition-all duration-300"
                    style={{ width: `${Math.max(prog.progress_percent, 5)}%` }}
                  />
                </div>
                <div className="text-[11px] text-zinc-400 font-mono truncate">{prog.status_message}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Storage Awareness Bar with Daily Sync Trigger */}
      <div className="flex flex-col sm:flex-row items-center justify-between px-4 py-3 rounded-[11px] bg-[#171615] border border-[#2a2928] text-xs gap-3">
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
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-[#777] font-mono">Hub Feed: {lastSyncedTime}</span>
          <button
            onClick={handleSyncDailyHub}
            disabled={isSyncingDaily}
            className="px-2.5 py-1 rounded-[8px] bg-[#222120] hover:bg-[#2c2b2a] text-white text-[11px] font-medium border border-[#2e2d2c] flex items-center gap-1.5 transition-colors"
            title="Check open-source hub for new weights, GGUFs, and datasets"
          >
            <RefreshCw className={`w-3 h-3 text-[#34888D] ${isSyncingDaily ? 'animate-spin' : ''}`} />
            <span>Check for Daily Releases</span>
          </button>
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
                    <div className="w-full space-y-1">
                      <div className="flex justify-between text-[11px] font-mono text-zinc-300">
                        <span>Installing...</span>
                        <span className="text-[#34888D] font-bold">{Math.round(swapProg.progress_percent)}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-[#222120] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#016A71] rounded-full transition-all duration-300"
                          style={{ width: `${Math.max(swapProg.progress_percent, 5)}%` }}
                        />
                      </div>
                    </div>
                  ) : (
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => handleSmartSwap(sug)}
                      isLoading={isSwapping === sug.current_model_id}
                      className="w-full text-xs font-semibold"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Upgrade to {sug.suggested_display_name}</span>
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Main Tabs Navigation */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[#2a2928] pb-4">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setActiveTab('installed_local')}
            className={`flex items-center gap-2 px-4 py-2 rounded-[11px] text-xs font-semibold transition-all ${
              activeTab === 'installed_local'
                ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
            }`}
          >
            <HardDrive className="w-3.5 h-3.5" />
            <span>Local AI Engines ({models.filter(m => m.is_local).length})</span>
          </button>

          <button
            onClick={() => setActiveTab('packages')}
            className={`flex items-center gap-2 px-4 py-2 rounded-[11px] text-xs font-semibold transition-all ${
              activeTab === 'packages'
                ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
            }`}
          >
            <Box className="w-3.5 h-3.5 text-[#34888D]" />
            <span>Curated Packages ({packages.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('huggingface_hub')}
            className={`flex items-center gap-2 px-4 py-2 rounded-[11px] text-xs font-semibold transition-all ${
              activeTab === 'huggingface_hub'
                ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
            }`}
          >
            <Globe className="w-3.5 h-3.5 text-amber-400" />
            <span>Hugging Face Hub 🌐</span>
          </button>

          <button
            onClick={() => setActiveTab('datasets')}
            className={`flex items-center gap-2 px-4 py-2 rounded-[11px] text-xs font-semibold transition-all ${
              activeTab === 'datasets'
                ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
            }`}
          >
            <Database className="w-3.5 h-3.5 text-cyan-400" />
            <span>Open Datasets ({hfDatasets.length})</span>
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

        {/* Sub-filters for local tab */}
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

      {/* Tab 2: Curated Packages Grid */}
      {activeTab === 'packages' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {packages.map((pkg) => {
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
                        <span>Package Ready</span>
                      </>
                    ) : (
                      <>
                        <Download className="w-3.5 h-3.5" />
                        <span>Install Full Package</span>
                      </>
                    )}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Tab 3: Hugging Face Hub Explorer View */}
      {activeTab === 'huggingface_hub' && (
        <div className="space-y-4">
          <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
            <form onSubmit={handleSearchSubmit} className="relative w-full md:w-96">
              <Search className="w-4 h-4 text-[#949494] absolute left-3 top-2.5" />
              <input
                type="text"
                value={hfSearchQuery}
                onChange={(e) => setHfSearchQuery(e.target.value)}
                placeholder="Search all 500,000+ Hugging Face models (e.g. llama, deepseek, qwen, coder)..."
                className="w-full bg-[#171615] border border-[#2a2928] rounded-[11px] pl-9 pr-20 py-2 text-xs text-white placeholder-[#949494] focus:outline-none focus:border-[#34888D]/70"
              />
              <button
                type="submit"
                className="absolute right-2 top-1.5 px-2.5 py-1 rounded-[8px] bg-[#016A71] hover:bg-[#01575d] text-white text-[11px] font-medium transition-colors"
              >
                Search
              </button>
            </form>

            <div className="flex flex-wrap items-center gap-1.5">
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
                  {cat === 'all' ? 'All Hub Models' : cat}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-[#777] px-1">
            <span>
              Showing <strong className="text-zinc-200">{hfModels.length}</strong> open-weights models evaluated for your hardware
            </span>
            {hfSearchQuery && (
              <button
                onClick={() => {
                  setHfSearchQuery('');
                  loadHfModels(36);
                }}
                className="text-[#34888D] hover:underline"
              >
                Clear search filter
              </button>
            )}
          </div>

          {isLoadingHf ? (
            <div className="p-12 text-center text-xs text-[#949494] flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-[#34888D]" />
              <span>Querying Hugging Face Hub live API & calculating hardware fit...</span>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {hfModels.map((hf) => {
                  const isInstalled = models.some(
                    (m) => (m.name.includes(hf.model_name.toLowerCase()) || m.name === hf.ollama_pull_tag) && m.is_installed
                  );
                  const prog = installProgressMap[hf.repo_id] || installProgressMap[`hf.co/${hf.repo_id}`];
                  const isCurrentlyInstalling = prog && !prog.is_completed && prog.status !== 'failed';

                  return (
                    <Card
                      key={hf.repo_id}
                      className="h-full flex flex-col justify-between p-4 bg-[#121110] border-[#222120] hover:border-[#34888D]/50 transition-all rounded-[14px] shadow-sm hover:shadow-[0_4px_20px_rgba(0,0,0,0.4)]"
                    >
                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-2.5">
                          <div className="flex items-center gap-2.5 min-w-0 flex-1">
                            <div className="p-2 rounded-[10px] bg-[#1c1b1a] border border-[#2a2928] flex-shrink-0 text-white">
                              {getCategoryIcon(hf.category)}
                            </div>
                            <div className="min-w-0 flex-1">
                              <h4 className="text-xs font-semibold text-white truncate leading-tight" title={hf.model_name}>
                                {hf.model_name}
                              </h4>
                              <span className="text-[11px] text-[#888] font-mono truncate block" title={hf.repo_id}>
                                {hf.author}
                              </span>
                            </div>
                          </div>

                          {hf.compatibility && (
                            <Badge
                              variant={
                                hf.compatibility.compatibility === 'Compatible'
                                  ? 'success'
                                  : hf.compatibility.compatibility === 'Maybe Compatible'
                                  ? 'warning'
                                  : 'danger'
                              }
                              size="sm"
                              className="flex-shrink-0 text-[10px] font-medium px-2 py-0.5"
                            >
                              {hf.compatibility.compatibility}
                            </Badge>
                          )}
                        </div>

                        <p className="text-[11px] text-[#9a9998] line-clamp-2 leading-relaxed min-h-[32px]">
                          {hf.description || `${hf.category} open-source model by ${hf.author}.`}
                        </p>

                        {hf.benchmark_highlight && !hf.benchmark_highlight.toLowerCase().includes('trending on') && (
                          <div className="px-2.5 py-1 rounded-[7px] bg-amber-950/25 border border-amber-800/35 text-[10px] text-amber-300 font-medium truncate">
                            ⭐ {hf.benchmark_highlight}
                          </div>
                        )}

                        <div className="grid grid-cols-2 gap-1.5 p-2 rounded-[9px] bg-black/40 border border-[#222120] text-[11px]">
                          <div className="flex items-center justify-between text-[#888] px-1">
                            <span>Downloads:</span>
                            <span className="text-white font-mono font-medium">{formatNumber(hf.downloads)}</span>
                          </div>
                          <div className="flex items-center justify-between text-[#888] px-1">
                            <span>Likes:</span>
                            <span className="text-white font-mono font-medium">★ {formatNumber(hf.likes)}</span>
                          </div>
                          <div className="flex items-center justify-between text-[#888] px-1">
                            <span>Est. Size:</span>
                            <span className="text-white font-mono font-medium">~{hf.estimated_size_gb} GB</span>
                          </div>
                          <div className="flex items-center justify-between text-[#888] px-1">
                            <span>Format:</span>
                            <span className="text-[#34888D] font-mono font-medium">{hf.recommended_quantization}</span>
                          </div>
                        </div>
                      </div>

                      <div className="pt-3 mt-3 border-t border-[#222120]">
                        {isCurrentlyInstalling ? (
                          <div className="w-full space-y-1.5 py-0.5">
                            <div className="flex items-center justify-between text-[11px]">
                              <span className="text-[#34888D] font-mono truncate">{prog.status_message}</span>
                              <span className="text-white font-mono font-bold ml-2">{Math.round(prog.progress_percent)}%</span>
                            </div>
                            <div className="w-full h-1.5 bg-[#222120] rounded-full overflow-hidden">
                              <div
                                className="h-full bg-gradient-to-r from-[#016A71] to-emerald-400 rounded-full transition-all duration-300"
                                style={{ width: `${Math.max(prog.progress_percent, 5)}%` }}
                              />
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-center justify-between gap-2">
                            <a
                              href={`https://huggingface.co/${hf.repo_id}`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[11px] text-[#888] hover:text-white flex items-center gap-1 transition-colors flex-shrink-0"
                            >
                              <span>Hub Card</span>
                              <ArrowUpRight className="w-3 h-3 text-[#34888D]" />
                            </a>

                            {isInstalled ? (
                              <span className="flex items-center space-x-1 text-[11px] text-emerald-400 font-medium px-2.5 py-1 bg-emerald-500/10 rounded-[9px] border border-emerald-500/20">
                                <Check className="w-3.5 h-3.5" />
                                <span>Ready</span>
                              </span>
                            ) : (
                              <Button
                                size="sm"
                                variant="primary"
                                onClick={() => handleInstallHfModel(hf)}
                                className="min-w-24 text-xs font-semibold py-1 px-3"
                              >
                                <Download className="w-3 h-3" />
                                <span>1-Click Install</span>
                              </Button>
                            )}
                          </div>
                        )}
                      </div>
                    </Card>
                  );
                })}
              </div>

              <div className="flex justify-center pt-4 pb-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLoadMoreHf}
                  isLoading={isLoadingMoreHf}
                  className="px-6 py-2 text-xs font-semibold text-zinc-300 hover:text-white border-[#2e2d2c] hover:border-[#34888D]/60 bg-[#161514]"
                >
                  <RefreshCw className="w-3.5 h-3.5 mr-2" />
                  <span>Load More Models from Hugging Face</span>
                </Button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Tab 4: Open-Source Datasets View */}
      {activeTab === 'datasets' && (
        <div className="space-y-4">
          <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
            <form onSubmit={handleDatasetSearchSubmit} className="relative w-full md:w-96">
              <Search className="w-4 h-4 text-[#949494] absolute left-3 top-2.5" />
              <input
                type="text"
                value={datasetSearchQuery}
                onChange={(e) => setDatasetSearchQuery(e.target.value)}
                placeholder="Search datasets (e.g. fineweb, gsm8k, code, instruction)..."
                className="w-full bg-[#171615] border border-[#2a2928] rounded-[11px] pl-9 pr-20 py-2 text-xs text-white placeholder-[#949494] focus:outline-none focus:border-[#34888D]/70"
              />
              <button
                type="submit"
                className="absolute right-2 top-1.5 px-2.5 py-1 rounded-[8px] bg-[#016A71] hover:bg-[#01575d] text-white text-[11px] font-medium transition-colors"
              >
                Search
              </button>
            </form>
            <span className="text-xs text-[#777]">Open-source training & RAG datasets from Hugging Face</span>
          </div>

          <div className="flex items-center justify-between text-xs text-[#777] px-1">
            <span>
              Showing <strong className="text-zinc-200">{hfDatasets.length}</strong> open datasets
            </span>
            {datasetSearchQuery && (
              <button
                onClick={() => {
                  setDatasetSearchQuery('');
                  loadDatasets(36);
                }}
                className="text-cyan-400 hover:underline"
              >
                Clear search filter
              </button>
            )}
          </div>

          {isLoadingDatasets ? (
            <div className="p-12 text-center text-xs text-[#949494] flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-[#34888D]" />
              <span>Loading open datasets...</span>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {hfDatasets.map((dataset) => (
                  <Card
                    key={dataset.repo_id}
                    className="h-full flex flex-col justify-between p-4 bg-[#121110] border-[#222120] hover:border-cyan-500/40 transition-all rounded-[14px] shadow-sm"
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2.5 min-w-0 flex-1">
                          <div className="p-2 rounded-[10px] bg-cyan-950/20 border border-cyan-800/40 text-cyan-400 flex-shrink-0">
                            <Database className="w-4 h-4" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <h4 className="text-xs font-semibold text-white truncate leading-tight" title={dataset.dataset_name}>
                              {dataset.dataset_name}
                            </h4>
                            <span className="text-[11px] text-[#888] font-mono truncate block" title={dataset.repo_id}>
                              {dataset.author}
                            </span>
                          </div>
                        </div>
                        <Badge variant="blue" size="sm" className="text-[10px] px-2 py-0.5 flex-shrink-0">
                          Dataset
                        </Badge>
                      </div>

                      <p className="text-[11px] text-[#9a9998] line-clamp-2 leading-relaxed min-h-[32px]">
                        {dataset.description}
                      </p>

                      <div className="grid grid-cols-2 gap-1.5 p-2 rounded-[9px] bg-black/40 border border-[#222120] text-[11px]">
                        <div className="flex items-center justify-between text-[#888] px-1">
                          <span>Downloads:</span>
                          <span className="text-white font-mono font-medium">{formatNumber(dataset.downloads)}</span>
                        </div>
                        <div className="flex items-center justify-between text-[#888] px-1">
                          <span>Likes:</span>
                          <span className="text-white font-mono font-medium">★ {formatNumber(dataset.likes)}</span>
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-1 min-h-[22px]">
                        {dataset.tags.slice(0, 3).map((tag, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 rounded-[6px] bg-[#1c1b1a] text-[#888] text-[10px] border border-[#2a2928] truncate max-w-[140px]"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-3 mt-3 border-t border-[#222120]">
                      <span className="text-[11px] text-cyan-400/80 font-mono">Dataset Hub</span>
                      <a
                        href={`https://huggingface.co/datasets/${dataset.repo_id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[8px] bg-[#1a1918] hover:bg-[#252423] text-white text-[11px] font-medium border border-[#2e2d2c] transition-colors"
                      >
                        <span>View on Hub</span>
                        <ArrowUpRight className="w-3 h-3 text-[#34888D]" />
                      </a>
                    </div>
                  </Card>
                ))}
              </div>

              <div className="flex justify-center pt-4 pb-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLoadMoreDatasets}
                  isLoading={isLoadingMoreDatasets}
                  className="px-6 py-2 text-xs font-semibold text-zinc-300 hover:text-white border-[#2e2d2c] hover:border-cyan-500/60 bg-[#161514]"
                >
                  <RefreshCw className="w-3.5 h-3.5 mr-2" />
                  <span>Load More Datasets from Hugging Face</span>
                </Button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Cloud API Keys Management View */}
      {activeTab === 'cloud' && (
        <div className="space-y-6">
          <Card className="p-6 bg-[#161514] border-[#2a2928] space-y-5">
            <div className="flex items-center justify-between border-b border-[#2a2928] pb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-[12px] bg-[#016A71]/20 border border-[#016A71]/40 text-[#34888D]">
                  <KeyRound className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-white">Cloud Provider API Keys</h3>
                  <p className="text-xs text-[#949494]">
                    Cloud models will only activate when you paste and save your respective API key below.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowKeys(!showKeys)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] bg-[#222120] hover:bg-[#2a2928] text-xs text-[#949494] hover:text-white transition-colors border border-[#2e2d2c]"
              >
                {showKeys ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                <span>{showKeys ? 'Hide Keys' : 'Show Keys'}</span>
              </button>
            </div>

            {keysSavedMessage && (
              <div className="p-3 rounded-[10px] bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-xs font-medium flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>{keysSavedMessage}</span>
              </div>
            )}

            <form onSubmit={handleSaveApiKeys} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-white flex items-center justify-between">
                    <span>Anthropic API Key (Claude 3.7 Sonnet)</span>
                    {anthropicKey ? <span className="text-emerald-400 text-[10px] font-mono">● Active</span> : <span className="text-[#666] text-[10px]">Unconfigured</span>}
                  </label>
                  <input
                    type={showKeys ? 'text' : 'password'}
                    value={anthropicKey}
                    onChange={(e) => setAnthropicKey(e.target.value)}
                    placeholder="sk-ant-api03-..."
                    className="w-full bg-[#121110] border border-[#2a2928] rounded-[10px] px-3 py-2 text-xs text-white placeholder-[#555] font-mono focus:outline-none focus:border-[#34888D]"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-white flex items-center justify-between">
                    <span>OpenAI API Key (GPT-4o)</span>
                    {openaiKey ? <span className="text-emerald-400 text-[10px] font-mono">● Active</span> : <span className="text-[#666] text-[10px]">Unconfigured</span>}
                  </label>
                  <input
                    type={showKeys ? 'text' : 'password'}
                    value={openaiKey}
                    onChange={(e) => setOpenaiKey(e.target.value)}
                    placeholder="sk-..."
                    className="w-full bg-[#121110] border border-[#2a2928] rounded-[10px] px-3 py-2 text-xs text-white placeholder-[#555] font-mono focus:outline-none focus:border-[#34888D]"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-white flex items-center justify-between">
                    <span>Groq API Key (Ultra-Fast Llama)</span>
                    {groqKey ? <span className="text-emerald-400 text-[10px] font-mono">● Active</span> : <span className="text-[#666] text-[10px]">Unconfigured</span>}
                  </label>
                  <input
                    type={showKeys ? 'text' : 'password'}
                    value={groqKey}
                    onChange={(e) => setGroqKey(e.target.value)}
                    placeholder="gsk_..."
                    className="w-full bg-[#121110] border border-[#2a2928] rounded-[10px] px-3 py-2 text-xs text-white placeholder-[#555] font-mono focus:outline-none focus:border-[#34888D]"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-white flex items-center justify-between">
                    <span>Hugging Face Token (Gated Models)</span>
                    {hfToken ? <span className="text-emerald-400 text-[10px] font-mono">● Active</span> : <span className="text-[#666] text-[10px]">Optional</span>}
                  </label>
                  <input
                    type={showKeys ? 'text' : 'password'}
                    value={hfToken}
                    onChange={(e) => setHfToken(e.target.value)}
                    placeholder="hf_..."
                    className="w-full bg-[#121110] border border-[#2a2928] rounded-[10px] px-3 py-2 text-xs text-white placeholder-[#555] font-mono focus:outline-none focus:border-[#34888D]"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <Button
                  type="submit"
                  size="sm"
                  variant="primary"
                  isLoading={isSavingKeys}
                  className="px-5 text-xs font-semibold shadow-[0_0_12px_rgba(1,106,113,0.3)]"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>Save Cloud Configuration</span>
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Tab 1: Local AI Engines Grid */}
      {(activeTab === 'installed_local' || activeTab === 'cloud') && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredLocalModels.map((model) => {
            const isInstalled = model.is_installed;
            const compat = model.compatibility;
            const prog = installProgressMap[model.name] || installProgressMap[model.id];
            const isCurrentlyInstalling = prog && !prog.is_completed && prog.status !== 'failed';

            return (
              <Card
                key={model.id}
                className="flex flex-col justify-between space-y-4 hover:border-[#34888D]/60 transition-colors bg-[#121110] border-[#222120]"
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
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
                    {model.description}
                  </p>

                  {/* Hardware Sizing */}
                  {compat && (
                    <div className="p-2.5 rounded-[11px] bg-black/40 border border-[#222120] text-[11px] space-y-1 text-[#949494]">
                      <div className="flex justify-between">
                        <span>Est. Memory:</span>
                        <span className="text-white font-medium font-mono">
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

                <div className="pt-2 border-t border-[#222120]">
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
                      <div className="w-full h-2 bg-black/60 rounded-full overflow-hidden border border-[#222120] p-0.5">
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
