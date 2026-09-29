import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'subtle' | 'interactive' | 'active';
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'default',
  className = '',
  ...props
}) => {
  const variantStyles = {
    default: 'bg-[#171615] border border-[#2a2928]',
    subtle: 'bg-[#171615]/70 border border-[#2a2928]/60',
    interactive: 'bg-[#171615] border border-[#2a2928] hover:border-[#34888D]/60 hover:bg-[#1c1b1a] cursor-pointer transition-all duration-150',
    active: 'bg-[#171615] border border-[#016A71] shadow-[0_0_16px_rgba(1,106,113,0.25)]',
  };

  return (
    <div
      className={`rounded-[11px] p-5 ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
