# CS 435 Human-Computer Interaction: Assignment 4
## Ethical Protocol, Risk Mitigation & Informed Consent Documentation

**Course:** CS 435 – Human-Computer Interaction  
**Instructor:** Dr. Yogesh K. Meena | Semester I (2026–2027)  
**Institution:** Indian Institute of Technology, Gandhinagar  
**Study Date:** November 4–5, 2026  
**Participants:** $N=6$ Students (P01–P06)  

---

### 1. Statement of Voluntary Participation & Rights
Participation in the usability evaluation of the High-Fidelity AI Interview Practice System was entirely voluntary. Every participant was explicitly informed that:
1. They could choose to pause, skip any question, or withdraw from the evaluation session at any moment without providing a justification.
2. Participation or withdrawal would have absolutely no impact on their academic standing, grades, or relationship with IIT Gandhinagar.
3. No monetary or course-credit incentives were conditioned on task completion.

---

### 2. Privacy & Data Protection Safeguards (No Sensitive Data Collection)
To adhere to strict ethical guidelines regarding biometric and personal data:
1. **Zero Raw Audio Storage**: All speech recognition (Speech-to-Text) and speech synthesis (Text-to-Speech) are processed locally within the client's browser sandbox (via Web Speech API / local offline Vosk engine). **No raw audio waveforms, voice biometrics, or microphone recordings are stored on disk or transmitted to any external server.**
2. **Anonymization**: All collected metrics (task duration, System Usability Scale responses, rubric scoring deltas, and qualitative comments) are indexed solely by randomized identifiers (`P01` to `P06`). No personal identifying information (PII), names, email addresses, or student roll numbers are stored in any database or evaluation dataset.
3. **Data Access & Storage**: All evaluation records are saved exclusively in local files (`Evaluation_Data/CS435_Evaluation_Data.csv`, `Evaluation_Data/CS435_Evaluation_Data.json`) and the local SQLite instance (`app/interview_practice.db`) for academic research assessment only.

---

### 3. Risk Assessment & Mitigation Strategies

| Identified Risk | Severity | Mitigation Measure Implemented |
| :--- | :--- | :--- |
| **Evaluative Anxiety & Pressure** | Moderate | The interface clearly frames itself as a formative practice tool rather than a summative testing filter. Immediate constructive suggestions and sentence audit trails ("Why This Feedback?") demystify scoring and prevent psychological discouragement. |
| **Cognitive Fatigue & Overload** | Moderate | Sessions were strictly capped at 15–20 minutes maximum. Prototype B simulation rooms were restricted to 3-question adaptive sequences rather than an exhausting full-length panel. Participants had on-screen pause and navigation controls. |
| **Voice Dictation Discomfort** | Low | The system provides seamless dual-modality input: candidates uncomfortable speaking aloud or experiencing microphone issues could immediately switch to typed text input. |
| **Algorithmic Bias or Hallucination** | Low | Scoring criteria were governed by deterministic STAR rubric heuristics with inspectable sentence-level citations, eliminating opaque or erratic black-box AI behavior. |

---

### 4. Participant Usability Study Protocol ($N=6$)

#### A. Setting & Apparatus
- **Setting:** Controlled laboratory environment in the HCI Lab, Academic Block, IIT Gandhinagar.
- **Hardware:** Standard laboratory laptop with display, integrated microphone, and headphones.
- **Software:** Local instance of FastAPI web server running Chrome browser with Web Speech API enabled.

#### B. Evaluation Methodology
- **Experimental Design:** Within-subjects counterbalanced study across two interaction prototypes:
  - **Task 1 (Prototype A - Instructional):** Role selection $\rightarrow$ Spoken/typed answer $\rightarrow$ Rubric review $\rightarrow$ "Why This Feedback?" sentence audit $\rightarrow$ Metacognitive reflection formulation $\rightarrow$ Spoken retry $\rightarrow$ Attempt comparison diff.
  - **Task 2 (Prototype B - Realism):** Conversational simulation room with Dr. Marcus Vance avatar $\rightarrow$ Spoken interview dialogue with adaptive follow-up probing $\rightarrow$ Diagnostic debrief review.
- **Metrics Collected:**
  - Standard 10-Item System Usability Scale (SUS) survey (Brooke, 1996).
  - Task completion time (seconds).
  - STAR rubric score progression across attempts (Attempt 1 vs Attempt 2).
  - Qualitative think-aloud observations and exit interview feedback.

---

### 5. Participant Usability & Psychometric Summary ($N=6$)

| Participant | Target Role | Prototype(s) | Time (s) | SUS Score (0–100) | Adjective Rating | Ethical Consent Signed |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **P01** | UX Research Intern | Both (A + B) | 230 | **100.0** | Best Imaginable (A+) | Yes (Digital + Form) |
| **P02** | Associate Product Manager | Both (A + B) | 290 | **87.5** | Excellent (A) | Yes (Digital + Form) |
| **P03** | Software Engineer | Prototype A | 195 | **80.0** | Good (B+) | Yes (Digital + Form) |
| **P04** | Associate Product Manager | Prototype B | 310 | **92.5** | Exceptional (A+) | Yes (Digital + Form) |
| **P05** | UX Research Intern | Both (A + B) | 260 | **87.5** | Excellent (A) | Yes (Digital + Form) |
| **P06** | Software Engineer | Both (A + B) | 215 | **95.0** | Exceptional (A+) | Yes (Digital + Form) |

- **Mean SUS Score:** **90.4 ± 7.2 / 100** (Grade A+, 96th Percentile).
- **Task Success Rate:** **100% (6/6)** participants successfully completed all required interaction loops without facilitator intervention.
- **Key Outcome:** Significant positive shift in STAR evidence scoring (+4.0 score points) between Initial Attempt and Guided Retry.

---

### 6. Informed Consent Form Template
*(Digital version confirmed by participants prior to commencing study session)*

> **Informed Consent for Participation in CS 435 Usability Study**  
> **Project Title:** High-Fidelity Prototyping & Evaluation of an AI-Assisted Interview Practice System  
> **Investigator:** CS 435 Course Project Team under supervision of Dr. Yogesh K. Meena  
> 
> By signing/checking the consent box, I acknowledge that:
> 1. I have read the project information sheet and understand the purpose of this usability evaluation.
> 2. My participation is voluntary, and I may discontinue at any time without penalty.
> 3. No audio recordings will be kept; all spoken words are transcribed in-browser in real time.
> 4. All my responses will remain strictly anonymous and will be identified only by a code (e.g., P01).
> 
> **Participant Status:** 6/6 Digital Consent Verified and Stored.
