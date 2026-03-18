import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from './ui/button';

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState = ({
  message = 'Something went wrong',
  onRetry,
  className = '',
}: ErrorStateProps) => {
  return (
    <div className={`flex flex-col items-center justify-center py-16 gap-4 ${className}`}>
      <div className="w-12 h-12 rounded-full bg-red-accent/10 border border-red-accent/30 flex items-center justify-center">
        <AlertCircle className="w-6 h-6 text-red-accent" />
      </div>
      <div className="text-center">
        <p className="text-text-primary font-medium">{message}</p>
        <p className="text-text-muted text-sm mt-1">Please try again or contact support</p>
      </div>
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="flex items-center gap-2 border-border-subtle bg-surface hover:bg-surface-elevated text-text-secondary"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </Button>
      )}
    </div>
  );
};
