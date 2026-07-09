# Future Meeting Adapters Design

This document details the engineering blueprint for connecting **TrueCandidate** to real server-side media streams, SDKs, and platform APIs. Due to the platform-independent `MeetingConnector` interface, these adapters can be integrated without modifying the core fusion engine.

---

## 1. Recall.ai Integration

[Recall.ai](https://www.recall.ai/) is a unified API for meeting bots (Zoom, Google Meet, MS Teams). It provides speaker-attributed real-time transcripts and raw audio/video streams.

### Architecture
```
┌───────────┐      Webhook (events)     ┌───────────────┐
│ Recall.ai │ ────────────────────────> │ TrueCandidate │
│           │ <──────────────────────── │  Recall API   │
└───────────┘    Recall Bot Control     └───────────────┘
```

### Event Mapping
1. **Participant Joined / Left**: Recall webhooks `bot.participant_joined` and `bot.participant_left`.
2. **Speaking Started / Stopped**: Extracted from Real-time Speaker Attribution audio metadata.
3. **Webcam Status**: Tracked via `video_added` / `video_removed` media stream events.
4. **Transcript**: Replaced by Recall's real-time transcription WebSocket/SSE pipeline.

---

## 2. Google Meet Integration (Server-Side)

Real-time integration with Google Meet can be achieved via the **Google Meet REST API** and **Google Cloud Pub/Sub** for event notifications.

### Architecture
```
┌─────────────┐       Pub/Sub Events      ┌───────────────┐
│ Google Meet │ ────────────────────────> │ TrueCandidate │
│   Server    │ <──────────────────────── │   GCP Admin   │
└─────────────┘       Google API Calls    └───────────────┘
```

### Implementation Details
- **Participant Tracking**: Subscribe to `spaces.spaceEvents` resource. Listen for `spaceEvents.participantJoined` and `spaceEvents.participantLeft`.
- **Calendar Matching**: Query Google Calendar API using `meetingCode` to retrieve full attendee lists, guest status, and email addresses.
- **Audio/Video Streams**: Requires Google Meet Media API (currently in developer preview) or deploying a headless Chromium bot (Puppeteer/Playwright) to join the call as a participant.

---

## 3. Zoom Meeting SDK Integration

Zoom provides a server-side **Zoom Meeting SDK** (Linux/macOS) designed to run inside Docker containers.

### Architecture
```
┌──────────────┐     Raw PCM Audio / YUV Video    ┌───────────────┐
│  Zoom SDK    │ ───────────────────────────────> │ TrueCandidate │
│ Container    │ <─────────────────────────────── │  Control API  │
└──────────────┘       C++ / NodeJS Bindings       └───────────────┘
```

### Implementation Details
- **Audio Capture**: Implement `IZoomSDKAudioRawDataDelegate`. This delegate receives unmixed raw PCM audio streams for each participant separately.
- **Video Capture**: Implement `IZoomSDKVideoRawDataDelegate` to receive raw YUV420 frame buffers per participant webcam stream.
- **Speaker Attribution**: Zoom SDK provides `userId` alongside raw audio frames, allowing native, hardware-accurate speaker attribution.

---

## 4. Microsoft Teams Integration

Teams integration uses the **Microsoft Graph Cloud Communications API** to create hosted media bots.

### Architecture
```
┌─────────────────┐      Server-Media Protocol     ┌───────────────┐
│ MS Graph Communication │ ──────────────────────────────> │ TrueCandidate │
│       Service   │ <────────────────────────────── │   Graph API   │
└─────────────────┘       REST / SignalR Channel    └───────────────┘
```

### Implementation Details
- **Hosted Media Bot**: Register a bot with Microsoft Entra ID. Use MS Graph API to create a call and invite the bot.
- **Real-time Audio**: The bot receives audio packets via the Microsoft.Skype.Bots.Media library (separate audio channel per participant).
- **Metadata**: Graph API sends `call.participants` updates for joining/leaving/mute events.

---

## 5. Web RTC & Server-Side Media Connectors (Custom Bots)

For self-hosted platforms or direct integrations (e.g., custom Jitsi, LiveKit, Twilio Video), TrueCandidate acts as a media consumer.

### LiveKit Adapter Example
```python
from livekit import rtc

class LiveKitConnector(MeetingConnector):
    def __init__(self, token: str, url: str):
        self.room = rtc.Room()
        
    async def connect(self, meeting_id: str):
        await self.room.connect(url, token)
        self.room.on("participant_connected", self._on_joined)
        self.room.on("track_subscribed", self._on_track_subscribed)
        
    def _on_track_subscribed(self, track, publication, participant):
        if track.kind == rtc.TrackKind.AUDIO:
            # Connect to Speech-to-Text transcriber
            asyncio.create_task(self._transcribe_audio(track, participant))
```
