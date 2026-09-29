import React from 'react';
import { WorkspaceResponse, HardwareProfile, UserSettingsResponse } from '../../types';
import { Badge } from '../ui/Badge';
import { Shield, Sparkles, Moon, Sun, Database } from 'lucide-react';

interface TopHeaderProps {
  activeWorkspace: WorkspaceResponse | null;
  hardwareProfile: HardwareProfile | null;
  settings: UserSettingsResponse | null;
  backendOnline: boolean;
  onOpenWorkspaces: () => void;
  onToggleTheme: () => void;
}

export const TopHeader: React.FC<TopHeaderProps> = ({
  activeWorkspace,
  hardwareProfile,
  settings,
  backendOnline,
  onOpenWorkspaces,
  onToggleTheme,
}) => {
  return (
    <header className="h-14 border-b border-[#2a2928] bg-[#000000] px-6 flex items-center justify-between select-none">
      {/* Left: Active Workspace selector button */}
      <div className="flex items-center gap-3">
        {activeWorkspace && (
          <button
            onClick={onOpenWorkspaces}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-[11px] bg-[#171615] border border-[#2a2928] hover:border-[#34888D]/60 text-xs font-semibold text-white transition-all"
          >
            <span
              className="w-2.5 h-2.5 rounded-full ring-2 ring-[#016A71]/30"
              style={{ backgroundColor: activeWorkspace.color }}
            />
            <span>{activeWorkspace.name} Workspace</span>
            <span className="text-[#949494] font-normal">▾</span>
          </button>
        )}
      </div>

      {/* Right: Telemetry & State Badges */}
      <div className="flex items-center gap-3">
        {/* Backend / PostgreSQL status */}
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-[11px] bg-[#171615] border border-[#2a2928] text-[11px] text-[#949494]">
          <Database className="w-3 h-3 text-[#34888D]" />
          <span>PostgreSQL:</span>
          <span className={backendOnline ? 'text-emerald-400 font-medium' : 'text-rose-400'}>
            {backendOnline ? 'Connected' : 'Connecting...'}
          </span>
        </div>

        {/* Privacy Mode */}
        {settings && (
          <Badge
            variant={
              settings.privacy_mode === 'LOCAL_ONLY'
                ? 'success'
                : settings.privacy_mode === 'HYBRID'
                ? 'purple'
                : 'blue'
            }
            size="sm"
          >
            <Shield className="w-3 h-3" />
            <span>{settings.privacy_mode.replace('_', ' ')}</span>
          </Badge>
        )}

        {/* Compute Tier */}
        {hardwareProfile && (
          <Badge variant="outline" size="sm">
            <Sparkles className="w-3 h-3 text-[#34888D]" />
            <span>{hardwareProfile.compute_tier}</span>
          </Badge>
        )}

        {/* Theme Toggle */}
        <button
          onClick={onToggleTheme}
          className="p-2 rounded-[11px] hover:bg-[#171615] text-[#949494] hover:text-white transition-colors border border-transparent hover:border-[#2a2928]"
          title="Toggle Theme"
        >
          {settings?.theme === 'light' ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-[#949494]" />
          )}
        </button>
      </div>
    </header>
  );
};
