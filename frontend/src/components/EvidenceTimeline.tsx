import React, { useRef, useEffect } from 'react';
import type { EvidenceItem } from '../types';

interface Props {
  evidence: EvidenceItem[];
  participantNames: Record<string, string>;
}

export const EvidenceTimeline: React.FC<Props> = ({ evidence, participantNames }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [evidence.length]);

  // Show only recent evidence, deduplicated
  const recent = evidence.slice(-50);

  return (
    <div className="right-sidebar-section" ref={scrollRef}>
      <div className="sidebar-title">Evidence Stream</div>
      {recent.length === 0 && (
        <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem', padding: 'var(--space-sm) 0' }}>
          No evidence yet...
        </div>
      )}
      {recent.map((e, i) => {
        const name = participantNames[e.participant_id] || e.participant_id;
        const isPositive = e.score > 0;
        const scoreDisplay = isPositive ? `+${(e.score * e.weight).toFixed(0)}` : `${(e.score * e.weight).toFixed(0)}`;

        return (
          <div key={i} className="evidence-item">
            <span className="evidence-time">{e.timestamp.toFixed(0)}s</span>
            <span className="evidence-text">
              <strong style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{name}</strong>{' '}
              {e.reason.replace(new RegExp(`'${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}'\\s*`, 'g'), '')}
            </span>
            <span className={`evidence-score ${isPositive ? 'positive' : 'negative'}`}>
              {scoreDisplay}
            </span>
          </div>
        );
      })}
    </div>
  );
};
