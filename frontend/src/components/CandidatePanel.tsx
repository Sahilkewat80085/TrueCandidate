import React from 'react';
import type { CandidatePrediction } from '../types';

interface Props {
  prediction: CandidatePrediction | null;
}

function getInitials(name: string): string {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

export const CandidatePanel: React.FC<Props> = ({ prediction }) => {
  if (!prediction || !prediction.current_candidate_id) {
    return (
      <div className="prediction-card">
        <div className="prediction-header">
          <span className="prediction-label">Identified Candidate</span>
        </div>
        <div className="empty-state" style={{ minHeight: 180 }}>
          <div className="empty-icon">🔍</div>
          <h3>Awaiting Identification</h3>
          <p>Select a scenario and start the simulation to begin candidate identification</p>
        </div>
      </div>
    );
  }

  const { current_candidate_name, confidence, confidence_level } = prediction;
  const name = current_candidate_name || 'Unknown';
  const confPercent = Math.round(confidence * 100);

  return (
    <div className="prediction-card animate-fade-in">
      <div className="prediction-header">
        <span className="prediction-label">Identified Candidate</span>
        <span className="prediction-label" style={{ color: 'var(--accent-primary-light)' }}>
          LIVE
        </span>
      </div>

      <div className="candidate-info">
        <div className="candidate-avatar">
          {getInitials(name)}
        </div>
        <div className="candidate-details">
          <h2>{name}</h2>
          <span className="candidate-role">
            {prediction.all_participants.find(p => p.participant_id === prediction.current_candidate_id)?.role || 'candidate'}
          </span>
        </div>
        <div className="confidence-display" style={{ marginLeft: 'auto' }}>
          <div className={`confidence-value ${confidence_level}`}>
            {confPercent}%
          </div>
          <div className={`confidence-level-label ${confidence_level}`} style={{ color: `var(--conf-${confidence_level === 'very_high' ? 'very-high' : confidence_level})` }}>
            {confidence_level.replace('_', ' ')}
          </div>
        </div>
      </div>

      <div className="confidence-bar">
        <div
          className={`confidence-fill ${confidence_level}`}
          style={{ width: `${confPercent}%` }}
        />
      </div>

      {/* Uncertainty Factors */}
      {prediction.uncertainty_factors.length > 0 && (
        <div style={{ marginTop: 'var(--space-md)' }}>
          {prediction.uncertainty_factors.slice(0, 2).map((factor, i) => (
            <div key={i} className="uncertainty-banner" style={{ marginBottom: 'var(--space-xs)' }}>
              <span className="uncertainty-icon">⚠️</span>
              <span>{factor}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
