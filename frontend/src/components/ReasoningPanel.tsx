import React from 'react';
import type { ReasonItem } from '../types';

interface Props {
  reasons: ReasonItem[];
}

const ICON_MAP: Record<string, string> = {
  positive: '✅',
  negative: '❌',
  warning: '⚠️',
  info: 'ℹ️',
};

export const ReasoningPanel: React.FC<Props> = ({ reasons }) => {
  if (reasons.length === 0) {
    return (
      <div>
        <div className="section-title">Reasoning</div>
        <div style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem', padding: 'var(--space-md) 0' }}>
          Waiting for evidence...
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="section-title">Reasoning</div>
      {reasons.map((r, i) => (
        <div key={i} className="reason-item animate-slide-in" style={{ animationDelay: `${i * 40}ms` }}>
          <div className={`reason-icon ${r.icon}`}>
            {ICON_MAP[r.icon] || 'ℹ️'}
          </div>
          <div className="reason-content">
            <div className="reason-text">{r.reason}</div>
          </div>
          <span className={`reason-impact ${r.impact.startsWith('+') ? 'positive' : r.impact.startsWith('-') ? 'negative' : ''}`}>
            {r.impact}
          </span>
        </div>
      ))}
    </div>
  );
};
