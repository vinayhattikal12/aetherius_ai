import React, { useEffect, useState } from 'react';
import { HardwareProfile } from '../../types';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Cpu, HardDrive, MemoryStick, Zap, CheckCircle2 } from 'lucide-react';

interface SystemAnalyzingProps {
  profile: HardwareProfile | null;
  isLoading: boolean;
  onNext: () => void;
  onRetry: () => void;
}

export const SystemAnalyzing: React.FC<SystemAnalyzingProps> = ({
  profile,
  isLoading,
  onNext,
  onRetry,
}) => {
  const [scanStep, setScanStep] = useState(0);

  useEffect(() => {
    if (isLoading) {
      setScanStep(0);
      const interval = setInterval(() => {
        setScanStep((prev) => (prev < 5 ? prev + 1 : prev));
      }, 500);
      return () => clearInterval(interval);
    } else {
      setScanStep(5);
    }
  }, [isLoading]);

  const getTierBadgeVariant = (tier: string) => {
    switch (tier) {
      case 'Ultra':
        return 'purple';
      case 'High':
        return 'success';
      case 'Medium':
        return 'blue';
      case 'Low':
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <div className="h-full w-full overflow-y-auto flex flex-col items-center px-4 md:px-6 py-6 md:py-8 bg-[#000000] relative">
      <div className="max-w-2xl w-full space-y-6 animate-in fade-in duration-300 pb-20">
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-[11px] bg-[#171615] border border-[#2a2928] text-[#949494] text-xs font-medium">
            <Zap className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span>Hardware Intelligence Engine</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-white">
            {isLoading || scanStep < 5
              ? 'Analyzing your system...'
              : !profile
              ? 'Analysis Failed'
              : 'System Profile Ready'}
          </h2>
          <p className="text-sm text-[#949494]">
            {isLoading || scanStep < 5 || profile
              ? 'Aetherius is benchmarking your CPU, memory, GPU, and acceleration to match optimal models.'
              : 'Ensure the Aetherius backend is running and try again.'}
          </p>
        </div>

        {/* Telemetry Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* CPU Card */}
          <div className="p-4 rounded-[11px] bg-[#171615] border border-[#2a2928] space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-white font-medium text-sm">
                <Cpu className="w-4 h-4 text-[#34888D]" />
                <span>Processor (CPU)</span>
              </div>
              {scanStep >= 1 ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 animate-in fade-in" />
              ) : (
                <span className="text-xs text-[#949494] animate-pulse">Scanning...</span>
              )}
            </div>
            <div className="text-base font-semibold text-white">
              {profile ? profile.cpu.model : 'Detecting CPU cores...'}
            </div>
            <div className="text-xs text-[#949494] flex items-center gap-3">
              <span>{profile?.cpu.physical_cores ?? '-'} Physical Cores</span>
              <span>•</span>
              <span>{profile?.cpu.logical_cores ?? '-'} Threads</span>
              <span>•</span>
              <span>{profile?.architecture ?? 'x64'}</span>
            </div>
          </div>

          {/* RAM Card */}
          <div className="p-4 rounded-[11px] bg-[#171615] border border-[#2a2928] space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-white font-medium text-sm">
                <MemoryStick className="w-4 h-4 text-[#34888D]" />
                <span>System Memory (RAM)</span>
              </div>
              {scanStep >= 2 ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 animate-in fade-in" />
              ) : (
                <span className="text-xs text-[#949494] animate-pulse">Scanning...</span>
              )}
            </div>
            <div className="text-base font-semibold text-white flex items-baseline gap-2">
              <span>{profile ? `${profile.ram.total_gb} GB` : 'Detecting RAM...'}</span>
              {profile && (
                <span className="text-xs text-[#949494] font-normal">
                  ({profile.ram.available_gb} GB available)
                </span>
              )}
            </div>
            <div className="w-full bg-black/40 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-[#016A71] h-full rounded-full transition-all duration-500"
                style={{ width: `${profile?.ram.percent_used ?? 0}%` }}
              />
            </div>
          </div>

          {/* GPU & VRAM Card */}
          <div className="p-4 rounded-[11px] bg-[#171615] border border-[#2a2928] space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-white font-medium text-sm">
                <Zap className="w-4 h-4 text-amber-400" />
                <span>Graphics & VRAM</span>
              </div>
              {scanStep >= 3 ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 animate-in fade-in" />
              ) : (
                <span className="text-xs text-[#949494] animate-pulse">Scanning...</span>
              )}
            </div>
            <div className="text-base font-semibold text-white truncate">
              {profile && profile.gpu.length > 0 ? profile.gpu[0].name : 'Detecting GPU...'}
            </div>
            <div className="text-xs text-[#949494] flex items-center gap-2">
              <span>VRAM: {profile?.vram_gb ?? 0} GB</span>
              <span>•</span>
              <span className={profile?.gpu.some((g) => g.cuda_supported) ? 'text-emerald-400' : 'text-[#949494]'}>
                {profile?.gpu.some((g) => g.cuda_supported) ? 'CUDA Enabled' : 'Integrated / DirectML'}
              </span>
            </div>
          </div>

          {/* Storage & OS Card */}
          <div className="p-4 rounded-[11px] bg-[#171615] border border-[#2a2928] space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-white font-medium text-sm">
                <HardDrive className="w-4 h-4 text-[#34888D]" />
                <span>Disk & Acceleration</span>
              </div>
              {scanStep >= 4 ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 animate-in fade-in" />
              ) : (
                <span className="text-xs text-[#949494] animate-pulse">Scanning...</span>
              )}
            </div>
            <div className="text-base font-semibold text-white">
              {profile ? `${profile.storage.free_gb} GB Free Space` : 'Detecting Storage...'}
            </div>
            <div className="text-xs text-[#949494] flex flex-wrap gap-1">
              {profile?.accelerators.map((acc, idx) => (
                <span key={idx} className="bg-[#222120] border border-[#2a2928] px-2 py-0.5 rounded-[11px] text-[10px]">
                  {acc}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Compute Tier Result Banner */}
        {profile && scanStep >= 5 && (
          <div className="p-4 rounded-[11px] bg-[#171615] border border-[#016A71]/50 flex items-center justify-between animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="space-y-1">
              <div className="text-xs text-[#34888D] font-semibold tracking-wide uppercase">
                Detected Hardware Profile
              </div>
              <div className="text-sm font-medium text-white">
                {profile.recommendations_summary}
              </div>
            </div>
            <Badge variant={getTierBadgeVariant(profile.compute_tier) as any} size="md">
              {profile.compute_tier} Tier
            </Badge>
          </div>
        )}

        {/* Action Button */}
        <div className="flex justify-end gap-3 pt-4">
          <Button variant="outline" onClick={onRetry} disabled={isLoading}>
            Re-scan
          </Button>
          <Button
            size="lg"
            onClick={onNext}
            disabled={isLoading || scanStep < 5 || !profile}
            className="w-48 shadow-[0_0_16px_rgba(1,106,113,0.3)]"
          >
            Recommended AI →
          </Button>
        </div>
      </div>
    </div>
  );
};
