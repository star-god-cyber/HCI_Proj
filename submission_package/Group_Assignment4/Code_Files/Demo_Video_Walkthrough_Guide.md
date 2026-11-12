# CS 435 Assignment 4: Demo Video & Viva Walkthrough Script (5–7 Minutes)

**Course:** CS 435 Human-Computer Interaction  
**Project:** High-Fidelity AI Interview Practice System  
**Institution:** Indian Institute of Technology, Gandhinagar  

---

## 📹 Video Recording Guidelines (Screen + Microphone)
- **Target Duration:** 4 to 6 minutes (strictly under 7 minutes).
- **Resolution:** 1080p (1920x1080) at 30 fps.
- **Audio:** Clear microphone voice input.
- **Tools for Recording:** OBS Studio, Windows Xbox Game Bar (`Win + Alt + R`), or Zoom screen recording.

---

## 🎬 Timed Demonstration Script

### Part 1: Introduction & System Overview (0:00 – 1:00)
- **On Screen:** Start at `http://127.0.0.1:8000/` showing the Home Screen.
- **Narrate:**
  > "Hello everyone. Welcome to our demonstration of the High-Fidelity AI Interview Practice System for CS 435. Self-directed interview preparation often traps students in evaluative anxiety and vague feedback. In this project, we designed and built a zero-cost system implementing two complementary interaction paradigms:
  > 1. Prototype A: Instructional practice with inspectable rubric scoring and guided metacognitive reflection.
  > 2. Prototype B: Conversational realism with an animated avatar, real-time voice turns, and adaptive follow-up questions."
- **Action:** Point out the mode cards on the home screen and the persistent top-left `🏠 Home` button.

---

### Part 2: Prototype A — Guided Instructional Cycle (1:00 – 3:00)
- **On Screen:** Click **"Feedback-Based Interview Practice"** (`screen-a1` $\rightarrow$ `screen-a2`).
- **Setup:** Select **UX Research Intern** role, **Behavioral (STAR)** type, **Medium** difficulty. Click **"Start Practice"** (`screen-a3`).
- **Narrate:**
  > "Here on Screen A3, the candidate can listen to the question using natural text-to-speech, and respond using real-time speech-to-text dictation."
- **Action:**
  - Click `🔊 Listen to Question`. Notice the synthesized voice reading the prompt aloud.
  - Click `🎤 Start Speaking` and dictate an initial answer:
    > *"In my previous project, we wanted to improve user onboarding. I conducted some usability interviews and suggested UI improvements."*
  - Notice the live audio equalizer waveform and real-time interim transcript preview.
  - Click `Submit Answer` $\rightarrow$ navigates to `screen-a4` (Rubric Feedback).
- **Inspect Feedback:**
  - Point out the 4 inspectable dimensions: Relevance (8/10), Specificity (5/10), Evidence & Outcome (4/10), Structure & Clarity (7/10).
  - Click **"Why This Feedback?"** (`screen-a5` modal).
  - Highlight the exact sentence citations:
    > "Notice the system pinpoints why points were deducted: lack of quantifiable metrics in Evidence and missing concrete methodologies in Specificity. It also presents a benchmark model STAR response."
  - Close modal $\rightarrow$ click **"Reflect & Retry"** (`screen-a6`).
- **Metacognitive Reflection & Retry:**
  - On `screen-a6`, demonstrate the reflection step:
    > *"What would you change? I need to quantify my usability test size and specify the conversion increase."*
  - Click **"Proceed to Retry"** (`screen-a7`).
  - Dictate an improved answer:
    > *"In my UX internship at EduTech, 40% of signups dropped off on step 2. I led 12 think-aloud interviews and usability tests, redesigned the navigation flow using Figma, and validated it with an A/B test. This increased 7-day user activation by 35%."*
  - Click `Submit Retry Answer` $\rightarrow$ navigates to `screen-a8` (Comparison Diff).
  - Highlight the **+4.0 Evidence improvement delta** and side-by-side attempt comparison.

---

### Part 3: Prototype B — Conversational Voice Simulation (3:00 – 4:45)
- **On Screen:** Click `🏠 Home` at the top left $\rightarrow$ select **"Interview Simulation"** $\rightarrow$ click **"Start Interview Simulation"** (`screen-b3`).
- **Simulation Room:**
  - Point out Dr. Marcus Vance's animated avatar with glowing halo rings and equalizer bars.
  - Show how Dr. Vance speaks the behavioral opening question aloud.
  - Click `🎤 Speak Your Answer` and speak:
    > *"I handled a major project conflict when our backend engineer missed a deadline. I stepped in and organized a daily standup to align our deliverables."*
  - Click `Finish Turn`.
  - Notice Dr. Vance transitions to **"Thinking..."** and generates a **dynamic adaptive follow-up question** challenging unaddressed aspects:
    > *"How specifically did you convince the backend engineer to accept daily standups without escalating the conflict to management?"*
  - Speak follow-up answer and finish turn.
  - Click `End Interview & View Debrief` $\rightarrow$ navigates to `screen-b6` (Diagnostic Debrief).
  - Point out the question-by-question breakdown, overall performance grade, and longitudinal tracking.

---

### Part 4: Longitudinal Progress Tracking & Reset (4:45 – 5:30)
- **On Screen:** Click **"View Longitudinal Progress"** (`screen-a9`).
- **Demonstrate:**
  - Show the 5-parameter time-series graph: Overall, Relevance, Specificity, Evidence, Structure plotted across attempts.
  - Point out the **"Reset All Progress Data"** button (`POST /api/progress/reset`) to demonstrate zero-data retention on demand.

---

### Part 5: Empirical Usability Results & Ethical Protections (5:30 – 6:15)
- **Narrate:**
  > "In our formal laboratory usability evaluation with 6 student participants at IIT Gandhinagar:
  > - Mean System Usability Scale (SUS) score: 90.4 / 100 (Grade A+, 96th percentile).
  > - 100% task completion rate across all participants.
  > - Statistically significant +4.0 point gain on STAR Evidence upon guided retry.
  > - 100% zero raw audio storage, local browser sandbox STT/TTS execution, and full anonymization P01–P06."

---

### Part 6: Conclusion (6:15 – 6:30)
- **Wrap-up:**
  > "Thank you. Our prototype is fully functional, zero-cost, thoroughly tested with 45 unit tests, and ready for viva questions."
