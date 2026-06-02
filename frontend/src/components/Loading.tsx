import React from 'react';

interface LoadingProps {
  size?: 'sm' | 'md' | 'lg';
  text?: string;
  fullScreen?: boolean;
}

export const Loading: React.FC<LoadingProps> = ({ 
  size = 'md', 
  text,
  fullScreen = false 
}) => {
  const sizeClasses = {
    sm: 'h-6 w-6 border-2',
    md: 'h-12 w-12 border-3',
    lg: 'h-16 w-16 border-4'
  };

  const spinner = (
    <div className="flex flex-col items-center justify-center gap-3">
      <div 
        className={`animate-spin rounded-full border-blue-600 border-t-transparent ${sizeClasses[size]}`}
        role="status"
        aria-label="Loading"
      />
      {text && (
        <p className="text-gray-600 text-sm font-medium">{text}</p>
      )}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 bg-white bg-opacity-90 flex items-center justify-center z-50">
        {spinner}
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center py-12">
      {spinner}
    </div>
  );
};

// Small inline loader for buttons
export const ButtonLoader: React.FC = () => (
  <div 
    className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
    role="status"
    aria-label="Loading"
  />
);
