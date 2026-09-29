import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'purple' | 'blue' | 'outline';
  size?: 'sm' | 'md';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'sm',
  className = '',
}) => {
  const variantStyles = {
    default: 'bg-[#171615] text-[#949494] border-[#2a2928]',
    success: 'bg-emerald-950/40 text-emerald-400 border-emerald-800/40',
    warning: 'bg-amber-950/40 text-amber-400 border-amber-800/40',
    danger: 'bg-rose-950/40 text-rose-400 border-rose-800/40',
    purple: 'bg-[#016A71]/20 text-[#34888D] border-[#016A71]/50',
    blue: 'bg-[#016A71]/25 text-[#4e99a3] border-[#34888D]/40',
    outline: 'bg-transparent text-[#949494] border-[#2a2928]',
  };

  const sizeStyles = {
    sm: 'px-2 py-0.5 text-xs font-medium',
    md: 'px-2.5 py-1 text-xs font-semibold',
  };

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-[11px] border transition-colors ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
    >
      {children}
    </span>
  );
};
