from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class RubricCriterion(BaseModel):
    name: str
    score: float
    max_score: float = 10.0
    status: str  # "Good", "Adequate", "Needs Improvement"
    reason: str
    evidence_found: Optional[str] = None
    missing_aspect: Optional[str] = None
    rubric_definition: str


class EvaluationResult(BaseModel):
    overall_score: float
    relevance: RubricCriterion
    specificity: RubricCriterion
    evidence_outcome: RubricCriterion
    structure_clarity: RubricCriterion
    strengths: List[str]
    needs_improvement: List[str]
    actionable_suggestions: List[str]
    example_improved_answer: Optional[str] = None
    why_feedback_summary: Dict[str, Any] = {}
    adaptive_followup: Optional[Dict[str, Any]] = None


class SessionSetupRequest(BaseModel):
    prototype_type: str = "A"  # "A" (Immediate/Learning) or "B" (Full Simulation/Realism)
    candidate_name: Optional[str] = "Candidate"
    job_role: str = "Software Engineer"
    target_company: Optional[str] = ""
    experience_level: Optional[str] = "Mid-Level"
    interview_type: str = "Full Mixed Mock (Behavioral + Technical Architecture)"
    interview_duration: Optional[str] = "Standard Round (6-7 Questions • ~45 mins)"
    difficulty: str = "Neutral Corporate (Standard Hiring Bar / Objective)"
    interviewer_tone: Optional[str] = None
    cv_text: Optional[str] = ""
    job_description: Optional[str] = ""
    persona_id: Optional[str] = "custom"


class AnswerSubmitRequest(BaseModel):
    session_id: str
    question_id: int
    question_text: str
    answer_text: str
    attempt_number: int = 1


class ReflectionSubmitRequest(BaseModel):
    session_id: str
    question_id: int
    what_would_you_change: str
    what_did_you_learn: str


class FollowUpRequest(BaseModel):
    session_id: str
    question_id: int
    previous_question: str
    user_answer: str
    job_role: str
    interview_type: Optional[str] = None
    interview_duration: Optional[str] = None
    interviewer_tone: Optional[str] = None


class InterviewTurnRequest(BaseModel):
    session_id: str
    user_message: str
    turn_index: int = 1
    candidate_name: Optional[str] = "Candidate"
    job_role: Optional[str] = "Software Engineer"
    target_company: Optional[str] = ""
    experience_level: Optional[str] = "Mid-Level"
    interview_type: Optional[str] = None
    interview_duration: Optional[str] = None
    interviewer_tone: Optional[str] = None
    cv_text: Optional[str] = ""
    job_description: Optional[str] = ""
    conversation_history: Optional[List[Dict[str, str]]] = []


class SimulationEvaluationRequest(BaseModel):
    session_id: str
    candidate_name: Optional[str] = "Candidate"
    job_role: Optional[str] = "Software Engineer"
    target_company: Optional[str] = ""
    experience_level: Optional[str] = "Mid-Level"
    interview_type: Optional[str] = "Comprehensive (STAR Behavioral + Technical)"
    interview_duration: Optional[str] = "Standard Round (6-7 Questions • ~45 mins)"
    interviewer_tone: Optional[str] = "Professional & Rigorous (Standard FAANG/Corporate)"
    cv_text: Optional[str] = ""
    job_description: Optional[str] = ""
    conversation_history: Optional[List[Dict[str, str]]] = []


class AttemptComparison(BaseModel):
    question_id: int
    question_text: str
    attempt1_answer: str
    attempt2_answer: str
    attempt1_scores: Dict[str, float]
    attempt2_scores: Dict[str, float]
    deltas: Dict[str, float]
    improvements: List[str]
    focus_areas_remaining: List[str]


class ConfigUpdateRequest(BaseModel):
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = "nvidia/nemotron-3.5-super-vl:free"
    gemini_api_key: Optional[str] = None
    voice_speed: Optional[float] = 1.0
    auto_speak: Optional[bool] = True


class UserEvaluationSubmission(BaseModel):
    participant_id: str
    target_role: str
    prototype_tested: str  # "A", "B", or "Both"
    task_completed: bool
    task_time_seconds: int
    sus_scores: List[int]  # 10 items (scale 1-5)
    sus_total_score: float
    feedback_realism: str
    feedback_learning: str
    ethical_consent_signed: bool = True


class FeedbackSubmissionRequest(BaseModel):
    participant_name: Optional[str] = "Anonymous"
    prototype_evaluated: Optional[str] = "Both Prototypes"
    rating_overall: Optional[int] = 9
    rating_voice: Optional[int] = 9
    rating_ai_feedback: Optional[int] = 9
    rating_learning_value: Optional[int] = 9
    what_worked_well: Optional[str] = ""
    suggestions_for_improvement: Optional[str] = ""
    candidate_role: Optional[str] = "Software Engineer"
