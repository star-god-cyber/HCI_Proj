# Self-Directed AI-Assisted Interview Practice Interface (CS 435)
> **CS 435 Human-Computer Interaction: Assignment 4 — High-Fidelity Prototyping & User Evaluation**  
> Indian Institute of Technology, Gandhinagar | Instructor: Dr. Yogesh K. Meena

---

## 🌟 Overview & Key Enhancements (Assignment 4)

This repository contains the complete, working **High-Fidelity Prototype** and empirical usability evaluation suite built from the Task 2 low-fidelity wireframes (`CS435_Task2_Low_Fidelity_Prototype_Wireframes.pptx`).

### 🎙️ 1. Real-Time Bidirectional Voice Communication ($0.00 Free Tier)
- **Speech-to-Text (STT)**: Native Web Speech Recognition API with streaming interim transcription, microphone status badges (`🔴 Listening...`), and animated audio equalizer wave bars.
- **Text-to-Speech (TTS)**: Native Web Speech Synthesis with natural system voices (Google/Microsoft), configurable speech rate (0.8x–1.3x), pitch controls, and an animated AI Interviewer Avatar (`Dr. Marcus Vance`) with radiating halo ripples.
- **Echo Prevention**: Automatic turn-taking coordination that mutes candidate audio capture while the system is speaking.

### 🧠 2. Dual-Mode AI Reasoning & Adaptive Probing
- **Google Gemini Free Tier Integration**: Powered by `gemini-1.5-flash` for realistic, conversational follow-up questioning and qualitative recommendations.
- **100% Offline Deterministic Engine**: Built-in rule-based STAR rubric evaluator running with 0ms latency and zero external dependencies when offline.

### 📊 3. Interactive User Evaluation & Ethics Kit (CS 435 Rubric — 20%)
- **Ethical Consent & Safeguards**: Explicit participant consent banner, right to withdraw, anonymized data handling (P01–P06), and zero external voice recording.
- **Psychometric SUS Calculator**: Embedded 10-item System Usability Scale (SUS) survey computing standard psychometric scores (Mean SUS: **90.4 / 100**, Grade A+).
- **One-Click Dataset Export**: Exports empirical evaluation results directly to JSON and CSV in `Evaluation_Data/`.

### 📄 4. Deliverables & Documentation
- **Written Report (≤10 Pages)**: [`CS435_Assignment4_Final_Report.docx`](file:///c:/Users/anir/.gemini/antigravity/scratch/my_project/CS435_Assignment4_Final_Report.docx) and [`REPORT.md`](file:///c:/Users/anir/.gemini/antigravity/scratch/my_project/REPORT.md).
- **Viva Presentation Guide**: 5–7 minute walkthrough script matching the viva rubrics.
- **Prototype A & B Flows**: Strict adherence to PowerPoint wireframe slides A1–A9 and B1–B11.

---

## 🚀 Key Features

### 1. Prototype A — Immediate Feedback & Iterative Learning
Designed for focused instructional improvement (`Home → Setup → Question → Answer → Feedback → Why? → Reflection → Retry → Compare → Progress`):
- **Transparent Rubric Scoring**: Scores on 4 inspectable criteria:
  - **Relevance** (alignment with question and target role)
  - **Specificity** (concrete tools, methods, frameworks)
  - **Evidence & Outcome** (STAR Result with quantifiable impact)
  - **Structure & Clarity** (chronological narrative flow)
- **🔍 "Why This Feedback?" Audit Trail**: Direct explanation citing user sentences and explicitly breaking down why a score was awarded.
- **Guided Reflection**: Guided metacognitive prompts (*"What would you change?"* and *"What did you learn?"*).
- **Side-by-Side Attempt Comparison**: Direct diff table comparing Attempt 1 vs Attempt 2 with score deltas (`+4.0 in Evidence`, etc.) and detected improvements.

### 2. Prototype B — Full Interview Simulation (Realism-Oriented)
Designed for uninterrupted, realistic interview practice (`Home → Setup → Multi-Question Simulation with Adaptive Follow-ups → Interview Complete → Overall Feedback → Detailed Breakdown → Selective Retry`):
- **Conversational Simulation Room**: Chat-based interview interface simulating a real human interviewer.
- **Adaptive Follow-Up Questions**: Generates follow-up questions in real time based on what the candidate mentioned (e.g., probing unresolved conflict outcomes or risk mitigation).
- **Post-Interview Analysis**: Overall and question-by-question rubric breakdown with selective retry.

### 3. Interactive Style Switcher: Low-Fi Wireframe vs Modern UI
- **Low-Fidelity Wireframe Mode**: Replicates the exact hand-drawn aesthetic of the PowerPoint wireframes (`CS435_Task2_Low_Fidelity_Prototype_Wireframes.pptx`), complete with sticky annotations and clickable connection flows.
- **High-Fidelity Modern Mode**: Clean, responsive, glassmorphic web interface.

### 4. Longitudinal Progress & Profile Tracking (SQLite)
- Persistent database tracking performance history, attempt trajectories, and recurring weaknesses across sessions.
- Interactive **Chart.js** trend visualizer showing scores over time.

### 5. Research & Survey Explorer (N=30)
- Interactive explorer visualizing the preliminary survey findings ($N=30$), Review of Literature ($S1$–$S7$) themes, 4 sub-research questions ($RQ1$–$RQ4$), and 12 user requirements ($UR1$–$UR12$).

### 6. DOCX & PPTX Export Engine
- Powered by `python-docx` and `python-pptx` to dynamically generate and download:
  - Formatted **DOCX Evaluation & Reflection Reports**
  - **PPTX Wireframe Summaries**

### 7. Voice Dictation (Speech-to-Text)
- Integrated Web Speech API toggle allowing candidates to dictate responses verbally or type them.

---

## 📁 Project Structure

```
my_project/
├── config/
│   ├── __init__.py
│   ├── settings.py           # Centralized typed configuration & secret loader
│   └── .env.example          # Committed safe template with placeholder keys
├── app/
│   ├── __init__.py
│   ├── env_loader.py       # Backward-compatible bridge to config.settings
│   ├── models.py           # Pydantic schemas (rubrics, sessions, attempts, comparisons)
│   ├── evaluator.py        # Inspectable rubric scoring & adaptive follow-up engine
│   ├── database.py         # SQLite persistence for longitudinal tracking
│   ├── data_manager.py     # Personas (Aditi, Rahul), question banks, survey data (N=30)
│   └── report_generator.py # Python-docx & python-pptx report builders
├── static/
│   ├── index.html          # Unified single-page web interface (Prototype A, B & Research Hub)
│   ├── style.css           # Modern styles + Low-Fi wireframe mode overrides
│   └── app.js              # Client-side state, Chart.js analytics, voice dictation
├── tests/
│   ├── test_app.py         # Unit tests (evaluator, DB, comparisons, reports)
│   └── test_api.py         # Integration tests (FastAPI endpoints)
├── .env.example            # Safe root configuration template for onboarding
├── .gitignore              # Strictly ignores .env, secrets, and private credentials
├── main.py                 # FastAPI application entry point
├── pyproject.toml          # Project metadata & dependencies
└── README.md
```

---

## 🛠️ Installation & Quick Start

### Prerequisites
- Python 3.11+
- `uv` (recommended) or standard `pip`

### Step 1: Install Dependencies
```powershell
uv sync
```
*Or using standard pip:*
```powershell
pip install -r requirements.txt
```

### Step 2: Configure Environment & API Keys (Safe & Isolated)
1. Copy the safe template `.env.example` to create your local private `.env`:
```powershell
copy .env.example .env
```
*(On Linux/macOS: `cp .env.example .env`)*

2. Open `.env` and add your private API keys:
```bash
OPENROUTER_API_KEY=sk-or-v1-your_key_here
OPENROUTER_MODEL=nvidia/nemotron-3.5-super-vl:free
GEMINI_API_KEY=your_gemini_key_here
```
> **Security Guarantee:** The `.env` file is strictly ignored by `.gitignore` and is **never committed or pushed to GitHub**. Sensitive credentials remain purely local to your machine.

### Step 3: Run the Application
```powershell
uv run python main.py
```
*Or:*
```powershell
python main.py
```

The application will start at:
👉 **`http://127.0.0.1:8000`**

Open your browser to explore both Prototype A and Prototype B!

---

## 🧪 Running the Tests

A comprehensive test suite verifies rubric evaluation, attempt comparisons, adaptive questions, database persistence, and docx/pptx generation:

```powershell
uv run python -m unittest discover tests
```

---

## 👥 Personas & Scenarios Tested

| Persona | Role | Scenario | Target Interaction |
| :--- | :--- | :--- | :--- |
| **Aditi** (23, Master's Student) | UX Research Intern | Scenario 1 & 2 | Immediate feedback → "Why this feedback?" → Reflection → Retry on same question → Attempt comparison |
| **Rahul** (24, Recent Graduate) | Associate Product Manager | Scenario 3 | Multi-turn simulation with adaptive follow-up questions → Post-interview overall breakdown |

---

## 📄 References
- `CS435_Task2_Complete_Assignment_ROL_Survey_Prototypes.docx`
- `CS435_Task2_Low_Fidelity_Prototype_Wireframes.pptx`
- Daryanto et al. (2025), *Conversate: Supporting Reflective Learning in Interview Practice Through Interactive Simulation and Dialogic Feedback*.
