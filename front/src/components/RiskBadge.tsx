import React from 'react';

/**
 * RiskBadge: score 1-3 = green, 4-6 = yellow, 7-10 = red
 */
interface RiskBadgeProps {
  score?: number | null;
  size?: 'sm' | 'lg';
}

export const RiskBadge = ({ score, size = 'sm' }: RiskBadgeProps) => {
  if (score === null || score === undefined) {
    return (
      <span className={`font-mono inline-flex items-center justify-center rounded border ${
        size === 'lg' ? 'text-base px-3 py-1' : 'text-xs px-2 py-0.5'
      } bg-surface border-border-subtle text-text-muted`}>
        N/A
      </span>
    );
  }

  const s = Number(score);
  let colorClasses = '';
  if (s <= 3) {
    colorClasses = 'bg-green-accent/10 border-green-accent/30 text-green-accent';
  } else if (s <= 6) {
    colorClasses = 'bg-yellow-accent/10 border-yellow-accent/30 text-yellow-accent';
  } else {
    colorClasses = 'bg-red-accent/10 border-red-accent/30 text-red-accent';
  }

  return (
    <span
      className={`font-mono inline-flex items-center justify-center rounded border ${
        size === 'lg' ? 'text-2xl px-4 py-2' : 'text-xs px-2 py-0.5'
      } ${colorClasses}`}
    >
      {s}/10
    </span>
  );
};
