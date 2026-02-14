import React from 'react';

interface SkeletonCardProps {
  variant?: 'booking' | 'statistics' | 'timeline' | 'action';
}

export const SkeletonCard: React.FC<SkeletonCardProps> = ({ variant = 'booking' }) => {
  if (variant === 'statistics') {
    return (
      <div className="bg-white rounded-lg p-6 shadow-sm animate-pulse">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <div className="h-3 bg-gray-200 rounded w-24 mb-2"></div>
            <div className="h-8 bg-gray-200 rounded w-16"></div>
          </div>
          <div className="w-14 h-14 bg-gray-200 rounded-xl"></div>
        </div>
      </div>
    );
  }

  if (variant === 'timeline') {
    return (
      <div className="flex gap-3 animate-pulse">
        <div className="w-8 h-8 bg-gray-200 rounded-full flex-shrink-0"></div>
        <div className="flex-1">
          <div className="h-4 bg-gray-200 rounded w-32 mb-2"></div>
          <div className="h-3 bg-gray-200 rounded w-48 mb-1"></div>
          <div className="h-3 bg-gray-200 rounded w-24"></div>
        </div>
      </div>
    );
  }

  if (variant === 'action') {
    return (
      <div className="bg-white rounded-lg p-5 shadow-sm border-2 border-transparent animate-pulse">
        <div className="flex flex-col items-center text-center gap-3">
          <div className="w-14 h-14 bg-gray-200 rounded-xl"></div>
          <div>
            <div className="h-4 bg-gray-200 rounded w-24 mb-2"></div>
            <div className="h-3 bg-gray-200 rounded w-32"></div>
          </div>
        </div>
      </div>
    );
  }

  // Default: booking card skeleton
  return (
    <div className="bg-gradient-to-br from-gray-200 to-gray-300 text-white border-none p-6 rounded-lg animate-pulse">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="flex-1 w-full">
          <div className="h-6 bg-white/20 rounded w-32 mb-3"></div>
          <div className="h-8 bg-white/30 rounded w-48 mb-2"></div>
          <div className="h-4 bg-white/20 rounded w-40 mb-4"></div>
          <div className="flex flex-wrap gap-3">
            <div className="h-12 bg-white/20 rounded-lg w-24"></div>
            <div className="h-12 bg-white/20 rounded-lg w-32"></div>
            <div className="h-12 bg-white/20 rounded-lg w-20"></div>
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <div className="h-9 bg-white/20 rounded w-24"></div>
          <div className="h-9 bg-white/20 rounded w-24"></div>
        </div>
      </div>
    </div>
  );
};

export default SkeletonCard;
