import React from 'react';

/**
 * StatusPill: pending (gray), processing (blue, animated), done (green), error (red)
 */
interface StatusPillProps {
  status?: string | null;
}

export const StatusPill = ({ status }: StatusPillProps) => {
  const configs = {
    pending: {
      label: 'Pending',
      classes: 'bg-surface border-border-subtle text-text-secondary',
      dot: 'bg-text-muted',
    },
    processing: {
      label: 'Processing',
      classes: 'bg-blue-accent/10 border-blue-accent/30 text-blue-accent',
      dot: 'bg-blue-accent pulse-dot',
    },
    done: {
      label: 'Done',
      classes: 'bg-green-accent/10 border-green-accent/30 text-green-accent',
      dot: 'bg-green-accent',
    },
    error: {
      label: 'Error',
      classes: 'bg-red-accent/10 border-red-accent/30 text-red-accent',
      dot: 'bg-red-accent',
    },
  };

  const config = configs[status as keyof typeof configs] || configs.pending;

  return (
    <span className={`inline-flex items-center gap-1.5 font-mono text-xs px-2 py-0.5 rounded border ${config.classes}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  );
};
