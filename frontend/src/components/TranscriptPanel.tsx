import React, { useRef, useEffect } from 'react';
import type { TranscriptEntry } from '../types';

interface Props {
  transcript: TranscriptEntry[];
  candidateId: string | null;
  participantNames: Record<string, string>;
}

export const TranscriptPanel: React.FC<Props> = ({ transcript, candidateId, participantNames }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript.length]);

  // React's JSX auto-escapes string variables to prevent Cross-Site Scripting (XSS).
  // We defensively display a slice of the most recent 30 transcript entries.
  const recent = transcript.slice(-30);

  return (
    <div className="right-sidebar-section" ref={scrollRef}>
      <div className="sidebar-title">Live Transcript</div>
      {recent.length === 0 && (
        <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem', padding: 'var(--space-sm) 0' }}>
          Waiting for speech...
        </div>
      )}
      {recent.map((entry, i) => {
        const name = participantNames[entry.speaker_id] || entry.speaker_name || entry.speaker_id;
        const isCandidate = entry.speaker_id === candidateId;
        const speakerClass = isCandidate ? 'candidate' : 'interviewer';

        return (
          <div key={i} className="transcript-item animate-fade-in">
            <div className="transcript-meta">
              <span className="transcript-time">{entry.time.toFixed(0)}s</span>
              <span className={`transcript-speaker ${speakerClass}`}>
                {name}
              </span>
            </div>
            <div className="transcript-text">{entry.text}</div>
          </div>
        );
      })}
    </div>
  );
};
