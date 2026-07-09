import React from 'react';
import type { ParticipantPrediction } from '../types';

interface Props {
  participants: ParticipantPrediction[];
  candidateId: string | null;
}

function getInitials(name: string): string {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function getConfColor(conf: number): string {
  if (conf >= 0.7) return 'var(--conf-very-high)';
  if (conf >= 0.4) return 'var(--conf-high)';
  if (conf >= 0.2) return 'var(--conf-medium)';
  return 'var(--conf-low)';
}

export const ParticipantList: React.FC<Props> = ({ participants, candidateId }) => {
  if (participants.length === 0) {
    return null;
  }

  const sorted = [...participants].sort((a, b) => b.confidence - a.confidence);

  return (
    <div>
      <div className="section-title">Participants</div>
      {sorted.map((p, i) => {
        const isCandidate = p.participant_id === candidateId;
        const confPercent = Math.round(p.confidence * 100);

        return (
          <div
            key={p.participant_id}
            className={`participant-card ${isCandidate ? 'is-candidate' : ''} animate-slide-in`}
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <div className="participant-left">
              <div className={`participant-avatar ${p.role}`}>
                {getInitials(p.display_name)}
              </div>
              <div>
                <div className="participant-name">{p.display_name}</div>
                <div className="participant-role">
                  {p.role === 'candidate' ? '🎯 ' : p.role === 'interviewer' ? '🎤 ' : p.role === 'observer' ? '👁 ' : '❓ '}
                  {p.role}
                </div>
              </div>
            </div>
            <div
              className="participant-confidence"
              style={{ color: getConfColor(p.confidence) }}
            >
              {confPercent}%
            </div>
          </div>
        );
      })}
    </div>
  );
};
