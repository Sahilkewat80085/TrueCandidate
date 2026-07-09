/* eslint-disable @typescript-eslint/no-explicit-any */

// ============================================
// Core Types matching backend models
// ============================================

export interface Scenario {
  id: string;
  title: string;
  description: string;
  difficulty: string;
  filename: string;
}

export interface CalendarMetadata {
  candidate_name: string;
  candidate_email?: string;
  interviewer_names: string[];
  scheduled_time?: string;
  position?: string;
}

export interface ParticipantPrediction {
  participant_id: string;
  display_name: string;
  confidence: number;
  role: string;
  top_reasons: ReasonItem[];
}

export interface ReasonItem {
  signal: string;
  impact: string;
  reason: string;
  icon: string;
}

export interface CandidatePrediction {
  meeting_id: string;
  current_candidate_id: string | null;
  current_candidate_name: string | null;
  confidence: number;
  confidence_level: string;
  top_reasons: ReasonItem[];
  all_participants: ParticipantPrediction[];
  uncertainty_factors: string[];
  timestamp: number;
}

export interface ConfidencePoint {
  timestamp: number;
  participant_id: string;
  confidence: number;
  event_description?: string;
}

export interface MeetingEvent {
  event_type: string;
  participant_id?: string;
  timestamp: number;
  data: Record<string, any>;
}

export interface EvidenceItem {
  signal_type: string;
  participant_id: string;
  score: number;
  weight: number;
  confidence: number;
  reason: string;
  timestamp: number;
}

export interface TranscriptEntry {
  speaker_id: string;
  speaker_name: string;
  text: string;
  time: number;
}

export interface WebSocketMessage {
  type: string;
  meeting_id?: string;
  prediction?: CandidatePrediction;
  event?: MeetingEvent;
  evidence?: EvidenceItem[];
}

// App state
export interface MeetingState {
  meetingId: string | null;
  scenarioId: string | null;
  isActive: boolean;
  prediction: CandidatePrediction | null;
  confidenceTimeline: ConfidencePoint[];
  events: MeetingEvent[];
  evidence: EvidenceItem[];
  transcript: TranscriptEntry[];
}
