import React, { useState, useEffect, useMemo, useCallback } from 'react';
import type { Scenario } from '../types';
import { fetchScenarios, startScenario, stopMeeting } from '../utils/api';
import { useMeeting } from '../hooks/useMeeting';
import { ScenarioSelector } from './ScenarioSelector';
import { CandidatePanel } from './CandidatePanel';
import { ParticipantList } from './ParticipantList';
import { ReasoningPanel } from './ReasoningPanel';
import { ConfidenceGraph } from './ConfidenceGraph';
import { EvidenceTimeline } from './EvidenceTimeline';
import { TranscriptPanel } from './TranscriptPanel';

export const Dashboard: React.FC = () => {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { state, isConnected, startMeeting: startMeetingState, resetMeeting } = useMeeting();

  // Load scenarios on mount
  useEffect(() => {
    fetchScenarios()
      .then(data => setScenarios(data.scenarios || []))
      .catch(err => console.error('Failed to load scenarios:', err));
  }, []);

  // Start scenario handler
  const handleStartScenario = useCallback(async (scenarioId: string) => {
    if (state.isActive && state.meetingId) {
      await stopMeeting(state.meetingId);
    }
    resetMeeting();

    setIsLoading(true);
    setSelectedScenario(scenarioId);

    try {
      const result = await startScenario(scenarioId, 5.0);
      startMeetingState(result.meeting_id, scenarioId);
    } catch (err) {
      console.error('Failed to start scenario:', err);
    } finally {
      setIsLoading(false);
    }
  }, [state.isActive, state.meetingId, startMeetingState, resetMeeting]);

  // Build participant name map
  const participantNames = useMemo(() => {
    const names: Record<string, string> = {};
    if (state.prediction?.all_participants) {
      for (const p of state.prediction.all_participants) {
        names[p.participant_id] = p.display_name;
      }
    }
    return names;
  }, [state.prediction]);

  const prediction = state.prediction;
  const candidateId = prediction?.current_candidate_id || null;

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="app-logo">
          <div className="logo-icon">🎯</div>
          <div>
            <h1>
              <span className="gradient-text">TrueCandidate</span>
            </h1>
            <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)', letterSpacing: '0.15em', textTransform: 'uppercase' }}>
              by Sherlock AI
            </span>
          </div>
        </div>

        <div className="header-status">
          {state.meetingId && (
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              {state.meetingId}
            </span>
          )}
          <div className={`status-badge ${state.isActive && isConnected ? 'active' : 'idle'}`}>
            <span className={`status-dot ${state.isActive && isConnected ? 'active' : 'idle'}`} />
            {isLoading ? 'Starting...' : state.isActive && isConnected ? 'Live' : 'Idle'}
          </div>
          {state.events.length > 0 && (
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              {state.events.length} events
            </span>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="app-main">
        {/* Left Sidebar: Scenarios */}
        <ScenarioSelector
          scenarios={scenarios}
          activeScenario={selectedScenario}
          isRunning={isLoading}
          onSelect={handleStartScenario}
        />

        {/* Center Panel */}
        <div className="center-panel">
          {/* Candidate Prediction */}
          <CandidatePanel prediction={prediction} />

          {/* Confidence Graph */}
          <div className="glass-card" style={{ padding: 'var(--space-lg)' }}>
            <ConfidenceGraph
              timeline={state.confidenceTimeline}
              participantNames={participantNames}
            />
          </div>

          {/* Participants */}
          <div className="glass-card" style={{ padding: 'var(--space-lg)' }}>
            <ParticipantList
              participants={prediction?.all_participants || []}
              candidateId={candidateId}
            />
          </div>

          {/* Reasoning */}
          <div className="glass-card" style={{ padding: 'var(--space-lg)' }}>
            <ReasoningPanel reasons={prediction?.top_reasons || []} />
          </div>
        </div>

        {/* Right Sidebar: Evidence + Transcript */}
        <div className="right-sidebar">
          <EvidenceTimeline
            evidence={state.evidence}
            participantNames={participantNames}
          />
          <TranscriptPanel
            transcript={state.transcript}
            candidateId={candidateId}
            participantNames={participantNames}
          />
        </div>
      </main>
    </div>
  );
};
