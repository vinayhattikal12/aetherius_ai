import React from 'react';
import { WorkspaceResponse } from '../../types';
import { Button } from '../ui/Button';
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
  Check
} from 'lucide-react';

interface WorkspacePickerProps {
  workspaces: WorkspaceResponse[];
  selectedSlug: string;
  onSelect: (slug: string) => void;
  onComplete: () => void;
  onBack: () => void;
}

export const WorkspacePicker: React.FC<WorkspacePickerProps> = ({
  workspaces,
  selectedSlug,
  onSelect,
  onComplete,
  onBack,
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
    <div className="h-full w-full overflow-y-auto flex flex-col items-center px-4 md:px-6 py-6 md:py-8 bg-[#000000] relative">
      <div className="max-w-4xl w-full space-y-6 animate-in fade-in duration-300 pb-20">
        <div className="text-center space-y-3">
          <h2 className="text-3xl font-bold tracking-tight text-white">
            Choose Your Initial Workspace
          </h2>
          <p className="text-sm text-[#949494] max-w-lg mx-auto">
            Workspaces tailor system instructions, available tools, memory filters, and model preferences to your exact role.
          </p>
        </div>

        {/* Workspace Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {workspaces.map((ws) => {
            const isSelected = selectedSlug === ws.slug;

            return (
              <Card
                key={ws.id}
                onClick={() => onSelect(ws.slug)}
                variant={isSelected ? 'active' : 'interactive'}
                className="flex flex-col justify-between h-48 relative group"
              >
                {isSelected && (
                  <div className="absolute top-3 right-3 p-1 rounded-[11px] bg-[#016A71] text-white shadow-[0_0_10px_rgba(1,106,113,0.3)]">
                    <Check className="w-3.5 h-3.5" />
                  </div>
                )}

                <div className="space-y-2.5">
                  <div
                    className="w-9 h-9 rounded-[11px] flex items-center justify-center text-white ring-1 ring-[#2a2928]"
                    style={{ backgroundColor: `${ws.color}25`, color: ws.color }}
                  >
                    {getWorkspaceIcon(ws.icon)}
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white group-hover:text-[#34888D] transition-colors">
                      {ws.name}
                    </h3>
                    <p className="text-xs text-[#949494] mt-1 line-clamp-3 leading-relaxed">
                      {ws.description}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 text-[10px] text-[#949494] font-mono">
                  <span>Model: {ws.preferred_model?.split(':')[0] || 'Auto'}</span>
                </div>
              </Card>
            );
          })}
        </div>

        {/* Action Buttons */}
        <div className="flex justify-between pt-4 border-t border-[#2a2928]">
          <Button variant="ghost" onClick={onBack}>
            ← Back
          </Button>
          <Button size="lg" onClick={onComplete} className="w-60 shadow-[0_0_16px_rgba(1,106,113,0.3)]">
            Start Using Aetherius →
          </Button>
        </div>
      </div>
    </div>
  );
};
