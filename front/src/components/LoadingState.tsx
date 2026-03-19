import React from 'react';

interface LoadingStateProps {
  rows?: number;
  className?: string;
}

export const LoadingState = ({ rows = 5, className = '' }: LoadingStateProps) => {
  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton-shimmer rounded h-14" style={{ opacity: 1 - i * 0.1 }} />
      ))}
    </div>
  );
};

export const SkeletonCard = ({ className = '' }: Pick<LoadingStateProps, 'className'>) => (
  <div className={`bg-surface border border-border-subtle rounded-lg p-5 space-y-3 ${className}`}>
    <div className="skeleton-shimmer h-5 w-2/3 rounded" />
    <div className="skeleton-shimmer h-4 w-1/2 rounded" />
    <div className="skeleton-shimmer h-4 w-1/3 rounded" />
  </div>
);
