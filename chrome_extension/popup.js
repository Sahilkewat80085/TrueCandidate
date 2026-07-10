document.addEventListener('DOMContentLoaded', () => {
  const setupForm = document.getElementById('setup-form');
  const activeSession = document.getElementById('active-session');
  const startBtn = document.getElementById('start-btn');
  const stopBtn = document.getElementById('stop-btn');
  const sessionIdText = document.getElementById('session-id');

  // Check if session already running
  chrome.storage.local.get(['meetingId', 'candidateName'], (data) => {
    if (data.meetingId) {
      showActiveSession(data.meetingId);
    }
  });

  startBtn.addEventListener('click', async () => {
    const candidateName = document.getElementById('candidate-name').value;
    const candidateEmail = document.getElementById('candidate-email').value;
    const interviewerName = document.getElementById('interviewer-name').value;
    const position = document.getElementById('position').value;

    if (!candidateName) {
      alert("Candidate name is required.");
      return;
    }

    startBtn.disabled = true;
    startBtn.innerText = "Connecting...";

    try {
      // 1. Call Backend to start custom meeting session
      const res = await fetch("http://localhost:8000/api/meetings/start_custom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_name: candidateName,
          candidate_email: candidateEmail,
          interviewer_names: interviewerName ? [interviewerName] : [],
          position: position
        })
      });

      const data = await res.json();
      const meetingId = data.meeting_id;

      // 2. Save meeting state to local storage
      chrome.storage.local.set({ meetingId, candidateName }, () => {
        showActiveSession(meetingId);
        
        // 3. Notify background script to start monitoring
        chrome.runtime.sendMessage({ type: "START_MONITORING", meetingId });
      });

    } catch (e) {
      alert("Failed to connect to backend: " + e.message);
      startBtn.disabled = false;
      startBtn.innerText = "Start Live Link";
    }
  });

  stopBtn.addEventListener('click', async () => {
    chrome.storage.local.get(['meetingId'], async (data) => {
      if (data.meetingId) {
        try {
          await fetch(`http://localhost:8000/api/meetings/${data.meetingId}/stop`, { method: "POST" });
        } catch (e) {
          console.error("Failed to stop meeting on backend:", e);
        }
      }
      
      // Clear storage
      chrome.storage.local.remove(['meetingId', 'candidateName'], () => {
        showSetupForm();
        chrome.runtime.sendMessage({ type: "STOP_MONITORING" });
      });
    });
  });

  function showActiveSession(meetingId) {
    setupForm.style.display = 'none';
    activeSession.style.display = 'block';
    sessionIdText.innerText = meetingId;
  }

  function showSetupForm() {
    setupForm.style.display = 'block';
    activeSession.style.display = 'none';
    startBtn.disabled = false;
    startBtn.innerText = "Start Live Link";
  }
});
