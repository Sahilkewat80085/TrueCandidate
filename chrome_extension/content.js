let activeMeetingId = null;
let intervalId = null;
let previousParticipants = new Map(); // name/id -> { webcamOn: false }

console.log("[TrueCandidate] Content script loaded — awaiting activation.");

// Listen to messages from popup or background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "ACTIVATE_MONITORING") {
    activeMeetingId = message.meetingId;
    console.log(`[TrueCandidate] Monitoring activated for meeting: ${activeMeetingId}`);
    startScraping();
  } else if (message.type === "DEACTIVATE_MONITORING") {
    console.log("[TrueCandidate] Monitoring deactivated.");
    stopScraping();
  }
});

// Auto-activate on load if storage already has active meeting
chrome.storage.local.get(['meetingId'], (data) => {
  if (data.meetingId) {
    activeMeetingId = data.meetingId;
    console.log(`[TrueCandidate] Auto-restoring monitoring session: ${activeMeetingId}`);
    startScraping();
  }
});

function startScraping() {
  if (intervalId) clearInterval(intervalId);
  previousParticipants.clear();
  
  // Scrape DOM every 2.5 seconds
  intervalId = setInterval(scrapeMeetDOM, 2500);
  scrapeMeetDOM(); // Run once immediately
}

function stopScraping() {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
  }
  activeMeetingId = null;
  previousParticipants.clear();
}

/**
 * Scrapes Google Meet DOM for participant names and webcam states.
 * Translates findings into normalized events (join, leave, camera on/off).
 */
function scrapeMeetDOM() {
  if (!activeMeetingId) return;

  const currentParticipants = new Map();

  // Selector Strategy:
  // Google Meet represents participant video tiles by elements with data-participant-id or data-requested-participant-id attributes.
  const tiles = document.querySelectorAll('[data-participant-id], [data-requested-participant-id], div[role="listitem"]');

  tiles.forEach((tile) => {
    // 1. Try to find the participant name inside this tile
    // Meet usually puts the name in a div with a specific font class or attribute
    let name = "";
    
    // Check elements with typical Meet name containers
    const nameEl = tile.querySelector('[data-self-name], div[dir="auto"], span[dir="auto"]');
    if (nameEl) {
      name = nameEl.getAttribute('data-self-name') || nameEl.textContent.trim();
    }

    // Clean up name
    if (!name || name.includes(":") || name.length > 50 || name === "You") {
      // Look at text content for other indicators
      const divs = tile.querySelectorAll('div');
      for (const d of divs) {
        if (d.childNodes.length === 1 && d.childNodes[0].nodeType === Node.TEXT_NODE) {
          const val = d.textContent.trim();
          if (val && val.length > 2 && val.length < 35 && !val.includes("Presentation") && !val.includes("Screen")) {
            name = val;
            break;
          }
        }
      }
    }

    if (!name) return;

    // 2. Check if webcam is on
    // If there is a visible video element inside this tile, the webcam is active
    const video = tile.querySelector('video');
    const webcamOn = !!(video && video.srcObject !== null && video.readyState >= 2);

    // Save state
    const pid = name.toLowerCase().replace(/[^a-z0-9]/g, "_");
    currentParticipants.set(pid, {
      display_name: name,
      webcamOn: webcamOn
    });
  });

  // Fallback: If no tiles found, search for any video tags and parent tags to find names
  if (currentParticipants.size === 0) {
    const videos = document.querySelectorAll('video');
    videos.forEach((video, index) => {
      // Find ancestor div that has text content (often the participant tile)
      let ancestor = video.parentElement;
      let name = `Participant_${index + 1}`;
      
      while (ancestor && ancestor !== document.body) {
        const text = ancestor.textContent.trim();
        if (text && text.length > 2 && text.length < 40) {
          name = text.split('\n')[0].trim();
          break;
        }
        ancestor = ancestor.parentElement;
      }
      
      const pid = name.toLowerCase().replace(/[^a-z0-9]/g, "_");
      currentParticipants.set(pid, {
        display_name: name,
        webcamOn: true
      });
    });
  }

  // --- Compare with previous state to emit events ---

  // 1. Detect Joins and Webcam Toggles
  currentParticipants.forEach((current, pid) => {
    const prev = previousParticipants.get(pid);

    if (!prev) {
      // Participant Joined
      emitEvent("participant_joined", pid, {
        display_name: current.display_name
      });

      // If they joined with webcam on
      if (current.webcamOn) {
        emitEvent("webcam_enabled", pid);
      }
    } else {
      // Check Webcam Toggle
      if (current.webcamOn && !prev.webcamOn) {
        emitEvent("webcam_enabled", pid);
      } else if (!current.webcamOn && prev.webcamOn) {
        emitEvent("webcam_disabled", pid);
      }
    }
  });

  // 2. Detect Leaves
  previousParticipants.forEach((prev, pid) => {
    if (!currentParticipants.has(pid)) {
      emitEvent("participant_left", pid);
    }
  });

  // Save current state for next tick
  previousParticipants = currentParticipants;
}

/**
 * Sends a meeting event to the background script.
 */
function emitEvent(eventType, participantId, data = {}) {
  const event = {
    event_type: eventType,
    participant_id: participantId,
    data: data
  };

  console.log(`[TrueCandidate] Emitting event: ${eventType} for ${participantId}`, data);
  
  chrome.runtime.sendMessage({
    type: "MEET_EVENT",
    event: event
  });
}
