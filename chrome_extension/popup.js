document.addEventListener('DOMContentLoaded', () => {
  const setupForm = document.getElementById('setup-form');
  const activeSession = document.getElementById('active-session');
  const startBtn = document.getElementById('start-btn');
  const stopBtn = document.getElementById('stop-btn');
  const sessionIdText = document.getElementById('session-id');

  // Input elements
  const candidateNameInput = document.getElementById('candidate-name');
  const candidateEmailInput = document.getElementById('candidate-email');
  const interviewerNameInput = document.getElementById('interviewer-name');
  const positionInput = document.getElementById('position');

  // Check if session already running
  chrome.storage.local.get(['meetingId', 'candidateName'], (data) => {
    if (data.meetingId) {
      showActiveSession(data.meetingId);
    } else {
      // Auto-fetch calendar info based on current Meet tab URL
      autoFetchCalendarDetails();
    }
  });

  // Automatically fetches candidate info from backend using Meet code
  function autoFetchCalendarDetails() {
    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
      const tab = tabs[0];
      if (!tab || !tab.url) return;

      try {
        const url = new URL(tab.url);
        if (url.hostname === "meet.google.com") {
          // Meet code is the path, e.g. "abc-defg-hij" (remove leading slashes)
          const code = url.pathname.replace(/^\/+/g, '').split('?')[0];
          
          if (code && code !== "landing" && code.match(/^[a-z]{3}-[a-z]{4}-[a-z]{3}$/)) {
            console.log(`[Extension] Detected Google Meet code: ${code}. Fetching calendar...`);
            
            const res = await fetch(`http://localhost:8000/api/meetings/calendar/${code}`);
            if (res.ok) {
              const cal = await res.json();
              console.log("[Extension] Auto-fetched calendar details:", cal);
              
              // Pre-fill inputs automatically
              candidateNameInput.value = cal.candidate_name || "";
              candidateEmailInput.value = cal.candidate_email || "";
              interviewerNameInput.value = cal.interviewer_names ? cal.interviewer_names.join(', ') : "";
              positionInput.value = cal.position || "";
            }
          }
        }
      } catch (e) {
        console.error("[Extension] Failed to auto-fetch calendar details:", e);
      }
    });
  }

  startBtn.addEventListener('click', async () => {
    const candidateName = candidateNameInput.value;
    const candidateEmail = candidateEmailInput.value;
    const interviewerName = interviewerNameInput.value;
    const position = positionInput.value;

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
          interviewer_names: interviewerName ? interviewerName.split(',').map(n => n.trim()) : [],
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
    autoFetchCalendarDetails(); // Refetch details for the tab
  }
});
