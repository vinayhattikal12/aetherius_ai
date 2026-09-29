import React from 'react';
import { Button } from '../ui/Button';
import { Sparkles, Cpu, ShieldCheck, Layers } from 'lucide-react';

interface WelcomeHeroProps {
  onStart: () => void;
}

export const WelcomeHero: React.FC<WelcomeHeroProps> = ({ onStart }) => {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 py-12 relative overflow-hidden bg-[#000000]">
      {/* Background glow effects */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-[#016A71]/15 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-[300px] h-[250px] bg-[#34888D]/10 blur-[100px] rounded-full pointer-events-none" />

      {/* Main Content */}
      <div className="relative z-10 max-w-2xl text-center space-y-8 animate-in fade-in zoom-in-95 duration-300">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-[11px] bg-[#016A71]/20 border border-[#016A71]/40 text-[#34888D] text-xs font-medium tracking-wide">
          <Sparkles className="w-3.5 h-3.5 text-[#34888D] animate-pulse" />
          <span>Aetherius AI Platform • Autonomous Intelligence</span>
        </div>

        <div className="space-y-4">
          <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight text-white">
            Aetherius
          </h1>
          <p className="text-xl md:text-2xl text-[#949494] font-normal">
            One AI environment for everything you do.
          </p>
        </div>

        <p className="text-sm md:text-base text-[#949494] leading-relaxed max-w-lg mx-auto">
          Adaptive local AI, cloud intelligence, role-based workspaces, and autonomous task continuity — seamlessly configured for your hardware.
        </p>

        {/* Value pillars */}
        <div className="grid grid-cols-3 gap-3 pt-4 max-w-md mx-auto text-left">
          <div className="p-3.5 rounded-[11px] bg-[#171615] border border-[#2a2928]">
            <Cpu className="w-4 h-4 text-[#34888D] mb-2" />
            <div className="text-xs font-semibold text-white">Hardware Native</div>
            <div className="text-[11px] text-[#949494] mt-0.5">Auto GPU & RAM adaptation</div>
          </div>
          <div className="p-3.5 rounded-[11px] bg-[#171615] border border-[#2a2928]">
            <Layers className="w-4 h-4 text-[#34888D] mb-2" />
            <div className="text-xs font-semibold text-white">Workspaces</div>
            <div className="text-[11px] text-[#949494] mt-0.5">Dev, Student, HR & more</div>
          </div>
          <div className="p-3.5 rounded-[11px] bg-[#171615] border border-[#2a2928]">
            <ShieldCheck className="w-4 h-4 text-emerald-400 mb-2" />
            <div className="text-xs font-semibold text-white">Private by Design</div>
            <div className="text-[11px] text-[#949494] mt-0.5">Local-first pgvector state</div>
          </div>
        </div>

        {/* CTA */}
        <div className="pt-6">
          <Button
            size="lg"
            onClick={onStart}
            className="w-48 shadow-[0_0_20px_rgba(1,106,113,0.3)] text-base"
          >
            Get Started
          </Button>
        </div>
      </div>
    </div>
  );
};
