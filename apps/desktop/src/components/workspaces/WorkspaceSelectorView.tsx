import React from 'react';
import { WorkspaceResponse } from '../../types';
import { Card } from '../ui/Card';
import {
  Sparkles,
  Code,
  GraduationCap,
  FlaskConical,
  Users,
  DollarSign,
  TrendingUp,
  PenTool,
  Check,
} from 'lucide-react';

interface WorkspaceSelectorViewProps {
  workspaces: WorkspaceResponse[];
  activeSlug: string;
  onSelectWorkspace: (slug: string) => void;
}

export const WorkspaceSelectorView: React.FC<WorkspaceSelectorViewProps> = ({
  workspaces,
  activeSlug,
  onSelectWorkspace,
}) => {
  const getWorkspaceIcon = (iconName: string) => {
    switch (iconName) {
      case 'code':
        return <Code className="w-5 h-5" />;
      case 'academic-cap':
        return <GraduationCap className="w-5 h-5" />;
      case 'beaker':
        return <FlaskConical className="w-5 h-5" />;
      case 'users':
        return <Users className="w-5 h-5" />;
      case 'currency-dollar':
        return <DollarSign className="w-5 h-5" />;
      case 'chart-bar':
        return <TrendingUp className="w-5 h-5" />;
      case 'pencil-square':
        return <PenTool className="w-5 h-5" />;
      default:
        return <Sparkles className="w-5 h-5" />;
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6 animate-in fade-in duration-150">
      <div>
        <h2 className="text-xl font-bold text-white tracking-tight">Workspaces</h2>
        <p className="text-xs text-[#949494]">
          Switch your active operating environment. Each workspace manages its own instructions, tools, and context.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {workspaces.map((ws) => {
          const isActive = ws.slug === activeSlug;

          return (
            <Card
              key={ws.id}
              variant={isActive ? 'active' : 'interactive'}
              onClick={() => onSelectWorkspace(ws.slug)}
              className="flex flex-col justify-between h-56 relative group transition-all"
            >
              {isActive && (
                <div className="absolute top-4 right-4 flex items-center gap-1.5 px-2.5 py-1 rounded-[11px] bg-[#016A71] text-white text-xs font-semibold shadow-[0_0_10px_rgba(1,106,113,0.3)]">
                  <Check className="w-3.5 h-3.5" />
                  <span>Active</span>
                </div>
              )}

              <div className="space-y-3">
                <div
                  className="w-10 h-10 rounded-[11px] flex items-center justify-center text-white ring-1 ring-[#2a2928]"
                  style={{ backgroundColor: `${ws.color}25`, color: ws.color }}
                >
                  {getWorkspaceIcon(ws.icon)}
                </div>

                <div>
                  <h3 className="text-sm font-bold text-white group-hover:text-[#34888D] transition-colors">
                    {ws.name} Workspace
                  </h3>
                  <p className="text-xs text-[#949494] mt-1 line-clamp-2 leading-relaxed">
                    {ws.description}
                  </p>
                </div>
              </div>

              <div className="space-y-2 pt-2 border-t border-[#2a2928]">
                <div className="flex flex-wrap gap-1">
                  {ws.enabled_tools.slice(0, 3).map((tool, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded-[11px] bg-[#222120] border border-[#2a2928] text-[10px] text-[#949494] font-mono"
                    >
                      {tool.replace('_', ' ')}
                    </span>
                  ))}
                  {ws.enabled_tools.length > 3 && (
                    <span className="px-2 py-0.5 rounded-[11px] bg-[#222120]/50 border border-[#2a2928] text-[10px] text-[#949494] font-mono">
                      +{ws.enabled_tools.length - 3}
                    </span>
                  )}
                </div>

                <div className="flex justify-between items-center text-[10px] text-[#949494] font-mono">
                  <span>Preferred: {ws.preferred_model || 'Auto'}</span>
                  <span>{ws.is_system ? 'System Preset' : 'Custom'}</span>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
};
