import { useState, useCallback, useEffect, useRef } from 'react';
import type {
  MeetingState,
  CandidatePrediction,
  EvidenceItem,
  MeetingEvent,
  ConfidencePoint,
  TranscriptEntry,
  WebSocketMessage,
} from '../types';
import { useWebSocket } from './useWebSocket';

const initialState: MeetingState = {
  meetingId: null,
  scenarioId: null,
  isActive: false,
  prediction: null,
  confidenceTimeline: [],
  events: [],
  evidence: [],
  transcript: [],
};

export function useMeeting() {
  const [state, setState] = useState<MeetingState>(initialState);
  const { isConnected, addListener } = useWebSocket(state.meetingId);
  const stateRef = useRef(state);
  stateRef.current = state;

  const startMeeting = useCallback((meetingId: string, scenarioId: string) => {
    setState({
      ...initialState,
      meetingId,
      scenarioId,
      isActive: true,
    });
  }, []);

  const stopMeeting = useCallback(() => {
    setState(prev => ({ ...prev, isActive: false }));
  }, []);

  const resetMeeting = useCallback(() => {
    setState(initialState);
  }, []);

  // Handle WebSocket messages
  useEffect(() => {
    const unsubscribe = addListener((msg: WebSocketMessage) => {
      if (msg.type === 'prediction_update' || msg.type === 'initial_state') {
        setState(prev => {
          const newState = { ...prev };

          // Update prediction
          if (msg.prediction) {
            newState.prediction = msg.prediction;
          }

          // Add event to timeline
          if (msg.event) {
            newState.events = [...prev.events, msg.event];

            // Extract transcript from transcript_chunk events
            if (msg.event.event_type === 'transcript_chunk' && msg.event.participant_id) {
              const entry: TranscriptEntry = {
                speaker_id: msg.event.participant_id,
                speaker_name: msg.event.data?.display_name || msg.event.participant_id,
                text: msg.event.data?.text || '',
                time: msg.event.timestamp,
              };
              newState.transcript = [...prev.transcript, entry];
            }
          }

          // Add evidence items
          if (msg.evidence && msg.evidence.length > 0) {
            newState.evidence = [...prev.evidence, ...msg.evidence];
          }

          // Build confidence timeline from prediction
          if (msg.prediction?.all_participants) {
            const newPoints: ConfidencePoint[] = msg.prediction.all_participants.map(p => ({
              timestamp: msg.prediction!.timestamp,
              participant_id: p.participant_id,
              confidence: p.confidence,
            }));
            newState.confidenceTimeline = [...prev.confidenceTimeline, ...newPoints];
          }

          return newState;
        });
      }
    });

    return unsubscribe;
  }, [addListener]);

  return {
    state,
    isConnected,
    startMeeting,
    stopMeeting,
    resetMeeting,
  };
}
