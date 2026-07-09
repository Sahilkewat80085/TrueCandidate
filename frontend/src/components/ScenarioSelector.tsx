import React from 'react';
import type { Scenario } from '../types';

interface Props {
  scenarios: Scenario[];
  activeScenario: string | null;
  isRunning: boolean;
  onSelect: (id: string) => void;
}

export const ScenarioSelector: React.FC<Props> = ({ scenarios, activeScenario, isRunning, onSelect }) => {
  return (
    <div className="sidebar">
      <div className="sidebar-title">Scenarios</div>
      {scenarios.map((s, i) => (
        <div
          key={s.id}
          className={`scenario-card ${activeScenario === s.id ? 'active' : ''} animate-fade-in`}
          style={{ animationDelay: `${i * 50}ms` }}
          onClick={() => !isRunning && onSelect(s.id)}
          role="button"
          tabIndex={0}
        >
          <div className="scenario-title">
            <span style={{ opacity: 0.4, marginRight: 6, fontFamily: 'var(--font-mono)', fontSize: '0.7rem' }}>
              {String(i + 1).padStart(2, '0')}
            </span>
            {s.title}
          </div>
          <div className="scenario-desc">{s.description}</div>
          <span className={`scenario-badge badge-${s.difficulty}`}>{s.difficulty}</span>
        </div>
      ))}

      {scenarios.length === 0 && (
        <div style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem', textAlign: 'center', padding: '2rem 0' }}>
          Loading scenarios...
        </div>
      )}
    </div>
  );
};
