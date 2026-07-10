# TrueCandidate Demo Video Script (5-10 Minutes)

This script outlines the flow, visual cues, and narration for a professional 5-10 minute video demonstration of the **TrueCandidate** system for the Sherlock team.

---

## Part 1: Introduction (0:00 - 1:15)

* **Visual on screen**: Live webcam of you (the presenter) OR the TrueCandidate Dashboard in its idle state.
* **Narration**:
  > *"Hi everyone, I'm presenting TrueCandidate — a production-ready prototype built for the Sherlock Internship Challenge. 
  > 
  > In live fraud detection, one of the biggest bottlenecks is ensuring we are analyzing the actual candidate's streams, rather than the interviewer's or an observer's. But real-world calls are messy. Candidates join as 'MacBook Pro', use nicknames, change display names mid-call, or join late.
  > 
  > TrueCandidate solves this by performing real-time multi-signal evidence fusion. It takes weak, noisy signals from participant actions, transcripts, and calendar data, and combines them into a high-confidence, explainable candidate prediction."*

---

## Part 2: Architecture & Technical Decisions (1:15 - 2:45)

* **Visual on screen**: Open the `README.md` file in VS Code or GitHub and zoom in on the **Mermaid Architecture Diagram**.
* **Narration**:
  > *"Before writing any code, we made a key architectural decision: **Do not build a Chrome extension or Google Meet SDK as the primary system**. 
  > 
  > Google Meet or Zoom SDKs cannot realistically run candidate identification engine logic on the client-side without facing sandboxing, security, and separate audio stream limits. 
  > 
  > Instead, we designed a **connector-based backend**. The connector's sole job is to stream normalized meeting events — like joins, webcam toggles, or transcripts. The core engine is completely platform-independent. This means we can swap in a Zoom SDK, Recall.ai bot, or Microsoft Teams connector without changing a single line of our AI logic.
  > 
  > Let's look at the flow: The Meeting Connector feeds events to our Event Normalizer. These go into the Evidence Engine, which runs 7 independent signal analyzers. The results are combined by the Bayesian Fusion Engine, smoothed by the Confidence Engine, and explained by the Explainability Engine, before streaming to the React dashboard via WebSockets."*

---

## Part 3: The 7 Signal Analyzers & Fusion (2:45 - 4:15)

* **Visual on screen**: Open code files: `backend/app/core/analyzers/name_similarity.py` and `backend/app/fusion/fusion_engine.py`.
* **Narration**:
  > *"TrueCandidate relies on 7 distinct signal analyzers to avoid single-point failure:
  > 1. **Name Similarity**: Fuzzy matches display names using Levenshtein distance and token overlaps.
  > 2. **Calendar Match**: Cross-references participants with the calendar invite guest list.
  > 3. **Speech Pattern**: Tracks speaking durations and turn-taking counts. Candidates speak the most.
  > 4. **Transcript Keyword**: Scans for self-introductions, resume references, and roles.
  > 5. **Behavioral**: Tracks webcam persistence and applies penalties for display name changes or rejoins.
  > 6. **Temporal**: Analyzes join order and response turn-taking.
  > 7. **LLM Reasoning**: Uses LLM transcript understanding to parse natural language context when ambiguity is high.
  > 
  > The **Fusion Engine** uses a weighted Bayesian odds update. We initialize each participant with a uniform prior probability. As evidence items arrive, they apply log-odds updates. This is mathematically stable and avoids overfitting. The **Confidence Engine** then applies an Exponential Moving Average (EMA) to smooth out sudden jumps, keeping the confidence curve stable."*

---

## Part 4: Live Dashboard Demo — Case 1: MacBook Pro (4:15 - 6:30)

* **Visual on screen**: Open the React Dashboard on Chrome (`http://localhost:5173`).
* **Action**: Click on Scenario 3: **"MacBook Pro Display Name"** in the sidebar.
* **Narration**:
  > *"Let's see this in action. I'll select Scenario 3: 'MacBook Pro Display Name'. 
  > 
  > Here, the candidate joins as 'MacBook Pro'. At the start, the system has no name match, so confidence is low. 
  > 
  > Watch the live transcript on the right. The interviewer asks: 'Are you Rahul Gupta?'. The candidate replies: 'Yes, sorry about that, I'm Rahul Gupta. Let me change my display name.' 
  > 
  > Instantly, the Transcript Analyzer flags the self-introduction. The candidate changes their name to 'Rahul G' — our behavioral analyzer catches the display name change and Name Similarity matches 'Rahul G' to 'Rahul Gupta'. 
  > 
  > Look at the center panel: the identified candidate switches to 'Rahul G' and the confidence line chart rises smoothly, locking in at 99% confidence. The Reasoning panel shows exactly why: name match, transcript confirmation, and webcam persistence."*

---

## Part 5: Demo Case 2: Ambiguous Identities (6:30 - 7:45)

* **Visual on screen**: In the dashboard, click Scenario 10: **"Ambiguous Identities"**.
* **Narration**:
  > *"Let's test a very hard edge case: Scenario 10. Here, we have two participants with similar names: 'Alex M' (who is an interviewer/observer) and 'A. Kumar' (the candidate, Alex Kumar). 
  > 
  > When they join, the system is highly uncertain because 'Alex' matches both names. The confidence graph shows both participants competing close to 50%.
  > 
  > As they speak, 'A. Kumar' answers the questions while 'Alex M' observes. The Speech Pattern Analyzer and Transcript Analyzer detect that 'A. Kumar' is sharing details about their PM experience. 
  > 
  > Watch the graph split: 'A. Kumar' rises to 96% confidence, while 'Alex M' decays down to 2%. Under uncertainty, the system did not guess blindly — it waited for behavioral evidence before committing."*

---

## Part 6: Headless Evaluation & Conclusion (7:45 - 9:00)

* **Visual on screen**: Switch to the terminal and run `python backend/evaluation/evaluator.py`.
* **Narration**:
  > *"To ensure reliability, we built an automated evaluation suite. It replays all 10 mock scenarios instantly to measure overall accuracy and speed.
  > 
  > As you can see, the evaluator reports **10/10 scenarios passed (100% accuracy)**. The average time to correct identification is **33 seconds**, showing how fast the fusion engine resolves ambiguity.
  > 
  > If we were deploying this to production at Sherlock tomorrow:
  > - We would use the Recall.ai connector to stream live meeting Webhooks.
  > - The core engine would feed the identified participant ID directly to Sherlock's deepfake and voice cloning microservices.
  > 
  > This makes the system scalable, robust, and entirely platform-agnostic. Thank you for your time!"*
