import React from 'react';
import { HardwareProfile } from '../../types';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Cpu, MemoryStick, Zap, HardDrive, CheckCircle2 } from 'lucide-react';

interface HardwareTelemetryCardProps {
  profile: HardwareProfile | null;
}

export const HardwareTelemetryCard: React.FC<HardwareTelemetryCardProps> = ({ profile }) => {
  if (!profile) {
    return (
      <Card className="text-center py-6 text-zinc-500 text-xs">
        Hardware data not loaded.
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight">System & Compute Telemetry</h3>
          <p className="text-xs text-[#949494]">Real-time local hardware capability analysis</p>
        </div>
        <Badge variant="purple" size="md">
          {profile.compute_tier} Compute Tier
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* CPU */}
        <Card className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-white">
            <Cpu className="w-4 h-4 text-[#34888D]" />
            <span>CPU</span>
          </div>
          <div className="text-sm font-bold text-white truncate" title={profile.cpu.model}>
            {profile.cpu.model}
          </div>
          <div className="text-[11px] text-[#949494]">
            {profile.cpu.physical_cores} Cores • {profile.cpu.logical_cores} Threads ({profile.architecture})
          </div>
        </Card>

        {/* RAM */}
        <Card className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-white">
            <MemoryStick className="w-4 h-4 text-[#34888D]" />
            <span>Memory (RAM)</span>
          </div>
          <div className="text-sm font-bold text-white">
            {profile.ram.total_gb} GB Total
          </div>
          <div className="text-[11px] text-[#949494]">
            {profile.ram.available_gb} GB Available ({profile.ram.percent_used}% used)
          </div>
        </Card>

        {/* GPU */}
        <Card className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-white">
            <Zap className="w-4 h-4 text-amber-400" />
            <span>GPU / VRAM</span>
          </div>
          <div className="text-sm font-bold text-white truncate" title={profile.gpu[0]?.name}>
            {profile.gpu[0]?.name || 'Integrated'}
          </div>
          <div className="text-[11px] text-[#949494]">
            {profile.vram_gb} GB VRAM • {profile.gpu.some(g => g.cuda_supported) ? 'CUDA Ready' : 'DirectML'}
          </div>
        </Card>

        {/* Storage */}
        <Card className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-white">
            <HardDrive className="w-4 h-4 text-[#34888D]" />
            <span>Storage</span>
          </div>
          <div className="text-sm font-bold text-white">
            {profile.storage.free_gb} GB Free
          </div>
          <div className="text-[11px] text-[#949494]">
            Total {profile.storage.total_gb} GB ({profile.os} {profile.os_release})
          </div>
        </Card>
      </div>

      <div className="p-3.5 rounded-[11px] bg-[#171615] border border-[#2a2928] text-xs text-white flex items-center gap-2">
        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
        <span>{profile.recommendations_summary}</span>
      </div>
    </div>
  );
};
