import React, { useState } from 'react';
import { ModelResponse, ModelPackageResponse, HardwareProfile } from '../../types';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';
import { Sparkles, Check, Download, Box, Code2, Brain, Zap, Cloud } from 'lucide-react';

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
  const [selectedTab, setSelectedTab] = useState<'models' | 'packages'>('models');
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [installingPkgId, setInstallingPkgId] = useState<string | null>(null);

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
      default:
        return <Sparkles className="w-4 h-4 text-indigo-400" />;
    }
  };

  return (
    <div className="h-full w-full overflow-y-auto flex flex-col items-center px-4 md:px-6 py-6 md:py-8 bg-[#000000] relative">
      <div className="max-w-4xl w-full space-y-6 animate-in fade-in duration-300 pb-20">
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-[11px] bg-[#016A71]/20 border border-[#016A71]/40 text-[#34888D] text-xs font-medium">
            <Sparkles className="w-3.5 h-3.5 text-[#34888D]" />
            <span>Compatibility Engine Recommendation</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-white">
            Recommended AI for Your System
          </h2>
          <p className="text-sm text-[#949494] max-w-xl mx-auto">
            Based on your <span className="text-white font-semibold">{profile?.ram.total_gb ?? 16} GB RAM</span> and{' '}
            <span className="text-white font-semibold">{profile?.vram_gb ?? 0} GB VRAM</span>, these models offer optimal speed and precision.
          </p>

          {/* Mode Tabs */}
          <div className="flex justify-center gap-2 pt-2">
            <button
              onClick={() => setSelectedTab('models')}
              className={`px-4 py-1.5 rounded-[11px] text-xs font-medium transition-all ${
                selectedTab === 'models'
                  ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                  : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
              }`}
            >
              Individual Models
            </button>
            <button
              onClick={() => setSelectedTab('packages')}
              className={`px-4 py-1.5 rounded-[11px] text-xs font-medium transition-all ${
                selectedTab === 'packages'
                  ? 'bg-[#016A71] text-white shadow-[0_0_12px_rgba(1,106,113,0.3)]'
                  : 'bg-[#171615] text-[#949494] hover:text-white border border-[#2a2928]'
              }`}
            >
              Curated Packages
            </button>
          </div>
        </div>

        {/* Tab 1: Individual Models */}
        {selectedTab === 'models' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {models.map((model) => {
              const isInstalled = model.is_installed;

              return (
                <Card
                  key={model.id}
                  className="flex flex-col justify-between space-y-4 hover:border-[#34888D]/60 transition-colors"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <div className="p-2 rounded-[11px] bg-[#222120] border border-[#2a2928]">
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

                    <p className="text-xs text-[#949494] line-clamp-2">
                      {model.description}
                    </p>

                    {/* Compatibility metrics */}
                    {model.compatibility && (
                      <div className="p-3 rounded-[11px] bg-black/40 border border-[#2a2928] text-[11px] space-y-1 text-[#949494]">
                        <div className="flex justify-between">
                          <span>Est. Memory Footprint:</span>
                          <span className="text-white font-medium font-mono">
                            {model.compatibility.estimated_memory_gb} GB
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Execution Mode:</span>
                          <span className="text-white font-medium">
                            {model.compatibility.recommended_execution}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Performance:</span>
                          <span className="text-[#34888D] font-medium">
                            {model.compatibility.performance_tier}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center justify-between pt-2 border-t border-[#2a2928]">
                    <span className="text-xs text-[#949494]">
                      {model.is_local ? 'One-Click Runtime' : 'API Ready'}
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

        {/* Tab 2: Curated Packages */}
        {selectedTab === 'packages' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {packages.map((pkg) => {
              const isPkgInstalled = pkg.recommended_model_ids.every((mid) => {
                const m = models.find((mod) => mod.id === mid || mod.name === mid);
                return m ? m.is_installed : false;
              });

              return (
                <Card key={pkg.id} className="flex flex-col justify-between space-y-4">
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <div className="p-2 rounded-[11px] bg-[#016A71]/20 border border-[#016A71]/40">
                        <Box className="w-4 h-4 text-[#34888D]" />
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-white">{pkg.name}</div>
                        <div className="text-xs text-[#949494]">{pkg.target_audience}</div>
                      </div>
                    </div>

                    <p className="text-xs text-[#949494]">{pkg.description}</p>

                    <div className="p-3 rounded-[11px] bg-black/40 border border-[#2a2928] text-xs space-y-1.5">
                      <div className="text-[#949494] font-medium">Bundled Models:</div>
                      <div className="flex flex-wrap gap-1.5">
                        {pkg.recommended_model_ids.map((mid, idx) => {
                          const m = models.find((mod) => mod.id === mid || mod.name === mid);
                          return (
                            <span
                              key={idx}
                              className={`px-2.5 py-0.5 rounded-[11px] font-mono text-[11px] flex items-center gap-1 ${
                                m?.is_installed
                                  ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-800/50'
                                  : 'bg-[#222120] text-[#949494] border border-[#2a2928]'
                              }`}
                            >
                              {m?.is_installed && <Check className="w-3 h-3 text-emerald-400" />}
                              <span>{mid}</span>
                            </span>
                          );
                        })}
                      </div>
                      <div className="flex justify-between text-[11px] text-[#949494] pt-1">
                        <span>Est. Storage: ~{pkg.estimated_storage_gb} GB</span>
                        <span>Min RAM: {pkg.required_ram_gb} GB</span>
                      </div>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-[#2a2928] flex justify-end">
                    <Button
                      size="sm"
                      variant={isPkgInstalled ? 'outline' : 'primary'}
                      onClick={() => handleInstallPackage(pkg)}
                      isLoading={installingPkgId === pkg.id}
                      className="min-w-36"
                    >
                      {isPkgInstalled ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Package Ready</span>
                        </>
                      ) : (
                        <>
                          <Download className="w-3.5 h-3.5" />
                          <span>Install Package</span>
                        </>
                      )}
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        )}

        {/* Navigation Actions */}
        <div className="flex justify-between pt-6 border-t border-[#2a2928] pb-12">
          <Button variant="ghost" onClick={onBack}>
            ← Back to System
          </Button>
          <Button size="lg" onClick={onNext} className="w-56 shadow-[0_0_16px_rgba(1,106,113,0.3)]">
            Choose Workspace →
          </Button>
        </div>
      </div>
    </div>
  );
};
