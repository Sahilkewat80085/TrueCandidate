const API_BASE = 'http://localhost:8000';

export async function fetchScenarios() {
  const res = await fetch(`${API_BASE}/api/scenarios/`);
  return res.json();
}

export async function startScenario(scenarioId: string, speed: number = 5.0) {
  const res = await fetch(`${API_BASE}/api/meetings/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario_id: scenarioId, speed }),
  });
  return res.json();
}

export async function stopMeeting(meetingId: string) {
  const res = await fetch(`${API_BASE}/api/meetings/${meetingId}/stop`, {
    method: 'POST',
  });
  return res.json();
}

export async function getPrediction(meetingId: string) {
  const res = await fetch(`${API_BASE}/api/meetings/${meetingId}/prediction`);
  return res.json();
}

export async function getConfidenceTimeline(meetingId: string) {
  const res = await fetch(`${API_BASE}/api/meetings/${meetingId}/confidence-timeline`);
  return res.json();
}

export async function getTranscript(meetingId: string) {
  const res = await fetch(`${API_BASE}/api/meetings/${meetingId}/transcript`);
  return res.json();
}

export async function getParticipants(meetingId: string) {
  const res = await fetch(`${API_BASE}/api/meetings/${meetingId}/participants`);
  return res.json();
}

export function createWebSocket(meetingId: string): WebSocket {
  return new WebSocket(`ws://localhost:8000/ws/${meetingId}`);
}
