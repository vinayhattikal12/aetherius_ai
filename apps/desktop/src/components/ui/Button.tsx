import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  className = '',
  disabled,
  ...props
}) => {
  const variantStyles = {
    primary: 'bg-[#016A71] hover:bg-[#01575d] text-white border border-transparent shadow-[0_0_12px_rgba(1,106,113,0.25)] active:scale-[0.98]',
    secondary: 'bg-[#171615] hover:bg-[#201f1e] text-white border border-[#2a2928] hover:border-[#363534] active:scale-[0.98]',
    outline: 'bg-transparent hover:bg-[#171615] text-white border border-[#2a2928] hover:border-[#363534] active:scale-[0.98]',
    ghost: 'bg-transparent hover:bg-[#171615] text-[#949494] hover:text-white',
    danger: 'bg-rose-700 hover:bg-rose-600 text-white shadow-lg shadow-rose-950/20 active:scale-[0.98]',
  };

  const sizeStyles = {
    sm: 'px-3 py-1.5 text-xs font-medium rounded-[11px]',
    md: 'px-4 py-2 text-sm font-medium rounded-[11px]',
    lg: 'px-5 py-2.5 text-base font-semibold rounded-[11px]',
  };

  return (
    <button
      disabled={disabled || isLoading}
      className={`inline-flex items-center justify-center gap-2 transition-all duration-150 select-none disabled:opacity-50 disabled:pointer-events-none ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {isLoading ? (
        <>
          <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-current" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
          Loading...
        </>
      ) : (
        children
      )}
    </button>
  );
};
