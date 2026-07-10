let activeMeetingId = null;
let startTime = null;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "START_MONITORING") {
    activeMeetingId = message.meetingId;
    startTime = Date.now();
    console.log(`[Background] Started monitoring for meeting: ${activeMeetingId}`);
    
    // Notify all Meet tabs to start scraping
    chrome.tabs.query({ url: "https://meet.google.com/*" }, (tabs) => {
      tabs.forEach(tab => {
        chrome.tabs.sendMessage(tab.id, { type: "ACTIVATE_MONITORING", meetingId: activeMeetingId });
      });
    });
  }

  else if (message.type === "STOP_MONITORING") {
    console.log(`[Background] Stopped monitoring meeting: ${activeMeetingId}`);
    activeMeetingId = null;
    startTime = null;
    
    // Notify all Meet tabs to stop scraping
    chrome.tabs.query({ url: "https://meet.google.com/*" }, (tabs) => {
      tabs.forEach(tab => {
        chrome.tabs.sendMessage(tab.id, { type: "DEACTIVATE_MONITORING" });
      });
    });
  }

  else if (message.type === "MEET_EVENT" && activeMeetingId) {
    // Inject timestamp if not provided (seconds since start)
    const timestamp = startTime ? (Date.now() - startTime) / 1000 : 0;
    const eventPayload = {
      event_type: message.event.event_type,
      participant_id: message.event.participant_id,
      timestamp: timestamp,
      data: message.event.data || {}
    };

    console.log("[Background] Forwarding event to backend:", eventPayload);

    // Forward event to FastAPI backend
    fetch(`http://localhost:8000/api/meetings/${activeMeetingId}/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(eventPayload)
    })
    .then(res => res.json())
    .then(data => {
      console.log("[Background] Backend response:", data);
    })
    .catch(e => {
      console.error("[Background] Failed to send event to backend:", e);
    });
  }
});
