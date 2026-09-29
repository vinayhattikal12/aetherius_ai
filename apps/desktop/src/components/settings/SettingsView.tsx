import React from 'react';
import { UserSettingsResponse, WorkspaceResponse } from '../../types';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import {
  Shield,
  Database,
  Layers,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';

interface SettingsViewProps {
  settings: UserSettingsResponse | null;
  workspaces: WorkspaceResponse[];
  backendOnline: boolean;
  onUpdateSettings: (updates: Partial<UserSettingsResponse>) => Promise<void>;
  onResetOnboarding: () => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  settings,
  workspaces,
  backendOnline,
  onUpdateSettings,
  onResetOnboarding,
}) => {
  if (!settings) return null;

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6 animate-in fade-in duration-150">
      <div>
        <h2 className="text-xl font-bold text-white tracking-tight">Platform Settings</h2>
        <p className="text-xs text-[#949494]">
          Configure privacy modes, default workspace routing, and local database connections.
        </p>
      </div>

      <div className="space-y-4">
        {/* Privacy Modes Card */}
        <Card className="space-y-4">
          <div className="flex items-center gap-2 text-sm font-bold text-white">
            <Shield className="w-4 h-4 text-[#34888D]" />
            <span>Privacy & Execution Mode</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              {
                mode: 'LOCAL_ONLY',
                title: 'Local Only',
                desc: '100% offline & local. Zero data leaves your machine.',
                variant: 'success' as const,
              },
              {
                mode: 'HYBRID',
                title: 'Hybrid Adaptive',
                desc: 'Local models for private files, cloud for heavy reasoning.',
                variant: 'purple' as const,
              },
              {
                mode: 'CLOUD',
                title: 'Cloud High-Power',
                desc: 'Full access to state-of-the-art frontier models.',
                variant: 'blue' as const,
              },
            ].map((item) => {
              const isSelected = settings.privacy_mode === item.mode;

              return (
                <div
                  key={item.mode}
                  onClick={() => onUpdateSettings({ privacy_mode: item.mode as any })}
                  className={`p-3.5 rounded-[11px] border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-[#171615] border-[#016A71] shadow-[0_0_12px_rgba(1,106,113,0.2)]'
                      : 'bg-black/40 border-[#2a2928] hover:border-[#34888D]/60'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-white">{item.title}</span>
                    <Badge variant={item.variant} size="sm">
                      {item.mode.replace('_', ' ')}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-[#949494] leading-relaxed">{item.desc}</p>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Database & System Connection */}
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-bold text-white">
              <Database className="w-4 h-4 text-[#34888D]" />
              <span>PostgreSQL & pgvector Engine</span>
            </div>
            <Badge variant={backendOnline ? 'success' : 'danger'} size="sm">
              {backendOnline ? 'PostgreSQL Active' : 'Connecting'}
            </Badge>
          </div>

          <div className="p-3 rounded-[11px] bg-black/40 border border-[#2a2928] text-xs font-mono text-[#949494] space-y-1">
            <div className="flex justify-between">
              <span>Database Engine:</span>
              <span className="text-white">PostgreSQL 18.x + pgvector</span>
            </div>
            <div className="flex justify-between">
              <span>Core Server:</span>
              <span className="text-white">FastAPI (Python 3.14 Async Engine)</span>
            </div>
            <div className="flex justify-between">
              <span>ORM & Migrations:</span>
              <span className="text-white">SQLAlchemy 2.0 + Alembic</span>
            </div>
          </div>
        </Card>

        {/* Workspace & Preferences */}
        <Card className="space-y-4">
          <div className="flex items-center gap-2 text-sm font-bold text-white">
            <Layers className="w-4 h-4 text-[#34888D]" />
            <span>Preferences</span>
          </div>

          <div className="space-y-3 text-xs">
            {/* Default Workspace */}
            <div className="flex items-center justify-between py-2 border-b border-[#2a2928]">
              <div>
                <div className="font-semibold text-white">Default Workspace on Launch</div>
                <div className="text-[#949494] text-[11px]">Choose starting workspace</div>
              </div>
              <select
                value={settings.default_workspace_slug}
                onChange={(e) => onUpdateSettings({ default_workspace_slug: e.target.value })}
                className="px-3 py-1.5 rounded-[11px] bg-[#201f1e] border border-[#2a2928] text-white text-xs focus:outline-none focus:border-[#34888D]/70"
              >
                {workspaces.map((ws) => (
                  <option key={ws.slug} value={ws.slug} className="bg-[#171615] text-white">
                    {ws.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Auto Routing */}
            <div className="flex items-center justify-between py-2 border-b border-[#2a2928]">
              <div>
                <div className="font-semibold text-white">Intelligent AI Routing</div>
                <div className="text-[#949494] text-[11px]">
                  Automatically select models based on query complexity and privacy
                </div>
              </div>
              <button
                onClick={() =>
                  onUpdateSettings({ auto_routing_enabled: !settings.auto_routing_enabled })
                }
                className="text-[#34888D]"
              >
                {settings.auto_routing_enabled ? (
                  <ToggleRight className="w-6 h-6 text-[#34888D]" />
                ) : (
                  <ToggleLeft className="w-6 h-6 text-[#949494]" />
                )}
              </button>
            </div>

            {/* Reset Onboarding Walkthrough */}
            <div className="flex items-center justify-between py-2">
              <div>
                <div className="font-semibold text-white">Re-run System Hardware Scan</div>
                <div className="text-[#949494] text-[11px]">
                  Trigger the onboarding hardware detection and model recommendations
                </div>
              </div>
              <Button size="sm" variant="outline" onClick={onResetOnboarding}>
                Run Scan
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};
