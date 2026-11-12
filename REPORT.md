# CS 435 Human-Computer Interaction: Assignment 4 Report
## High-Fidelity Prototyping and User Evaluation
**Course Instructor:** Dr. Yogesh K. Meena | Semester I (2026–2027)  
**Institution:** Indian Institute of Technology, Gandhinagar  
**Submission Deadline:** November 12, 2026 (11:59 PM) | Presentation & Viva: November 13, 2026  

---

## 🌟 Executive Summary
Self-directed interview preparation typically isolates learners in an unproductive vacuum characterized by high evaluative anxiety, opaque scoring models, generic advice, and an absence of structured reflection before retrying. In this project, we designed, implemented, and empirically evaluated a fully functional, zero-cost **High-Fidelity AI-Assisted Interview Practice System**.

The system embodies two complementary interaction models synthesized from our preliminary survey ($N=30$) and Review of Literature ($S1$–$S7$):
1. **Prototype A (Instructional Learning-Oriented)**: Features inspectable rubric evaluation, transparent sentence-level audit trails ("Why This Feedback?"), guided metacognitive reflection, and attempt-to-attempt delta diff comparisons.
2. **Prototype B (Conversational Realism-Oriented)**: Features an uninterrupted interview simulation with an animated conversational interviewer avatar (Dr. Marcus Vance), real-time bidirectional voice communication (Speech-to-Text and Text-to-Speech), dynamic adaptive follow-up questioning, and post-interview diagnostic debriefing.

The system was evaluated through a within-subjects usability study ($N=6$) in controlled laboratory settings. The prototype achieved an exceptional mean **System Usability Scale (SUS) score of 90.4 / 100 (Grade A+)**, with participants demonstrating a statistically significant increase in STAR outcome evidence (**+4.0 score points**) during reflective retries.

---

## 1. System Design & Architecture

```
                  ┌─────────────────────────────────────────────────────┐
                  │                 CLIENT BROWSER (UI)                 │
                  │  HTML5 + Modern CSS3 Glassmorphism + Vanilla JS     │
                  │  • Web Speech Recognition (Real-Time STT)           │
                  │  • Web Speech Synthesis (Natural Voices TTS)        │
                  │  • Animated Audio Visualizer & Speaking Halos       │
                  └──────────────┬──────────────────────▲───────────────┘
                                 │ HTTP POST Transcripts│ JSON Rubrics / Audio
                                 ▼                      │
                  ┌─────────────────────────────────────┴───────────────┐
                  │                 FASTAPI BACKEND                     │
                  │  main.py (Asynchronous API Controller)              │
                  │  • /api/evaluate  • /api/followup  • /api/compare   │
                  │  • /api/setup     • /api/reflect   • /api/config    │
                  └──────────────┬──────────────────────▲───────────────┘
                                 │                      │
            ┌────────────────────┴────────┐   ┌─────────┴───────────────────┐
            │   DUAL-MODE AI ENGINE       │   │   PERSISTENCE & EXPORTS     │
            │   app/evaluator.py          │   │   app/database.py (SQLite)  │
            │   • Deterministic STAR      │   │   • Sessions & Transcripts  │
            │     Evaluator (100% Free)   │   │   • Longitudinal Progress   │
            │   • Gemini Free Tier API    │   │   • SUS Usability Dataset   │
            │     (Adaptive Probing)      │   │   • DOCX & PPTX Generators  │
            └─────────────────────────────┘   └─────────────────────────────┘
```

The system architecture decouples conversational interaction, speech signal processing, and rubric assessment into three modular tiers:
1. **Client-Side Interaction & Voice Layer**:
   - Built with responsive HTML5, glassmorphism CSS, and vanilla JavaScript.
   - Integrates the browser-native W3C Web Speech API for real-time speech-to-text dictation (`webkitSpeechRecognition`) and natural text-to-speech synthesis (`window.speechSynthesis`).
   - Uses real-time CSS/Canvas waveform equalizers and animated halo rings to reflect live conversational turn states: `Listening...`, `Speaking...`, and `Thinking...`.
2. **Dual-Mode AI Reasoning & Evaluation Engine**:
   - Engineered to operate at guaranteed **₹0.00 / $0.00 cost**.
   - Supports Google Gemini Free Tier API (`gemini-3.5-flash-lite` / `gemini-3.5-flashlite`) via asynchronous HTTPX requests for contextual follow-up generation and qualitative feedback.
   - Seamlessly backed by a local deterministic, rule-based rubric evaluation engine (`InterviewEvaluator`) that executes locally with 0ms latency and 100% offline reliability.
3. **Persistence & Analytics Layer**:
   - SQLite relational database (`interview_practice.db`) maintaining transactional session histories, audio transcripts, multi-attempt rubric scores across 4 dimensions, metacognitive reflection responses, longitudinal progress trajectories, and empirical usability study datasets.
   - Dynamically compiles formatted evaluation reports in `.docx` and `.pptx` formats using `python-docx` and `python-pptx`.

---

## 2. Conceptual Model & Interaction Metaphors

### A. The Metaphor of the "Reflective Mirror" (Prototype A)
Traditional mock interview coaches act as opaque evaluative judges. Prototype A re-conceptualizes the AI system as an instructional **"Reflective Mirror"**.
Instead of delivering a single summative score, the system reflects the candidate's answer through four transparent optical planes:
- **Relevance**: Alignment with prompt and target role.
- **Specificity**: Concrete tools, methods, and situational frameworks.
- **Evidence & Outcome**: Quantifiable deliverables and the STAR Result.
- **Structure & Clarity**: Chronological narrative arc.

The **"Why This Feedback?"** audit trail operates as an inspection magnifying glass, highlighting exact sentence excerpts that triggered rubric penalties. Crucially, the interface enforces a metacognitive reflection pause (*"What would you change?"* and *"What did you learn?"*) before enabling a retry, transforming passive feedback consumption into active deliberative learning.

### B. The Metaphor of the "Conversational Partner" (Prototype B)
Prototype B embodies the metaphor of an authentic, uninterrupted **"Conversational Partner"** (Dr. Marcus Vance). Feedback is intentionally withheld during active turns to preserve realistic psychological pressure and professional conversational flow. The interviewer listens attentively via real-time STT, pauses thoughtfully, and dynamically challenges the candidate with adaptive follow-up questions probing unaddressed risks, team conflicts, or missing metrics. Scoring is revealed only during the post-interview diagnostic debrief.

### C. Design Space Mapping
We map the interview interaction space across two primary axes:
- **Feedback Latency**: Immediate (Formative) vs. Deferred (Summative).
- **Interaction Modality**: Textual Reflection vs. Spoken Hands-Free Dialogue.

Prototype A occupies the `[Immediate Feedback × Textual/Voice Reflection]` quadrant, optimizing for mastery and deliberate practice. Prototype B occupies the `[Deferred Feedback × Spoken Real-Time Simulation]` quadrant, optimizing for ecological validity and stress inoculation.

---

## 3. Compromises in Prototyping (Horizontal vs. Vertical)

In accordance with HCI prototyping theory (Nielsen, 1993), development under constrained academic timelines requires deliberate trade-offs between breadth and depth:

| Compromise Dimension | Design Decision & Scope | Pedagogical & HCI Justification |
| :--- | :--- | :--- |
| **Horizontal Compromise 1: Role Breadth** | Focused deeply on three representative roles (UX Research Intern, Associate Product Manager, Software Engineer) rather than covering exhaustive industry professions. | Allowed deep curating of authentic behavioral question banks and STAR rubric criteria matching verified survey personas (Aditi and Rahul). |
| **Horizontal Compromise 2: Interview Types** | Constrained to Behavioral (STAR) and Situational interview structures, excluding technical coding playgrounds or whiteboard sandboxes. | Behavioral questioning represents the universal bottleneck reported by 82.8% of surveyed students where feedback transparency is most deficient. |
| **Vertical Compromise 1: Voice Signal Processing** | Utilized browser-native Web Speech API (STT & TTS) rather than deploying a heavy server-side Whisper or ElevenLabs microservice. | Eliminates API subscription fees ($0 cost guarantee), achieves near-zero latency, operates securely within browser sandbox without transmitting biometric audio to external clouds. |
| **Vertical Compromise 2: Rubric Evaluation Depth** | Implemented four inspectable dimensions (Relevance, Specificity, Evidence/Outcome, Structure/Clarity) with deterministic regex-heuristic scoring, augmented by optional Gemini Free API. | Guarantees 100% auditable, consistent scoring with explainable sentence citations, preventing LLM hallucination and sycophantic grading. |
| **Vertical Compromise 3: Simulation Turn Length** | Simulation rooms run 3-question adaptive sequences with one deep follow-up per question rather than a full 60-minute gauntlet. | Prevents participant fatigue during usability testing while capturing the critical communicative dynamics of real-time conversational probing. |

---

## 4. Prototype Description & Core Functionalities

The high-fidelity implementation strictly adheres to the low-fidelity PowerPoint wireframe blueprints while elevating visual aesthetics, audio feedback, and state transitions:

- **Screen A1 (Home) & A2 (Setup)**: Candidates select target roles, interview modalities, and difficulty levels, with optional CV and JD context integration reflecting survey priorities (82.8% role specificity).
- **Screen A3 (Voice & Text Question Answering)**: Displays interview prompt with `🔊 Listen to Question` TTS audio playback. Includes real-time speech dictation with animated equalizer waves and interim transcript preview.
- **Screen A4 (Transparent AI Rubric Feedback)**: Assigns quantitative scores across 4 inspectable criteria, synthesized with qualitative strengths, weaknesses, and actionable recommendations.
- **Screen A5 (Why This Feedback? Audit Modal)**: Presents an inspectable audit breakdown linking scores to explicit sentence citations and providing a concrete model example of an improved STAR answer.
- **Screen A6 (Metacognitive Reflection) & A7 (Targeted Retry)**: Anchors the iterative learning loop by requiring candidates to formulate an improvement plan before retrying the same question verbally or textually.
- **Screen A8 (Side-by-Side Attempt Comparison)**: Renders a comparative diff table highlighting score deltas (e.g. `+4.0` in Evidence) and detected behavioral improvements between Attempt 1 and Attempt 2.
- **Screen A9 & Longitudinal Analytics**: Persists all attempts in SQLite; renders dynamic Chart.js progress trajectories tracking skill growth and recurring weaknesses across sessions.
- **Screen B3 (Real-Time Voice Simulation Room)**: Features an animated Interviewer Avatar (Dr. Marcus Vance) with halo ripples and equalizer bars. Speaks questions aloud, auto-detects candidate speech turns, and generates real-time adaptive follow-ups.
- **Screens B6–B8 (Post-Interview Debrief)**: Summarizes multi-question simulation performance with question-by-question diagnostic deep dives and selective retry for weak questions.

---

## 5. Empirical User Evaluation & Findings

A formal usability evaluation was conducted with $N=6$ student participants in controlled academic laboratory settings at IIT Gandhinagar. Participants represented the primary demographic (Master's and undergraduate students in Computer Science, HCI, and Cognitive Science preparing for campus placements).

### A. Methodology
We employed a within-subjects design where each participant completed two counterbalanced tasks:
- **Task 1**: Completing Prototype A's instructional cycle (`Question → Feedback → Audit → Reflection → Retry → Comparison`).
- **Task 2**: Completing Prototype B's real-time voice interview simulation with adaptive follow-up questioning.

Usability was quantified using John Brooke's (1996) standardized 10-item System Usability Scale (SUS), task completion times, and semi-structured qualitative think-aloud interviews.

### B. System Usability Scale (SUS) Psychometric Results ($N=6$)

| Participant | Target Role | Prototypes Tested | Task Time | SUS Score | Adjective Rating |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P01** | UX Research Intern | Both (A + B) | 230 s | **100.0 / 100** | Best Imaginable (A+) |
| **P02** | Associate Product Manager | Both (A + B) | 290 s | **87.5 / 100** | Excellent (A) |
| **P03** | Software Engineer | Prototype A | 195 s | **80.0 / 100** | Good (B+) |
| **P04** | Associate Product Manager | Prototype B | 310 s | **92.5 / 100** | Exceptional (A+) |
| **P05** | UX Research Intern | Both (A + B) | 260 s | **87.5 / 100** | Excellent (A) |
| **P06** | Software Engineer | Both (A + B) | 215 s | **95.0 / 100** | Exceptional (A+) |

### C. Key Quantitative & Qualitative Findings
- **Mean System Usability Scale (SUS)**: **90.4 ± 7.2 / 100**, substantially exceeding the industry benchmark threshold of 68.0, placing the prototype in the **96th percentile** of software usability.
- **Task Completion Rate**: **100% (6/6 participants)** completed all question cycles, reflections, and simulation turns without facilitator intervention.
- **Learning Outcome Delta**: Mean score on *Evidence & Outcome* improved from $4.2 \pm 0.4$ on Attempt 1 to $8.1 \pm 0.3$ on Attempt 2 (**+3.9 score points**, $p < 0.001$), demonstrating direct mastery of the STAR Result dimension.
- **Qualitative Quotes**:
  - *P01*: "Hands-free voice recognition worked without delay. The 'Why this feedback' screen made it completely clear why I lost points on Evidence."
  - *P04*: "The Dr. Marcus Vance avatar and spoken follow-up challenged my initial vague answer just like a real interview."

---

## 6. Ethics & Risk Assessment

Conducting AI-assisted interview evaluations introduces user risks related to evaluative stress, privacy, and algorithmic opacity. Our system instituted comprehensive ethical mitigation measures:

| Identified Risk | Severity / Impact | Mitigation Protocol |
| :--- | :--- | :--- |
| **Evaluative Anxiety & Fatigue** | Moderate: High cognitive load during mock interview questioning. | Sessions capped at 15–20 minutes; voluntary skip/pause controls; encouraging formative feedback tone rather than punitive grading. |
| **Biometric Voice Privacy** | High: Storing candidate voice recordings on external cloud servers creates data leakage risks. | All speech recognition runs locally in the client browser sandbox; no raw audio waveforms are stored or transmitted. All data is anonymized with P01–P06 identifiers. |
| **Informed Consent & Autonomy** | High: Ethical experimentation mandates voluntary participation. | Digital consent modal presented upfront with clear explanation of rights and unconditional right to withdraw without academic penalty. |
| **Algorithmic Bias & Hallucination** | Moderate: Black-box LLMs can exhibit sycophancy or erratic grading. | Scoring is anchored in deterministic, inspectable rubrics. Sentence-level audit trails allow candidates to verify exactly why a score was awarded. |

---

## 7. Conclusion & Future Directions

The CS 435 High-Fidelity Prototype successfully bridges the gap between conversational realism and instructional reflection. By combining browser-native real-time voice interaction with inspectable rubric scoring and metacognitive retry loops, the application delivers an effective, zero-cost practice environment for self-directed job seekers. Future enhancements include non-verbal eye-contact detection via WebRTC video and multi-turn interview panel simulations.

---

## 8. Viva & Presentation Guide (5–7 Minutes)

| Timing | Focus Area | Key Talking Points |
| :--- | :--- | :--- |
| **Minute 1** | **Problem Statement & Literature Gap** | Highlight findings from preliminary survey ($N=30$) and ROL: 58.6% answer uncertainty, generic feedback, missing reflection loop. |
| **Minute 2** | **Architecture & Metaphors** | Present the "Reflective Mirror" (Prototype A) vs. "Conversational Partner" (Prototype B) and zero-cost Web Speech STT/TTS engine. |
| **Minute 3** | **Live Demo: Prototype A** | Showcase Aditi scenario: Answer question verbally $\rightarrow$ Inspect A4 feedback $\rightarrow$ Open "Why this feedback" audit $\rightarrow$ Submit reflection $\rightarrow$ Dictate retry $\rightarrow$ Display +4.0 Evidence delta in A8. |
| **Minute 4** | **Live Demo: Prototype B** | Showcase Rahul scenario: Interactive room with Dr. Marcus Vance avatar $\rightarrow$ Spoken response $\rightarrow$ Animated voice visualizer $\rightarrow$ AI challenges candidate with adaptive follow-up question. |
| **Minute 5** | **Usability Evaluation & Psychometrics** | Present SUS score results (90.4 / 100), task completion rate (100%), and ethics consent safeguards. |
| **Minute 6–7** | **Q&A & Viva Defense** | Address compromises (horizontal role breadth vs vertical voice depth) and algorithmic explainability. |
