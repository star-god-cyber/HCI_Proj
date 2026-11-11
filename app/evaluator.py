"""
Rubric Evaluator & Adaptive Question Engine.
Provides inspectable, transparent rubric evaluations, 'Why This Feedback' evidence extraction,
attempt comparisons, and adaptive follow-up question generation.
Supports Google Gemini Free Tier API with 100% offline deterministic fallback.
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import httpx
from app.models import EvaluationResult, RubricCriterion, AttemptComparison
from app.data_manager import get_question_bank_for_role
from app.env_loader import get_env_variable

logger = logging.getLogger(__name__)

GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-flash-latest"]
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_GEMINI_MODEL}:generateContent"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "nvidia/nemotron-3.5-super-vl:free"


class InterviewEvaluator:
    def __init__(self):
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.openrouter_model = os.environ.get("OPENROUTER_MODEL", OPENROUTER_MODEL)
        self.last_openrouter_status: Dict[str, Any] = {}
        # Action keywords
        self.action_words = [
            "decided", "implemented", "organized", "scheduled", "analyzed", "researched",
            "facilitated", "moderated", "created", "built", "designed", "resolved", "conducted",
            "initiated", "collaborated", "aligned", "prioritized", "negotiated"
        ]
        # Outcome keywords (metrics, deliverables, results)
        self.outcome_words = [
            "result", "outcome", "improved", "increased", "decreased", "saved", "delivered",
            "completed", "launched", "achieved", "reduced", "metric", "percent", "%",
            "success", "timeline", "consensus", "agreed", "validated", "adopted", "promoted"
        ]
        # Specificity indicators (tools, frameworks, concrete entities)
        self.specificity_words = [
            "figma", "python", "sql", "jira", "sprint", "star", "usability", "metric", "kpi",
            "interview", "survey", "prototype", "wireframe", "stakeholder", "engineer", "designer",
            "product", "user", "cohort", "a/b test", "roadmap", "architecture", "git"
        ]

    def get_openrouter_api_key(self) -> str:
        """
        Dynamically retrieves the latest OpenRouter API key from .env / settings.
        Detects live edits on disk immediately without requiring a server reboot.
        """
        env_key = get_env_variable("OPENROUTER_API_KEY", "")
        # Always prefer dynamically refreshed key from .env unless explicitly overridden
        key = self.openrouter_api_key or env_key
        # If the key in .env on disk has changed from previous memory, update in-memory cache
        if env_key and self.openrouter_api_key != env_key:
            self.openrouter_api_key = env_key
            key = env_key

        clean_key = (key or "").strip().strip('"').strip("'")
        if clean_key.lower().startswith("bearer "):
            clean_key = clean_key[7:].strip()
        if clean_key:
            if clean_key.startswith("v1-"):
                clean_key = f"sk-or-{clean_key}"
            elif not clean_key.startswith("sk-"):
                clean_key = f"sk-or-v1-{clean_key}"
        return clean_key

    def get_gemini_api_key(self) -> str:
        """Dynamically retrieves the latest Gemini API key from .env / settings."""
        env_key = get_env_variable("GEMINI_API_KEY", "")
        if env_key and self.gemini_api_key != env_key:
            self.gemini_api_key = env_key
        key = self.gemini_api_key or env_key
        clean_key = (key or "").strip().strip('"').strip("'")
        if clean_key.lower().startswith("bearer "):
            clean_key = clean_key[7:].strip()
        return clean_key

    def evaluate_answer(
        self,
        question_text: str,
        answer_text: str,
        job_role: str = "General",
        attempt_number: int = 1
    ) -> EvaluationResult:
        cleaned = answer_text.strip()
        sentences = [s.strip() for s in re.split(r'[.!?]+', cleaned) if len(s.strip()) > 5]
        words = cleaned.split()
        word_count = len(words)

        # Baseline checks
        if word_count < 15:
            # Very short / incomplete answer
            rel_score = 4.0
            spec_score = 3.0
            evid_score = 2.0
            struct_score = 3.0
            overall = 3.0
            return EvaluationResult(
                overall_score=overall,
                relevance=RubricCriterion(
                    name="Relevance",
                    score=rel_score,
                    status="Needs Improvement",
                    reason="The response is too brief to adequately address the core dimensions of the question.",
                    evidence_found="Brief statement provided.",
                    missing_aspect="Context and role-specific depth.",
                    rubric_definition="Addresses the specific prompt directly, stays on topic, and reflects target role competencies."
                ),
                specificity=RubricCriterion(
                    name="Specificity",
                    score=spec_score,
                    status="Needs Improvement",
                    reason="No concrete examples, tools, or specific methods were cited.",
                    evidence_found="None",
                    missing_aspect="Concrete situational details, names, tools, or methodologies.",
                    rubric_definition="Mentions concrete details, names, tools, technologies, and specific methodologies rather than broad generalities."
                ),
                evidence_outcome=RubricCriterion(
                    name="Evidence & Outcome",
                    score=evid_score,
                    status="Needs Improvement",
                    reason="No tangible result or measurable outcome was presented.",
                    evidence_found="None",
                    missing_aspect="Deliverables, metrics, or positive resolution.",
                    rubric_definition="Provides concrete results, quantifiable metrics, positive impact, and tangible deliverables (the 'R' in STAR)."
                ),
                structure_clarity=RubricCriterion(
                    name="Structure & Clarity",
                    score=struct_score,
                    status="Needs Improvement",
                    reason="Lacks narrative flow or STAR structure.",
                    evidence_found="Fragmentary explanation.",
                    missing_aspect="Progression from Situation to Task, Action, and Result.",
                    rubric_definition="Follows an organized narrative arc (e.g. STAR framework) with coherent progression."
                ),
                strengths=["Started addressing the topic."],
                needs_improvement=["Answer is too short (under 15 words). Elaborate using the STAR method."],
                actionable_suggestions=["Expand on the situation, the specific actions you took, and what resulted from it."],
                example_improved_answer=self._generate_example_answer(question_text, job_role),
                why_feedback_summary={
                    "primary_deficit": "Word count below threshold for substantive evaluation",
                    "recommendation": "Use 100-250 words following Situation, Task, Action, and Result."
                }
            )

        # 1. Relevance Score calculation (0-10)
        relevance_evidence = []
        rel_score = 7.0
        # Check alignment with question keywords
        q_keywords = [w.lower() for w in re.findall(r'\b\w{4,}\b', question_text)]
        overlap = [w for w in q_keywords if w in cleaned.lower()]
        if len(overlap) >= 3:
            rel_score += 1.5
            relevance_evidence.append(f"Directly addressed question concepts: {', '.join(set(overlap[:4]))}")
        elif len(overlap) >= 1:
            rel_score += 0.5
            relevance_evidence.append(f"Referenced question elements: {', '.join(set(overlap[:2]))}")
        else:
            rel_score -= 1.0

        if word_count > 60:
            rel_score += 0.5
        rel_score = min(9.5, max(4.0, round(rel_score, 1)))

        # 2. Specificity Score calculation (0-10)
        spec_hits = [w for w in self.specificity_words if re.search(r'\b' + re.escape(w) + r'\b', cleaned.lower())]
        spec_evidence = []
        has_numbers = bool(re.search(r'\b\d+\b|\b\d+%\b', cleaned))

        spec_score = 5.0
        if spec_hits:
            spec_score += min(3.0, len(spec_hits) * 0.8)
            spec_evidence.append(f"Concrete terms used: {', '.join(spec_hits[:4])}")
        if has_numbers:
            spec_score += 1.5
            num_match = re.search(r'\b\d+(?:%|\s+[a-zA-Z]+)?', cleaned)
            spec_evidence.append(f"Quantifiable detail cited: '{num_match.group(0)}'")
        if word_count > 120:
            spec_score += 0.5

        spec_score = min(9.5, max(3.5, round(spec_score, 1)))

        # 3. Evidence & Outcome Score calculation (0-10)
        # Outcome metrics require quantifiable impact or explicit outcome statements (STAR: Result)
        outcome_metric_match = re.search(r'\b\d+%\b|\b\d+\s*(?:percent|%|days ahead|higher|lower|increase|decrease|rate|satisfaction|completion)\b', cleaned, re.IGNORECASE)
        has_explicit_result_phrase = bool(re.search(r'\b(?:result|outcome|analytics revealed|metrics showed|completion rate|consequence)\b', cleaned, re.IGNORECASE))
        has_resolution = bool(re.search(r'\b(?:compromise|resolved|agreed|finished)\b', cleaned, re.IGNORECASE))

        evid_evidence = []
        evid_missing = None

        if outcome_metric_match or (has_explicit_result_phrase and ("%" in cleaned or "rate" in cleaned.lower() or "improved" in cleaned.lower())):
            evid_score = 8.0
            if outcome_metric_match:
                evid_score += 0.5
            outcome_sentences = [s for s in sentences if any(w in s.lower() for w in ["result", "outcome", "rate", "%", "improved", "ahead"])]
            if outcome_sentences:
                evid_evidence.append(f"Outcome clearly articulated: “{outcome_sentences[0].strip()}”")
            else:
                evid_evidence.append("Described positive measurable team and project results.")
        elif has_resolution or has_explicit_result_phrase:
            # Described action / compromise, but lacks measurable outcome (The Docx Survey / Scenario case: 4.0 to 5.0)
            evid_score = 4.5
            evid_evidence.append("Mentioned that a compromise was reached, but omitted concrete measurable outcomes.")
            evid_missing = "Concrete measurable result, metric, or user impact percentage (e.g., '28% higher task completion rate')."
        else:
            # Typical Survey/Docx scenario: "Situation clearly explained, outcome is missing (4/10)"
            evid_score = 4.0
            evid_missing = "Outcome is completely missing. Response describes actions taken but does not state the final tangible result or evidence."

        evid_score = min(9.5, max(3.0, round(evid_score, 1)))

        # 4. Structure & Clarity (0-10)
        struct_score = 6.0
        struct_evidence = []
        action_hits = [w for w in self.action_words if re.search(r'\b' + re.escape(w) + r'\b', cleaned.lower())]

        if len(sentences) >= 3:
            struct_score += 1.0
            struct_evidence.append(f"Well-developed response structure across {len(sentences)} distinct sentences.")
        if action_hits:
            struct_score += 1.0
            struct_evidence.append(f"Clear action-oriented phrasing ('{action_hits[0]}', '{action_hits[1] if len(action_hits)>1 else ''}').")
        if evid_score >= 7.0 and len(sentences) >= 3:
            struct_score += 1.0
            struct_evidence.append("Follows natural STAR progression (Situation → Action → Result).")

        struct_score = min(9.5, max(4.0, round(struct_score, 1)))

        # Overall weighted score
        overall = round((rel_score * 0.25) + (spec_score * 0.25) + (evid_score * 0.3) + (struct_score * 0.2), 1)

        # Qualitative synthesis
        strengths = []
        needs_improvement = []
        suggestions = []

        if rel_score >= 7.5:
            strengths.append("Situation and context are clearly framed and directly relevant to the role.")
        if spec_score >= 7.5:
            strengths.append(f"Great use of concrete terminology ({', '.join(spec_hits[:3]) if spec_hits else 'specific details'}).")
        if struct_score >= 7.5:
            strengths.append("Answer follows a coherent narrative sequence with clear professional actions.")
        if not strengths:
            strengths.append("You clearly explained the situation and the initial friction point.")

        if evid_score < 7.0:
            needs_improvement.append("Outcome is missing or understated: your answer does not explain what tangible result occurred.")
            suggestions.append("Add a concrete result, measurable metric (e.g., delivered on time, 95% user satisfaction, zero regressions), or clear team consensus.")
        if spec_score < 7.0:
            needs_improvement.append("Lacks specific methodologies, tools, or concrete artifacts.")
            suggestions.append("Name the exact tools (e.g., Figma, Jira, user tests) or specific meeting formats you utilized.")
        if struct_score < 7.0:
            needs_improvement.append("Structure feels somewhat rushed. Organize more explicitly around the STAR framework.")
            suggestions.append("Explicitly state: 1. Situation, 2. Your specific Task, 3. Actions taken, 4. Final Result.")

        if not needs_improvement:
            needs_improvement.append("Strong response! To elevate further, briefly mention what long-term takeaway or process change you instituted.")
            suggestions.append("Reflect on what you would do even better next time.")

        # Status labels
        def get_status(s):
            if s >= 8.0:
                return "Good"
            elif s >= 6.0:
                return "Adequate"
            return "Needs Improvement"

        why_summary = {
            "evaluation_criterion": "Provides concrete outcome / evidence (UR5, Rubric Section 10)",
            "evidence_score": evid_score,
            "evidence_reason": (
                "Your response describes the action you took, but does not provide a concrete outcome."
                if evid_score <= 5.5 else
                "Your response incorporates positive resolution and measurable details."
            ),
            "citations_found": evid_evidence if evid_evidence else ["Action described, but resolution omitted."],
            "recommended_addition": "A single sentence quantifying impact (e.g., 'As a result, we finished the sprint 2 days early with 100% test coverage').",
            "criteria_breakdown": {
                "evidence_outcome": {
                    "name": "Evidence & Outcome (STAR: Result)",
                    "score": evid_score,
                    "standard": "Rubric Section 10: The response must state a concrete outcome, business metric, or positive resolution.",
                    "excerpt": evid_evidence[0] if evid_evidence else "Action described, but concrete outcome omitted.",
                    "reason": "The response describes the action taken, but does not state a concrete outcome." if evid_score <= 5.5 else "Your response incorporates positive resolution and measurable details.",
                    "recommendation": "Add a single sentence quantifying impact (e.g., 'As a result, we finished the sprint 2 days early with 100% test coverage')."
                },
                "relevance": {
                    "name": "Relevance & Directness",
                    "score": rel_score,
                    "standard": "Rubric Section 7: Addresses the exact question asked without deviating into unprompted background.",
                    "excerpt": relevance_evidence[0] if relevance_evidence else "General narrative alignment.",
                    "reason": "Addresses the theme effectively and stays focused on professional context." if rel_score >= 7 else "Partially aligns with prompt, but deviates into generalities.",
                    "recommendation": "Anchor your opening sentence directly to the scenario asked in the question."
                },
                "specificity": {
                    "name": "Specificity & Technical Depth",
                    "score": spec_score,
                    "standard": "Rubric Section 8: Uses concrete details, named tools, frameworks, and specific technical artifacts.",
                    "excerpt": spec_evidence[0] if spec_evidence else "Broad general terminology.",
                    "reason": "Includes technical and contextual references." if spec_score >= 7 else "Uses broad, generic descriptions rather than specific tools or steps.",
                    "recommendation": "Name the specific systems, libraries, methodologies, or data pipelines you used."
                },
                "structure_clarity": {
                    "name": "Structure & STAR Flow",
                    "score": struct_score,
                    "standard": "Rubric Section 9: Organized narrative arc following Situation, Task, Action, and Result cleanly.",
                    "excerpt": struct_evidence[0] if struct_evidence else "Chronological narrative flow.",
                    "reason": "Clear chronological arc from problem to resolution." if struct_score >= 7.5 else "Narrative flow is slightly jumpy or incomplete.",
                    "recommendation": "Use explicit signposting like 'My specific role was...' and 'The ultimate outcome was...'."
                }
            }
        }

        return EvaluationResult(
            overall_score=overall,
            relevance=RubricCriterion(
                name="Relevance",
                score=rel_score,
                status=get_status(rel_score),
                reason="Addresses the conflict resolution theme effectively and stays focused on professional context." if rel_score >= 7 else "Partially aligns with prompt, but deviates into generalities.",
                evidence_found="; ".join(relevance_evidence) if relevance_evidence else "Referenced situational elements.",
                missing_aspect=None if rel_score >= 7.5 else "More direct alignment with role responsibilities.",
                rubric_definition="Addresses the specific prompt directly, stays on topic, and reflects target role competencies."
            ),
            specificity=RubricCriterion(
                name="Specificity",
                score=spec_score,
                status=get_status(spec_score),
                reason="Includes technical and contextual references." if spec_score >= 7 else "Uses broad, generic descriptions rather than specific tools or steps.",
                evidence_found="; ".join(spec_evidence) if spec_evidence else "General terminology used.",
                missing_aspect="Specific artifacts, tools, or metrics." if spec_score < 7.5 else None,
                rubric_definition="Mentions concrete details, names, tools, technologies, and specific methodologies rather than broad generalities."
            ),
            evidence_outcome=RubricCriterion(
                name="Evidence & Outcome",
                score=evid_score,
                status=get_status(evid_score),
                reason="Clearly documents outcomes and resolution impact." if evid_score >= 7.5 else "The response describes the action taken, but does not state a concrete outcome.",
                evidence_found="; ".join(evid_evidence) if evid_evidence else "None detected.",
                missing_aspect=evid_missing,
                rubric_definition="Provides concrete results, quantifiable metrics, positive impact, and tangible deliverables (the 'R' in STAR)."
            ),
            structure_clarity=RubricCriterion(
                name="Structure & Clarity",
                score=struct_score,
                status=get_status(struct_score),
                reason="Clear chronological arc from problem to resolution." if struct_score >= 7.5 else "Narrative flow is slightly jumpy or incomplete.",
                evidence_found="; ".join(struct_evidence) if struct_evidence else "Basic chronological order.",
                missing_aspect="Clear transition to the outcome phase." if struct_score < 7.5 else None,
                rubric_definition="Follows an organized narrative arc (e.g. STAR framework) with coherent progression."
            ),
            strengths=strengths,
            needs_improvement=needs_improvement,
            actionable_suggestions=suggestions,
            example_improved_answer=self._generate_example_answer(question_text, job_role),
            why_feedback_summary=why_summary
        )

    def _generate_example_answer(self, question_text: str, job_role: str) -> str:
        if "difficult teammate" in question_text.lower() or "conflict" in question_text.lower():
            return (
                "“During our cross-functional sprint for the user dashboard, a lead engineer and I disagreed on "
                "whether to include an extensive filtering menu or streamline it based on our usability tests. "
                "(Situation/Task) Rather than escalating, I scheduled a 30-minute working session where I walked through "
                "recorded test clips showing that 4 out of 5 users were confused by excessive filters. I proposed an A/B test "
                "compromise with collapsible advanced filters. (Action) As a measurable result, our engineering partner supported "
                "the compromise, we shipped the feature 2 days ahead of deadline, and subsequent product analytics revealed a "
                "28% higher task completion rate with zero user drop-offs.” (Result/Evidence)"
            )
        elif "incomplete information" in question_text.lower() or "decision" in question_text.lower():
            return (
                "“When our quarterly roadmap was due, analytics tracking on our newest onboarding funnel was delayed by a week. "
                "I needed to decide whether to invest in social sign-in or two-factor security first. (Situation) "
                "I triangulated qualitative support tickets, interviewed 6 recent active users, and reviewed historical drop-off patterns. "
                "(Action) I made the call to prioritize social sign-in while implementing basic 2FA in the subsequent sprint. (Action) "
                "Post-launch metrics validated the decision: onboarding completion surged by 19% within two weeks, with zero reported security escalations.” (Outcome)"
            )
        else:
            return (
                "“In my previous project, we faced an unexpected timeline crunch. I prioritized the core MVP requirements, "
                "communicated proactively with our stakeholders through daily standups, and reallocated sprint backlog items. "
                "As a concrete result, we delivered the high-priority release on schedule, improved client satisfaction scores from 3.8 to 4.7/5, "
                "and prevented any engineering burnout.”"
            )

    def compare_attempts(
        self,
        question_id: int,
        question_text: str,
        attempt1_answer: str,
        attempt2_answer: str,
        eval1: EvaluationResult,
        eval2: EvaluationResult
    ) -> AttemptComparison:
        deltas = {
            "relevance": round(eval2.relevance.score - eval1.relevance.score, 1),
            "specificity": round(eval2.specificity.score - eval1.specificity.score, 1),
            "evidence_outcome": round(eval2.evidence_outcome.score - eval1.evidence_outcome.score, 1),
            "structure_clarity": round(eval2.structure_clarity.score - eval1.structure_clarity.score, 1),
            "overall": round(eval2.overall_score - eval1.overall_score, 1),
        }

        improvements = []
        if deltas["evidence_outcome"] > 0:
            improvements.append(f"✓ Added measurable outcome & concrete evidence ({eval1.evidence_outcome.score} → {eval2.evidence_outcome.score})")
        if deltas["specificity"] > 0:
            improvements.append(f"✓ Integrated more concrete details, tools, and specific examples ({eval1.specificity.score} → {eval2.specificity.score})")
        if deltas["structure_clarity"] > 0:
            improvements.append(f"✓ Improved narrative flow and STAR progression ({eval1.structure_clarity.score} → {eval2.structure_clarity.score})")
        if deltas["overall"] > 0:
            improvements.append(f"✓ Overall score increased from {eval1.overall_score}/10 to {eval2.overall_score}/10 (+{deltas['overall']})")

        if not improvements:
            improvements.append("Revised phrasing and consolidated wording between attempts.")

        remaining = []
        if eval2.evidence_outcome.score < 8.0:
            remaining.append("Continue to sharpen quantifiable business metrics in the conclusion.")
        if eval2.specificity.score < 8.0:
            remaining.append("Consider citing specific industry frameworks or tools.")

        return AttemptComparison(
            question_id=question_id,
            question_text=question_text,
            attempt1_answer=attempt1_answer,
            attempt2_answer=attempt2_answer,
            attempt1_scores={
                "relevance": eval1.relevance.score,
                "specificity": eval1.specificity.score,
                "evidence": eval1.evidence_outcome.score,
                "structure": eval1.structure_clarity.score,
                "overall": eval1.overall_score
            },
            attempt2_scores={
                "relevance": eval2.relevance.score,
                "specificity": eval2.specificity.score,
                "evidence": eval2.evidence_outcome.score,
                "structure": eval2.structure_clarity.score,
                "overall": eval2.overall_score
            },
            deltas=deltas,
            improvements=improvements,
            focus_areas_remaining=remaining
        )

    def generate_adaptive_followup(
        self,
        previous_question: str,
        user_answer: str,
        job_role: str
    ) -> Dict[str, str]:
        cleaned = user_answer.strip()
        sentences = [s.strip() for s in re.split(r'[.!?]+', cleaned) if len(s.strip()) > 5]

        # Analyze answer content for realistic contextual follow-up
        lower_ans = cleaned.lower()
        if "conflict" in lower_ans or "disagreed" in lower_ans or "teammate" in lower_ans:
            if not any(w in lower_ans for w in ["result", "outcome", "percent", "%", "metric", "compromise"]):
                return {
                    "followup_question": "I can certainly understand how challenging that kind of disagreement can be with a teammate. When you sat down to work through that, what was the specific compromise or outcome you landed on, and how did it affect the project timeline?",
                    "reasoning": "Acknowledging conflict resolution effort while probing for the tangible resolution outcome and timeline impact."
                }
            else:
                return {
                    "followup_question": "That sounds like a very productive way to reach consensus. If you were to encounter that same disagreement with an executive stakeholder or external customer rather than a peer, how would you adapt your approach?",
                    "reasoning": "Validating peer resolution while probing situational adaptability across seniority levels."
                }
        elif "decision" in lower_ans or "data" in lower_ans or "incomplete" in lower_ans:
            return {
                "followup_question": "Making a critical call under ambiguity is always tough. When you made that decision with limited data, what primary risk did you identify, and what contingency plan did you prepare in case your hypothesis was wrong?",
                "reasoning": "Acknowledging ambiguity while probing risk management and contingency planning."
            }
        else:
            return {
                "followup_question": f"Thanks for sharing that breakdown. Looking back at that experience in your role as {job_role}, what was the single biggest takeaway that changed how you operate today?",
                "reasoning": "Inviting reflective depth and longitudinal professional growth."
            }

    def _normalize_gemini_messages(self, messages: List[Dict[str, str]]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Structures conversation messages into valid Google Gemini Generative Language API payload:
        1. Extracts 'system' roles into the top-level 'system_instruction' field.
        2. Normalizes 'assistant' -> 'model' and 'user' -> 'user'.
        3. Enforces strict alternating turns between 'user' and 'model' by concatenating consecutive same-role turns.
        4. Ensures the conversation sequence starts with a 'user' turn.
        """
        sys_texts = []
        contents = []
        for m in messages:
            role = m.get("role", "user").lower()
            text = m.get("content", "").strip()
            if not text:
                continue
            if role == "system":
                sys_texts.append(text)
            else:
                gem_role = "model" if role in ("assistant", "model") else "user"
                if contents and contents[-1]["role"] == gem_role:
                    contents[-1]["parts"][0]["text"] += f"\n\n{text}"
                else:
                    contents.append({"role": gem_role, "parts": [{"text": text}]})

        if contents and contents[0]["role"] == "model":
            contents.insert(0, {"role": "user", "parts": [{"text": "Hello."}]})

        sys_inst = {"parts": [{"text": "\n\n".join(sys_texts)}]} if sys_texts else None
        return sys_inst, contents

    async def call_gemini(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.6,
        max_tokens: int = 1500,
        response_json: bool = False,
        preferred_model: Optional[str] = None
    ) -> Optional[str]:
        """
        Executes a completion call to Google Gemini Generative Language API.
        Automatically verifies key, normalizes system instruction, and cascades across active models:
        (gemini-3.5-flash -> gemini-3.5-flash-lite -> gemini-flash-latest).
        Logs real-time live request and response telemetry to stdout.
        """
        key = self.get_gemini_api_key()
        if not key or key.startswith("test_mock") or len(key) < 10:
            return None

        masked_key = f"{key[:7]}...{key[-4:]}" if len(key) > 11 else "***"
        sys_inst, contents = self._normalize_gemini_messages(messages)
        if not contents:
            return None

        candidate_models = []
        if preferred_model:
            candidate_models.append(preferred_model)
        for m in GEMINI_MODELS:
            if m not in candidate_models:
                candidate_models.append(m)

        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            gen_config: Dict[str, Any] = {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
            if response_json:
                gen_config["responseMimeType"] = "application/json"

            payload: Dict[str, Any] = {
                "contents": contents,
                "generationConfig": gen_config
            }
            if sys_inst:
                payload["system_instruction"] = sys_inst

            print(f"\n=======================================================", flush=True)
            print(f"[Gemini LIVE REQUEST] >>> POST {url.split('?')[0]}", flush=True)
            print(f"[Gemini LIVE REQUEST] Model: {model_name} | Key: {masked_key}", flush=True)
            print(f"[Gemini LIVE REQUEST] Messages Count: {len(messages)} | Max Tokens: {max_tokens} | JSON Mode: {response_json}", flush=True)

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=payload)
                    print(f"[Gemini LIVE RESPONSE] <<< HTTP Status: {resp.status_code}", flush=True)

                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if text and text.strip():
                                print(f"[Gemini LIVE RESPONSE] [SUCCESS] Received completion from {model_name}!", flush=True)
                                print(f"=======================================================\n", flush=True)
                                return text.strip()
                    elif resp.status_code == 404:
                        print(f"[Gemini LIVE RESPONSE] Model '{model_name}' not available. Cascading to next candidate...", flush=True)
                        continue
                    else:
                        print(f"[Gemini LIVE RESPONSE] HTTP {resp.status_code}: {resp.text[:300]}", flush=True)
                        print(f"=======================================================\n", flush=True)
            except Exception as e:
                print(f"[Gemini LIVE EXCEPTION] {model_name} call failed: {e}", flush=True)
                print(f"=======================================================\n", flush=True)

        return None

    async def test_gemini_connection(self) -> Dict[str, Any]:
        """
        Executes an instant end-to-end diagnostic ping to Google Generative Language API
        to inspect API key validity, active model connectivity, and live responsiveness.
        """
        key = self.get_gemini_api_key()
        if not key or key.startswith("test_mock") or len(key) < 10:
            return {
                "success": False,
                "status": "missing_key",
                "message": "No valid Gemini API key found in .env or active settings."
            }

        masked_key = f"{key[:7]}...{key[-4:]}" if len(key) > 11 else "***"
        result: Dict[str, Any] = {
            "api_key_masked": masked_key,
            "key_valid": False,
            "status_code": None,
            "model_tested": None,
            "test_reply": None
        }

        for m in GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        url,
                        json={"contents": [{"parts": [{"text": "Respond with the single word CONNECTED"}]}]}
                    )
                    result["status_code"] = resp.status_code
                    result["model_tested"] = m
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip() if candidates else "CONNECTED"
                        result["key_valid"] = True
                        result["success"] = True
                        result["test_reply"] = text
                        result["message"] = f"✓ Google Gemini API call succeeded with model '{m}'!"
                        return result
                    elif resp.status_code == 404:
                        continue
                    else:
                        result["success"] = False
                        result["message"] = f"Google Gemini returned HTTP {resp.status_code}: {resp.text[:200]}"
            except Exception as e:
                result["exception"] = str(e)
                continue

        result["success"] = False
        result["message"] = result.get("message") or "Failed to connect to Google Gemini API."
        return result

    async def generate_adaptive_followup_gemini(
        self,
        previous_question: str,
        user_answer: str,
        job_role: str,
        api_key: Optional[str] = None
    ) -> Dict[str, str]:
        prompt = f"""You are an empathetic yet rigorous professional interviewer conducting an interview for the role: "{job_role}".
The previous interview question asked was:
"{previous_question}"

The candidate just provided this spoken response:
"{user_answer}"

Generate an adaptive follow-up question.
Requirements:
1. Ground the follow-up directly in what the candidate mentioned or omitted (e.g., probe for metrics, trade-offs, interpersonal nuance, or risk management).
2. Keep it conversational, realistic, and punchy (1-2 sentences maximum).
3. Do NOT include markdown styling or bullet points.

Respond ONLY with a JSON object in this exact format:
{{
  "followup_question": "“Your question here...”",
  "reasoning": "Brief explanation of why this follow-up was probed based on the response."
}}
"""
        try:
            content = await self.call_gemini([{"role": "user", "content": prompt}], temperature=0.7, max_tokens=300, response_json=True)
            if content:
                parsed = self._clean_json_output(content)
                if isinstance(parsed, dict) and "followup_question" in parsed:
                    parsed["source"] = "gemini_3.5_flash"
                    return parsed
        except Exception as e:
            logger.warning(f"Gemini API call failed, falling back to local engine: {e}")

        fallback = self.generate_adaptive_followup(previous_question, user_answer, job_role)
        fallback["source"] = "deterministic_engine"
        return fallback

    async def evaluate_answer_gemini(
        self,
        question_text: str,
        answer_text: str,
        job_role: str = "General",
        attempt_number: int = 1,
        api_key: Optional[str] = None,
        candidate_name: str = "Candidate",
        target_company: str = "",
        experience_level: str = "",
        cv_text: str = ""
    ) -> EvaluationResult:
        base_eval = self.evaluate_answer(question_text, answer_text, job_role, attempt_number)
        if len(answer_text.strip().split()) < 15:
            return base_eval

        cand_context = f"Candidate: {candidate_name}, Role: {job_role}"
        if target_company:
            cand_context += f", Target Company: {target_company}"
        if experience_level:
            cand_context += f", Seniority: {experience_level}"
        if cv_text:
            cand_context += f"\nCV Excerpt: {cv_text[:300]}"

        prompt = f"""You are an expert interview coach evaluating a candidate for the role: "{job_role}".
{cand_context}

Question: "{question_text}"
Candidate's Spoken Answer: "{answer_text}"

The candidate was preliminarily evaluated on:
- Relevance: {base_eval.relevance.score}/10
- Specificity: {base_eval.specificity.score}/10
- Evidence & Outcome: {base_eval.evidence_outcome.score}/10
- Structure & Clarity: {base_eval.structure_clarity.score}/10

Please provide:
1. 2 distinct strengths
2. 2 distinct needs for improvement
3. 1 concrete actionable recommendation following the STAR method
4. An improved model response demonstrating how to include measurable outcomes tailored to this role.

Respond ONLY with a JSON object in this format:
{{
  "strengths": ["...", "..."],
  "needs_improvement": ["...", "..."],
  "actionable_suggestions": ["..."],
  "example_improved_answer": "..."
}}
"""
        try:
            content = await self.call_gemini([{"role": "user", "content": prompt}], temperature=0.6, max_tokens=1500, response_json=True)
            if content:
                parsed = self._clean_json_output(content)
                if isinstance(parsed, dict):
                    if "strengths" in parsed and parsed["strengths"]:
                        base_eval.strengths = [str(s) for s in parsed["strengths"]]
                    if "needs_improvement" in parsed and parsed["needs_improvement"]:
                        base_eval.needs_improvement = [str(n) for n in parsed["needs_improvement"]]
                    if "actionable_suggestions" in parsed and parsed["actionable_suggestions"]:
                        base_eval.actionable_suggestions = [str(a) for a in parsed["actionable_suggestions"]]
                    if "example_improved_answer" in parsed and parsed["example_improved_answer"]:
                        base_eval.example_improved_answer = str(parsed["example_improved_answer"])
                    base_eval.why_feedback_summary["evaluator_engine"] = "gemini_3.5_flash"
        except Exception as e:
            logger.warning(f"Gemini API call for evaluation failed, retaining deterministic feedback: {e}")

        return base_eval

    # =========================================================================
    # OPENROUTER INTEGRATION: NVIDIA Nemotron 3.5 Super VL (Free)
    # =========================================================================

    async def call_openrouter(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: int = 3000
    ) -> Optional[str]:
        """
        Executes a chat completion call to OpenRouter targeting nvidia/nemotron-3.5-super-vl:free.
        Zero cost free tier reasoning model. Logs real-time request and response telemetry.
        """
        api_key = self.get_openrouter_api_key()
        if not api_key:
            print("[OpenRouter] No API key configured. Bypassing OpenRouter call.", flush=True)
            return None

        model_name = (self.openrouter_model or OPENROUTER_MODEL).strip()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://127.0.0.1:8000",
            "Referer": "http://127.0.0.1:8000",
            "X-Title": "CS 435 AI Interview Practice",
            "Content-Type": "application/json"
        }
        masked_key = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 11 else "***"
        # Nemotron 3.5 requires sufficient token budget for reasoning + output
        token_budget = max(max_tokens, 2800)
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": token_budget
        }

        print(f"\n=======================================================", flush=True)
        print(f"[OpenRouter LIVE REQUEST] >>> POST {OPENROUTER_API_URL}", flush=True)
        print(f"[OpenRouter LIVE REQUEST] Model: {model_name} | Key: {masked_key}", flush=True)
        print(f"[OpenRouter LIVE REQUEST] Messages Count: {len(messages)} | Token Budget: {token_budget}", flush=True)

        try:
            # 60 second timeout with 15s connect for reasoning model completion
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                resp = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
                gen_id = resp.headers.get("x-generation-id", "none")
                rl_rem = resp.headers.get("x-ratelimit-remaining", "n/a")
                rl_lim = resp.headers.get("x-ratelimit-limit", "n/a")

                self.last_openrouter_status = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "model": model_name,
                    "status_code": resp.status_code,
                    "generation_id": gen_id,
                    "ratelimit_remaining": rl_rem,
                    "ratelimit_limit": rl_lim,
                    "response_snippet": resp.text[:300]
                }

                print(f"[OpenRouter LIVE RESPONSE] <<< HTTP Status: {resp.status_code}", flush=True)
                print(f"[OpenRouter LIVE RESPONSE] Generation ID: {gen_id}", flush=True)
                print(f"[OpenRouter LIVE RESPONSE] Daily Quota Remaining: {rl_rem} / {rl_lim}", flush=True)

                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    print(f"[OpenRouter LIVE RESPONSE] [SUCCESS] Received completion from {model_name}!", flush=True)
                    print(f"=======================================================\n", flush=True)
                    if choices:
                        msg = choices[0].get("message", {})
                        content = msg.get("content")
                        if content and content.strip():
                            return content.strip()
                        reasoning = msg.get("reasoning", "")
                        if reasoning and ("[" in reasoning or "{" in reasoning):
                            return reasoning.strip()
                elif resp.status_code == 429:
                    print(f"[OpenRouter LIVE RESPONSE] [HTTP 429 RATE LIMIT EXCEEDED]", flush=True)
                    print(f"[OpenRouter LIVE RESPONSE] Error Details: {resp.text}", flush=True)
                    print(f"[OpenRouter LIVE RESPONSE] CRITICAL NOTE: OpenRouter does NOT create log entries in your dashboard Activity tab when a request is blocked by free-tier daily rate limits (429), because Cloudflare edge rejects the call before model token generation.", flush=True)
                    print(f"[OpenRouter LIVE RESPONSE] Engaging fallback dialogue synthesis engine.", flush=True)
                    print(f"=======================================================\n", flush=True)
                else:
                    print(f"[OpenRouter LIVE RESPONSE] [HTTP {resp.status_code}] {resp.text[:300]}", flush=True)
                    print(f"=======================================================\n", flush=True)
        except Exception as e:
            self.last_openrouter_status = {
                "timestamp": datetime.utcnow().isoformat(),
                "model": model_name,
                "status_code": 0,
                "error": str(e)
            }
            print(f"[OpenRouter LIVE EXCEPTION] Failed to connect: {e}", flush=True)
            print(f"=======================================================\n", flush=True)

        return None

    async def test_openrouter_connection(self) -> Dict[str, Any]:
        """
        Executes an instant end-to-end diagnostic ping to OpenRouter to inspect API key validity,
        daily quota limits, and live model responsiveness.
        """
        api_key = self.get_openrouter_api_key()
        if not api_key:
            return {
                "success": False,
                "status": "missing_key",
                "message": "No OpenRouter API key found in .env or active settings."
            }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://127.0.0.1:8000",
            "X-Title": "CS 435 AI Interview Practice",
            "Content-Type": "application/json"
        }
        masked_key = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 11 else "***"
        model_name = (self.openrouter_model or OPENROUTER_MODEL).strip()

        result: Dict[str, Any] = {
            "api_key_masked": masked_key,
            "model": model_name,
            "key_valid": False,
            "quota_status": None,
            "chat_status_code": None,
            "chat_generation_id": None,
            "chat_response": None,
            "dashboard_logging_explanation": ""
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Inspect key status & quota
            try:
                k_resp = await client.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
                if k_resp.status_code == 200:
                    k_data = k_resp.json().get("data", {})
                    result["key_valid"] = True
                    result["quota_status"] = k_data.get("free_model_daily_requests")
                    result["credits"] = {
                        "usage": k_data.get("usage", 0),
                        "is_free_tier": k_data.get("is_free_tier", True)
                    }
            except Exception as e:
                result["key_error"] = str(e)

            # 2. Live chat test probe
            try:
                c_resp = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": "Respond with the single word 'CONNECTED'"}],
                        "max_tokens": 10
                    }
                )
                result["chat_status_code"] = c_resp.status_code
                result["chat_generation_id"] = c_resp.headers.get("x-generation-id", "none")

                if c_resp.status_code == 200:
                    result["success"] = True
                    result["chat_response"] = c_resp.json()
                    result["message"] = "✓ OpenRouter call succeeded! A new generation log is now visible in your OpenRouter Activity tab."
                    result["dashboard_logging_explanation"] = "Because this request returned HTTP 200 OK, OpenRouter logged this run under https://openrouter.ai/activity."
                elif c_resp.status_code == 429:
                    result["success"] = False
                    result["chat_response"] = c_resp.json()
                    result["message"] = "⚠️ OpenRouter HTTP 429: Rate limit exceeded (50/50 free daily requests used)."
                    result["dashboard_logging_explanation"] = (
                        "WHY NO LOGS APPEAR IN OPENROUTER DASHBOARD: OpenRouter's dashboard Activity tab ONLY logs runs where a model was called and tokens were generated (HTTP 200). "
                        "When your account exceeds the 50 free requests/day limit, Cloudflare rejects the request at the edge gateway before model execution. "
                        "The call definitely reached OpenRouter (as proven by the Generation ID and 429 response above), but 429s are not stored as completed generations."
                    )
                else:
                    result["success"] = False
                    result["chat_response"] = c_resp.text
                    result["message"] = f"OpenRouter returned HTTP {c_resp.status_code}."
            except Exception as e:
                result["success"] = False
                result["chat_exception"] = str(e)
                result["message"] = f"Connection failed: {e}"

        return result

    def _clean_json_output(self, text: str) -> Any:
        """Helper to safely parse JSON from LLM responses even if wrapped in markdown blocks, reasoning text, or containing comments/trailing commas."""
        t = text.strip()
        if t.startswith("```"):
            t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
            t = re.sub(r"\s*```$", "", t)
        t = t.strip()

        try:
            return json.loads(t)
        except Exception:
            pass

        # Check if a markdown code block exists anywhere in the response (common when LLM outputs preamble/thinking)
        code_block = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, flags=re.IGNORECASE)
        if code_block:
            inner = code_block.group(1).strip()
            try:
                return json.loads(inner)
            except Exception:
                cleaned_inner = re.sub(r',\s*([}\]])', r'\1', inner)
                try:
                    return json.loads(cleaned_inner)
                except Exception:
                    pass

        # Match bracketed json array or object
        match = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', t)
        if match:
            candidate = match.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                # Remove trailing commas like ", }" or ", ]"
                cleaned = re.sub(r',\s*([}\]])', r'\1', candidate)
                try:
                    return json.loads(cleaned)
                except Exception:
                    pass

        # Robust regex-based question array recovery
        regex_items = []
        for block in re.finditer(r'\{[^{}]*"(?:text|question)"[^{}]*\}', t):
            b_str = block.group(0)
            try:
                b_clean = re.sub(r',\s*\}', '}', b_str)
                regex_items.append(json.loads(b_clean))
            except Exception:
                q_match = re.search(r'"(?:text|question)"\s*:\s*"([^"]+)"', b_str)
                if q_match:
                    comp_match = re.search(r'"competency"\s*:\s*"([^"]+)"', b_str)
                    cat_match = re.search(r'"category"\s*:\s*"([^"]+)"', b_str)
                    regex_items.append({
                        "id": len(regex_items) + 1,
                        "text": q_match.group(1),
                        "competency": comp_match.group(1) if comp_match else "Role Competency",
                        "category": cat_match.group(1) if cat_match else "Behavioral"
                    })
        if regex_items:
            return regex_items

        raise ValueError(f"Could not parse valid JSON from text: {t[:200]}")

    async def generate_custom_interview_questions(
        self,
        candidate_name: str,
        job_role: str,
        target_company: str = "",
        experience_level: str = "Mid-Level",
        interview_type: str = "Behavioral",
        difficulty: str = "Medium",
        cv_text: str = "",
        job_description: str = "",
        count: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Generates high-fidelity tailored interview questions using OpenRouter (NVIDIA Nemotron 3.5 Super VL).
        Falls back seamlessly to curated sample questions when offline or key is absent.
        """
        api_key = self.get_openrouter_api_key()
        gemini_key = self.get_gemini_api_key()
        fallback_questions = get_question_bank_for_role(job_role)

        if not api_key and not (gemini_key and not gemini_key.startswith("test_mock") and len(gemini_key) > 10):
            logger.info("No AI API key configured; using curated fallback question bank.")
            return fallback_questions

        company_context = f" Target Company: '{target_company}'." if target_company else " Industry Tier 1 Firm."
        cv_context = f"\nCandidate Resume/CV Highlights:\n{cv_text.strip()[:1000]}" if cv_text and cv_text.strip() else "\nCandidate Background: Mid to senior engineering/product practitioner."
        jd_context = f"\nTarget Job Description / Requirements:\n{job_description.strip()[:1000]}" if job_description and job_description.strip() else ""

        system_prompt = (
            "You are an elite corporate technical and behavioral interviewer for top global tech and product firms. "
            "Your goal is to generate personalized, rigorous, realistic interview questions for a candidate based directly on their profile. "
            "Always output strictly valid JSON with no unescaped double quotes inside strings."
        )

        user_prompt = f"""Generate {count} distinct interview questions tailored directly to this candidate:
Candidate Name: {candidate_name}
Target Role: {job_role}{company_context}
Experience Level: {experience_level}
Interview Focus / Type: {interview_type}
Difficulty / Tone: {difficulty}{cv_context}{jd_context}

Requirements:
1. Deeply anchor each question in the candidate's actual resume experience, role expertise, target company domain, and seniority level.
2. Provide a realistic mix of behavioral (STAR-method), technical execution, and architectural trade-off questions.
3. Do NOT use unescaped double quotes inside strings. Use single quotes for any internal terms or code identifiers.
4. For each question, supply the competency tested, ideal structure, and key lookouts for evaluation.

Respond ONLY with a valid JSON array of {count} question objects in this exact format, with no preamble:
[
  {{
    "id": 1,
    "text": "The verbatim interview question to ask the candidate...",
    "category": "{interview_type}",
    "difficulty": "{difficulty}",
    "competency": "Key competency being tested",
    "ideal_structure": "Situation, Task, Action, Result with quantifiable impact",
    "key_lookouts": ["Lookout 1", "Lookout 2", "Lookout 3"]
  }}
]
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            content = await self.call_openrouter(messages, temperature=0.4, max_tokens=3000)
            if content:
                parsed = self._clean_json_output(content)
                # If wrapped in a dict like {"questions": [...]} or {"data": [...]}
                if isinstance(parsed, dict):
                    for key in ["questions", "interview_questions", "question_list", "items", "data"]:
                        if key in parsed and isinstance(parsed[key], list):
                            parsed = parsed[key]
                            break

                if isinstance(parsed, list) and len(parsed) > 0:
                    sanitized = []
                    for i, q in enumerate(parsed[:count], start=1):
                        if isinstance(q, str):
                            sanitized.append({
                                "id": i,
                                "text": q.strip(),
                                "category": interview_type,
                                "difficulty": difficulty,
                                "competency": "Core Competency",
                                "ideal_structure": "STAR Method (Situation, Task, Action, Result)",
                                "key_lookouts": ["Specific actions taken", "Measurable outcome"],
                                "source": "openrouter_nemotron"
                            })
                        elif isinstance(q, dict):
                            sanitized.append({
                                "id": i,
                                "text": q.get("text") or q.get("question") or f"Tell me about your experience as a {job_role}.",
                                "category": q.get("category", interview_type),
                                "difficulty": q.get("difficulty", difficulty),
                                "competency": q.get("competency", "Core Competencies"),
                                "ideal_structure": q.get("ideal_structure", "STAR Method (Situation, Task, Action, Result)"),
                                "key_lookouts": q.get("key_lookouts", ["Specific actions", "Measurable outcomes"]),
                                "source": "openrouter_nemotron"
                            })
                    if sanitized:
                        logger.info(f"Generated {len(sanitized)} custom questions via OpenRouter ({self.openrouter_model}).")
                        return sanitized
        except Exception as e:
            logger.warning(f"Failed to generate custom questions via OpenRouter: {e}")

        # Try Google Gemini if key is configured
        gemini_key = self.get_gemini_api_key()
        if gemini_key and not gemini_key.startswith("test_mock") and len(gemini_key) > 10:
            try:
                content = await self.call_gemini(
                    [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    temperature=0.4,
                    max_tokens=1500,
                    response_json=True
                )
                if content:
                    parsed = self._clean_json_output(content)
                    if isinstance(parsed, dict):
                        for key in ["questions", "interview_questions", "question_list", "items", "data"]:
                            if key in parsed and isinstance(parsed[key], list):
                                parsed = parsed[key]
                                break
                    if isinstance(parsed, list) and len(parsed) > 0:
                        sanitized = []
                        for i, q in enumerate(parsed[:count], start=1):
                            if isinstance(q, dict):
                                sanitized.append({
                                    "id": i,
                                    "text": q.get("text") or q.get("question") or f"Tell me about your experience as a {job_role}.",
                                    "category": q.get("category", interview_type),
                                    "difficulty": q.get("difficulty", difficulty),
                                    "competency": q.get("competency", "Core Competencies"),
                                    "ideal_structure": q.get("ideal_structure", "STAR Method (Situation, Task, Action, Result)"),
                                    "key_lookouts": q.get("key_lookouts", ["Specific actions", "Measurable outcomes"]),
                                    "source": "gemini_3.5_flash"
                                })
                        if sanitized:
                            logger.info(f"Generated {len(sanitized)} custom questions via Google Gemini.")
                            return sanitized
            except Exception as e:
                logger.warning(f"Failed to generate custom questions via Gemini: {e}")

        logger.info("Generating profile-grounded custom questions via Semantic Dialogue Engine.")
        return self._synthesize_custom_questions_from_profile(
            candidate_name=candidate_name,
            job_role=job_role,
            target_company=target_company,
            experience_level=experience_level,
            interview_type=interview_type,
            difficulty=difficulty,
            cv_text=cv_text,
            job_description=job_description,
            count=count
        )

    def _synthesize_custom_questions_from_profile(
        self,
        candidate_name: str,
        job_role: str,
        target_company: str = "",
        experience_level: str = "Mid-Level",
        interview_type: str = "Behavioral",
        difficulty: str = "Medium",
        cv_text: str = "",
        job_description: str = "",
        count: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Synthesizes deeply customized, domain-specific interview questions grounded in
        the candidate's exact CV highlights, target role, and company expectations.
        Never falls back to generic one-size-fits-all questions.
        """
        company_phrase = f" at {target_company}" if target_company else ""
        semantics = self._extract_candidate_semantics(cv_text)
        techs = semantics["tech"]
        metrics = semantics["metrics"]
        actions = semantics["actions"]

        # Extract salient projects or achievements from CV lines
        salient_points = []
        if cv_text:
            lines = [l.strip().lstrip("•-* ") for l in cv_text.split("\n") if len(l.strip()) > 25]
            for line in lines:
                if any(k in line.lower() for k in ["led", "architected", "built", "spearheaded", "designed", "optimized", "managed", "conducted", "deployed", "scaled"]):
                    first_sent = line.split(".")[0].strip()
                    if len(first_sent) > 20:
                        salient_points.append(first_sent)

        flagship_project = salient_points[0] if salient_points else (actions[0] if actions else f"{job_role} core systems")
        secondary_project = salient_points[1] if len(salient_points) > 1 else (actions[1] if len(actions) > 1 else "cross-functional project delivery")

        top_tech = techs[0] if techs else "core architecture"
        secondary_tech = techs[1] if len(techs) > 1 else "scalable infrastructure"
        metric_cite = f" (such as {metrics[0]})" if metrics else ""

        int_lower = (interview_type or "").lower()

        # Tailor questions by track
        if "technical" in int_lower or "system" in int_lower or "architecture" in int_lower:
            q1_text = (
                f"In your work on {flagship_project}, you dealt with critical engineering constraints and scalability demands. "
                f"Could you walk me through the architectural topology of that system, explain how you managed data flow and state persistence using {top_tech}, "
                f"and what specific bottleneck or failure mode posed the greatest challenge?"
            )
            q1_comp = "System Architecture & High-Throughput Design"
            q1_struct = "Context & scale, Architectural topology, Bottleneck diagnosis, Resolution"

            q2_text = (
                f"When implementing {secondary_project}, you had to make critical architectural trade-offs between latency, consistency, and operational complexity{metric_cite}. "
                f"Can you describe a significant disagreement or differing viewpoint you had with a teammate or tech lead regarding whether to use {top_tech} versus an alternative approach, and how you drove consensus?"
            )
            q2_comp = "Technical Trade-Offs & Consensus Building"
            q2_struct = "STAR (Conflicting viewpoints, Benchmarking data, Alignment mechanism, Quantifiable outcome)"

            q3_text = (
                f"For mission-critical systems{company_phrase}, resilience during catastrophic network partitions, service degradation, or traffic surges is paramount. "
                f"How did you design failure recovery, chaos testing, or automated failover for your services, and how did you verify that zero data anomalies or SLA violations occurred?"
            )
            q3_comp = "Fault Tolerance, Chaos Engineering & Production Reliability"
            q3_struct = "Failure scenarios, Observability & alerting, Recovery mechanics, Production telemetry"

        elif "ux" in (job_role or "").lower() or "research" in (job_role or "").lower() or "design" in (job_role or "").lower():
            q1_text = (
                f"In your research experience on {flagship_project}, you evaluated user friction and behavioral patterns. "
                f"Could you walk me through your end-to-end research methodology—how you formulated your research questions, selected user cohorts, and synthesized qualitative feedback into concrete design specifications?"
            )
            q1_comp = "Mixed-Methods Research Design & Synthesis"
            q1_struct = "Research objective, Methodology selection, Synthesis framework, Impact on product"

            q2_text = (
                f"Tell me about a time during {secondary_project} where your evaluative research findings contradicted the core assumptions or roadmap priorities of product managers or engineering leads. "
                f"How did you present the contradictory evidence diplomatically, and how did you navigate their pushback?"
            )
            q2_comp = "Evidence-Based Advocacy & Stakeholder Alignment"
            q2_struct = "STAR (Friction with stakeholders, Evidence presentation clips/metrics, Resolution, Final design adoption)"

            q3_text = (
                f"When conducting user studies under tight sprint timelines{company_phrase}, how do you evaluate the trade-off between qualitative depth (contextual inquiries) and quantitative breadth (surveys, usability benchmarking{metric_cite}) to ensure decision confidence?"
            )
            q3_comp = "Research Prioritization & Rigor Under Constraints"
            q3_struct = "Trade-off criteria, Resource balancing, Concrete past study example, Quantifiable impact"

        elif "product" in (job_role or "").lower() or "apm" in (job_role or "").lower() or "strategy" in int_lower:
            q1_text = (
                f"In your experience leading {flagship_project}, you were tasked with driving product adoption and business value{metric_cite}. "
                f"Could you explain how you established your North Star metric, mapped the user journey, and prioritized the initial MVP feature scope against competing team requests?"
            )
            q1_comp = "Product Discovery, North Star Metrics & Scoping"
            q1_struct = "Problem statement, Metric definition, Scoping framework, Launch execution"

            q2_text = (
                f"Tell me about a high-stakes trade-off you had to manage during {secondary_project} where engineering wanted to address technical debt while business stakeholders demanded immediate customer features. "
                f"How did you evaluate the opportunity cost, structure the compromise, and align both sides?"
            )
            q2_comp = "Cross-Functional Trade-Offs & Strategic Prioritization"
            q2_struct = "STAR (Competing priorities, Cost-of-delay analysis, Stakeholder compromise, Business result)"

            q3_text = (
                f"How do you design and interpret multivariate A/B experiments when sample sizes or market volatility create noisy signals{company_phrase}? "
                f"Can you share an example where an experiment produced ambiguous or counter-intuitive metrics, and how you made the final launch decision?"
            )
            q3_comp = "Experimentation Rigor & Data-Informed Decision Making"
            q3_struct = "Hypothesis, Experiment design, Guardrail metrics analysis, Executive launch decision"

        elif "leadership" in int_lower:
            q1_text = (
                f"Looking at your career trajectory in {flagship_project}, you have taken on increasing technical and organizational ownership. "
                f"Can you describe how you set the technical vision and engineering standards across squads, and how you ensure team alignment with multi-quarter business milestones?"
            )
            q1_comp = "Technical Strategy & Organizational Alignment"
            q1_struct = "Strategic vision, Execution roadmap, Cross-team buy-in, Measurable milestones"

            q2_text = (
                f"Describe a situation during {secondary_project} where an engineering team was falling behind on critical deliverables or experiencing severe cross-team friction. "
                f"How did you intervene, diagnose the root cause, and realign the team without compromising morale?"
            )
            q2_comp = "Team Mentorship, Friction Resolution & Delivery Health"
            q2_struct = "STAR (Diagnosis of bottleneck, Remediation actions, Psychological safety, Recovery metric)"

            q3_text = (
                f"How do you balance investing in long-term platform resilience and developer velocity against delivering urgent executive commitments{company_phrase}? "
                f"Give an example where you successfully secured leadership buy-in for a major architectural refactoring."
            )
            q3_comp = "Executive Communication & Platform Investment"
            q3_struct = "Business case formulation, ROI projection, Executive sponsorship, Operational outcome"

        else: # Standard / Behavioral & Mixed
            q1_text = (
                f"Reflecting on your flagship work on {flagship_project}: could you walk me through the end-to-end lifecycle of that project, "
                f"highlighting your personal technical contribution, the key tools you utilized ({top_tech}), and how you resolved the single hardest obstacle?"
            )
            q1_comp = "Technical Ownership & Problem Solving"
            q1_struct = "Context & role, Execution details, Obstacle overcome, Measurable outcome"

            q2_text = (
                f"Tell me about a time during {secondary_project} when you encountered a significant conflict or breakdown in communication with a teammate, designer, or product partner. "
                f"What was the root cause of the disagreement, and what specific steps did you take to reach an objective resolution?"
            )
            q2_comp = "Conflict Resolution & Cross-Functional Collaboration (STAR)"
            q2_struct = "Situation, Task, Action (communication & compromise), Result"

            q3_text = (
                f"When working on complex deliverables under tight deadlines{company_phrase}, how do you ensure the delivered solution satisfies rigorous quality standards{metric_cite}? "
                f"Can you share a specific instance where your verification caught a critical issue before deployment?"
            )
            q3_comp = "Quality Assurance, Risk Mitigation & Measurable Delivery"
            q3_struct = "Quality framework, Risk discovery, Mitigation action, Quantified impact"

        return [
            {
                "id": 1,
                "text": q1_text,
                "category": interview_type,
                "difficulty": difficulty,
                "competency": q1_comp,
                "ideal_structure": q1_struct,
                "key_lookouts": ["Depth of technical ownership", "Concrete tools & architecture mentioned", "Clarity of communication"],
                "source": "semantic_dialogue_engine"
            },
            {
                "id": 2,
                "text": q2_text,
                "category": "Behavioral & Cross-Functional Collaboration",
                "difficulty": difficulty,
                "competency": q2_comp,
                "ideal_structure": q2_struct,
                "key_lookouts": ["Diplomatic stakeholder handling", "STAR structure (Action & Result)", "Quantifiable resolution"],
                "source": "semantic_dialogue_engine"
            },
            {
                "id": 3,
                "text": q3_text,
                "category": "Operational Rigor & Measurable Outcomes",
                "difficulty": difficulty,
                "competency": q3_comp,
                "ideal_structure": q3_struct,
                "key_lookouts": ["Resilience & edge-case awareness", "Concrete metrics cited", "Verification methodology"],
                "source": "semantic_dialogue_engine"
            }
        ]

    def generate_opening_question(
        self,
        candidate_name: str,
        job_role: str,
        target_company: str = "",
        experience_level: str = "",
        interview_type: str = "Full Mixed Mock (Behavioral + Technical Architecture)",
        difficulty: str = "Neutral Corporate (Standard Hiring Bar / Objective)",
        cv_text: str = "",
        job_description: str = ""
    ) -> str:
        """
        Generates a natural, personalized, role-grounded opening question from Dr. Marcus Vance.
        Anchored in the candidate's exact CV and target role, avoiding robotic one-size-fits-all greetings.
        """
        company_phrase = f" at {target_company}" if target_company else ""
        semantics = self._extract_candidate_semantics(cv_text)
        techs = semantics["tech"]
        actions = semantics["actions"]

        # Extract top highlight from CV
        highlight = ""
        if cv_text:
            lines = [l.strip().lstrip("•-* ") for l in cv_text.split("\n") if len(l.strip()) > 25]
            for l in lines:
                if any(k in l.lower() for k in ["led", "architected", "built", "spearheaded", "designed", "deployed", "managed", "conducted"]):
                    first_sent = l.split(".")[0].strip()
                    highlight = first_sent if len(first_sent) < 110 else first_sent[:105].rsplit(" ", 1)[0] + "..."
                    break

        if not highlight:
            if actions:
                highlight = actions[0]
            elif techs:
                highlight = f"{techs[0]} and {techs[1]}" if len(techs) > 1 else techs[0]
            else:
                highlight = f"{job_role} core initiatives"

        int_lower = (interview_type or "").lower()
        if "technical" in int_lower or "architecture" in int_lower:
            round_desc = "system architecture and engineering"
        elif "ux" in (job_role or "").lower() or "research" in (job_role or "").lower():
            round_desc = "design and evaluative research"
        elif "product" in (job_role or "").lower() or "apm" in (job_role or "").lower():
            round_desc = "strategic product execution"
        else:
            round_desc = "comprehensive"

        intro_highlight = f" Looking through your background and resume, I noted your experience with {highlight}." if highlight else ""
        return (
            f"Good morning, {candidate_name}! Welcome to your official {round_desc} interview for the {job_role} position{company_phrase}. "
            f"I'm Dr. Marcus Vance, lead hiring evaluator for the team today.{intro_highlight} "
            f"To kick off our conversation, could you please introduce yourself, walk me through your background and career journey, and share what specifically brings you to this role?"
        )

    def _is_user_requesting_wrapup(self, message: str) -> bool:
        """Detects if the candidate communicated that they are ready to wrap up or conclude the interview."""
        clean = message.lower().strip()
        pattern = r'\b(wrap\s*up|conclude|concluding|end\s+(?:the\s+)?interview|finish\s+(?:the\s+)?interview|that(?:\'s|\s+is)\s+all(?:\s+from\s+my\s+side|\s+for\s+now)?|that\s+covers\s+(?:everything|it)|ready\s+for\s+(?:the\s+)?evaluation|no\s+more\s+questions|i(?:\'m|\s+am)\s+done|we\s+can\s+stop\s+here)\b'
        return bool(re.search(pattern, clean))

    def _synthesize_adaptive_followup(
        self,
        previous_question: str,
        user_answer: str,
        job_role: str = "General",
        candidate_name: str = "Candidate",
        cv_text: str = "",
        job_description: str = ""
    ) -> Dict[str, str]:
        """
        Synthesizes a sharp, contextually grounded adaptive AI follow-up probe
        based directly on what the candidate mentioned or omitted in their spoken answer.
        Never falls back to generic static strings.
        """
        semantics = self._extract_candidate_semantics(user_answer)
        techs = semantics["tech"]
        metrics = semantics["metrics"]
        actions = semantics["actions"]

        if actions:
            anchor = actions[0]
        elif len(techs) >= 2:
            anchor = f"{techs[0]} and {techs[1]}"
        elif techs:
            anchor = techs[0]
        else:
            anchor = f"your {job_role} solution"

        lower_ans = user_answer.lower()
        if not metrics:
            probe = (
                f"You laid out your execution steps on {anchor} clearly, {candidate_name}. "
                f"However, could you share the concrete measurable outcome: what specific metrics, KPIs, or latency numbers proved the initiative succeeded?"
            )
            reason = "Candidate omitted quantifiable outcomes (STAR Result); probing for metrics and business impact."
        elif not any(w in lower_ans for w in ["trade-off", "tradeoff", "alternative", "compromise", "disagreement", "pushback", "friction", "debate", "challenge"]):
            probe = (
                f"Achieving {metrics[0]} on {anchor} is a great result, {candidate_name}. "
                f"What was the most significant architectural trade-off or alternative option you weighed and rejected when making that decision?"
            )
            reason = "Candidate presented a clean execution path; probing for architectural trade-offs and alternative designs."
        elif not any(w in lower_ans for w in ["failure", "resilience", "edge", "bottleneck", "recovery", "outage", "monitoring"]):
            probe = (
                f"I appreciate how you navigated that challenge with {anchor}. "
                f"How did you design for failure resilience—what edge case or bottleneck caused the greatest concern in production?"
            )
            reason = "Probing operational resilience, fault tolerance, and failure mode mitigation."
        else:
            probe = (
                f"Reflecting on your experience with {anchor}, {candidate_name}: "
                f"if you had to tackle that same problem today with your current perspective, what would you design differently?"
            )
            reason = "Probing retrospective architectural depth and continuous technical learning."

        return {
            "followup_question": probe,
            "reasoning": reason,
            "source": "adaptive_ai_dialogue_engine"
        }

    async def generate_adaptive_followup_ai(
        self,
        previous_question: str,
        user_answer: str,
        job_role: str,
        candidate_name: str = "Candidate",
        target_company: str = "",
        experience_level: str = "",
        cv_text: str = "",
        job_description: str = ""
    ) -> Dict[str, str]:
        """
        Generates an adaptive follow-up probing question.
        Priority:
        1. OpenRouter (NVIDIA Nemotron 3.5 Super VL)
        2. Gemini 1.5 Flash (if key present)
        3. Deterministic local follow-up engine
        """
        api_key = self.get_openrouter_api_key()
        if api_key:
            cand_profile_str = f"Candidate: {candidate_name}, Target Role: {job_role}"
            if target_company:
                cand_profile_str += f", Target Company: {target_company}"
            if experience_level:
                cand_profile_str += f", Seniority: {experience_level}"
            if cv_text:
                cand_profile_str += f"\nCandidate Resume Highlights: {cv_text.strip()[:400]}"
            if job_description:
                cand_profile_str += f"\nTarget Job Context: {job_description.strip()[:300]}"

            company_ref = f" at {target_company}" if target_company else ""
            system_prompt = (
                f"You are Dr. Marcus Vance, a warm, seasoned, and highly perceptive senior hiring evaluator{company_ref} "
                f"interviewing {candidate_name} for the position of '{job_role}'. "
                "You conduct an authentic, natural human conversation. You actively listen to the candidate's exact words, "
                "acknowledge their points like a real human leader, and naturally probe their decision-making. "
                "You NEVER sound like an AI, a generic rubric checklist, or a cold mechanical exam interrogation."
            )
            user_prompt = f"""Candidate Profile:
{cand_profile_str}

The interview question you previously asked {candidate_name} was:
"{previous_question}"

{candidate_name} just answered you with this spoken response:
"{user_answer}"

Generate your natural, in-the-moment spoken conversational follow-up response.
Strict guidelines for an authentic, human conversation:
1. Open with a brief, warm, authentic conversational acknowledgment referencing a specific detail or dilemma they actually stated (e.g. 'That is a classic dilemma between velocity and stability, {candidate_name}.', 'Makes total sense why that would be a contentious issue with the engineering lead.').
2. Seamlessly transition into an insightful, natural follow-up question probing how they reached alignment, what benchmarks or prototypes they leveraged, or the actual measured outcome.
3. Keep the total response spoken, conversational, and punchy (1 to 2 spoken sentences total).
4. Do NOT use unescaped double quotes inside strings. Use single quotes for any internal terms.

Respond ONLY with a JSON object in this exact format:
{{
  "followup_question": "Your spoken conversational acknowledgment and follow-up question here...",
  "reasoning": "1-sentence note explaining why you probed this angle."
}}
"""
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            try:
                content = await self.call_openrouter(messages, temperature=0.6, max_tokens=2000)
                if content:
                    parsed = self._clean_json_output(content)
                    if isinstance(parsed, dict):
                        fq = parsed.get("followup_question") or parsed.get("question") or parsed.get("followup")
                        reason = parsed.get("reasoning") or parsed.get("reason") or "Probing situational depth."
                        if fq:
                            return {
                                "followup_question": str(fq).strip(),
                                "reasoning": str(reason).strip(),
                                "source": "openrouter_nemotron"
                            }
                    elif isinstance(parsed, str) and len(parsed.strip()) > 10:
                        return {
                            "followup_question": parsed.strip(),
                            "reasoning": "Contextual probing on candidate response.",
                            "source": "openrouter_nemotron"
                        }
            except Exception as e:
                logger.warning(f"OpenRouter follow-up failed, falling back: {e}")

        # Fallback to Gemini if configured
        gemini_key = self.get_gemini_api_key()
        if gemini_key:
            return await self.generate_adaptive_followup_gemini(previous_question, user_answer, job_role, api_key=gemini_key)

        # Fallback to adaptive semantic AI dialogue engine
        return self._synthesize_adaptive_followup(
            previous_question=previous_question,
            user_answer=user_answer,
            job_role=job_role,
            candidate_name=candidate_name,
            cv_text=cv_text,
            job_description=job_description
        )

    def build_official_interview_system_prompt(
        self,
        candidate_name: str,
        job_role: str,
        target_company: str = "",
        experience_level: str = "",
        cv_text: str = "",
        job_description: str = "",
        interview_type: str = "Full Mixed Mock (Behavioral + Technical Architecture)",
        interview_duration: str = "Standard Round (6-7 Questions • ~45 mins)",
        interviewer_tone: str = "Neutral Corporate (Standard Hiring Bar / Objective)",
        turn_index: int = 1,
        max_turns: int = 7
    ) -> str:
        company_phrase = f" at {target_company}" if target_company else ""

        # Determine exact current stage instruction based on turn_index
        if turn_index <= 1:
            stage_instruction = f"""CURRENT MANDATORY STAGE TARGET: STAGE 2 (Candidate Introduction Acknowledgment & Technical Deep Dive Transition)
- The candidate has just provided their self-introduction and career background in Turn 1.
- MANDATORY TWO-STEP PROTOCOL:
  1. STEP 1 - ACKNOWLEDGE THE INTRODUCTION & BACKGROUND FIRST: Warmly and explicitly acknowledge and validate {candidate_name}'s self-introduction, career journey, and specific background highlights (actively listening and mirroring back 1 to 2 specific technologies, frameworks, company names, or achievements they just mentioned).
  2. STEP 2 - START WITH QUESTIONS: Smoothly transition from their introduction into the interview questions by asking ONE focused, deep-dive question about a major system architecture, initiative, or core technical/domain challenge they highlighted in their background.
- CRITICAL NEGATIVE CONSTRAINT: Under NO circumstances should you ask {candidate_name} to introduce themselves or walk through their background again. That introduction is completed!"""
        elif turn_index == 2:
            stage_instruction = f"""CURRENT MANDATORY STAGE TARGET: STAGE 3 (Behavioral, Conflict & Technical Trade-Offs)
- The candidate has just explained their technical project architecture.
- CRITICAL NEGATIVE CONSTRAINT: Do NOT ask for their background or self-introduction!
- YOUR MANDATORY GOAL FOR THIS TURN:
  1. Acknowledge their technical architecture or design choices like a seasoned engineering leader.
  2. Transition to a behavioral probe asking about a significant disagreement, trade-off, or conflict they had with a teammate, tech lead, or product manager during that project, and how they reached resolution."""
        elif turn_index == 3:
            stage_instruction = f"""CURRENT MANDATORY STAGE TARGET: STAGE 4 (Resilience, Failure Modes & Edge Cases)
- The candidate has just explained their conflict/trade-off resolution.
- YOUR MANDATORY GOAL FOR THIS TURN:
  1. Acknowledge their resolution with active listening.
  2. Ask how their system handled unexpected edge cases, failure recovery, or sudden traffic/scale spikes, and how their architecture ensured resilience."""
        elif turn_index == 4:
            stage_instruction = f"""CURRENT MANDATORY STAGE TARGET: STAGE 5 (Measured Impact & Quantitative Verification)
- The candidate has just explained their resilience/scalability approach.
- YOUR MANDATORY GOAL FOR THIS TURN:
  1. Acknowledge their technical execution.
  2. Probe how they verified the business impact and measurable outcomes (concrete KPIs, latency metrics, conversion, or user adoption)."""
        elif turn_index == 5:
            stage_instruction = f"""CURRENT MANDATORY STAGE TARGET: STAGE 6 (Retrospective Reflection & Lessons Learned)
- YOUR MANDATORY GOAL FOR THIS TURN:
  1. Acknowledge their quantified metrics.
  2. Probe what architectural or strategic choice they would do differently today with hindsight."""
        elif turn_index == 6:
            stage_instruction = f"""CURRENT MANDATORY STAGE TARGET: STAGE 7 (Cross-Functional Leadership & Roadmap Prioritization)
- YOUR MANDATORY GOAL FOR THIS TURN:
  1. Acknowledge their reflective insights.
  2. Probe how they navigate roadmap friction and collaborate with non-technical stakeholders."""
        else:
            stage_instruction = f"""CURRENT MANDATORY STAGE TARGET: STAGE FINAL (Official Interview Conclusion)
- YOUR MANDATORY GOAL FOR THIS TURN:
  1. Warmly thank {candidate_name} for sharing their technical journey and quantified outcomes.
  2. Officially state that this concludes the oral questioning, and you will now finalize their hiring committee scorecard."""

        return f"""You are Dr. Marcus Vance, a distinguished, seasoned, and deeply observant senior hiring evaluator conducting an official, high-stakes corporate interview{company_phrase} for the position of '{job_role}'.

==================================================
NON-NEGOTIABLE CANDIDATE SPECIFICATION (GROUND TRUTH)
==================================================
- Candidate Name: {candidate_name}
- Target Job Role: {job_role}
- Target Company / Organization: {target_company or 'Leading Industry Firm'}
- Experience / Seniority Level: {experience_level or 'Mid-Level'}
- Interview Round Type & Focus: {interview_type}
- Target Interview Duration & Pacing: {interview_duration}
- Interviewer Persona & Evaluation Rigor: {interviewer_tone}
- Candidate Resume & Experience Highlights:
{cv_text.strip() or 'Strong background in industry-standard competencies for ' + job_role + '.'}
- Target Job Description & Expectations:
{job_description.strip() or 'Core competencies, technical execution, leadership, problem-solving, and cross-functional communication.'}

==================================================
CURRENT CONVERSATIONAL TURN & MANDATORY OBJECTIVE
==================================================
Current Turn: Turn {turn_index} of {max_turns}
{stage_instruction}

==================================================
NON-NEGOTIABLE OFFICIAL INTERVIEW RULES
==================================================
1. ASK QUESTIONS STRICTLY ONE BY ONE:
   - Ask exactly ONE clear, focused question at a time.
   - NEVER ask multi-part compound questions, numbered lists, or bullet points.
   - Wait for the candidate's spoken response before proceeding to the next stage.

2. ACTIVE LISTENING & EXPLICIT GROUNDING:
   - Every single response from you MUST begin with a genuine, human conversational reaction directly acknowledging 1 to 3 specific concepts, technologies, metrics, or frameworks the candidate just stated in their latest prompt.
   - NEVER REPEAT GREETINGS: Do NOT repeat greetings like 'Good morning', 'Good afternoon', or 'Hello' in subsequent turns! The opening greeting was already delivered in Stage 1. Repeating greetings sounds robotic and unnatural. Jump straight into an active listening reaction.
   - Never sound like an AI assistant or a rubric checklist.
   - Keep each spoken response between 2 to 3 natural, conversational sentences.
   - Do NOT emit Markdown headers, asterisks, bullet points, JSON keys, or meta tags in your spoken dialogue so that browser text-to-speech sounds completely natural.

3. INTERVIEWER PERSONA & TONE ENFORCEMENT:
   - Your tone must strictly embody: '{interviewer_tone}'.
   - If Tone contains 'Supportive' or 'Mentorship': Be encouraging, warm, validate achievements constructively, and create psychological safety for the candidate.
   - If Tone contains 'Neutral' or 'Standard': Maintain a structured, professional, executive presence, neither overly effusive nor cold.
   - If Tone contains 'Challenging' or 'Bar Raiser' or 'Stress': Rigorously examine technical depth, probe boundary conditions, question trade-offs, and push for concrete numbers and accountability without being hostile.

4. NATURAL CONVERSATION CONCLUSION PROTOCOL:
   - User-Communicated Conclusion: If the candidate signals that they wish to wrap up, conclude, have answered all questions, or are ready for evaluation (e.g., 'wrap up', 'that covers everything', 'that is all from my side', 'ready for evaluation'):
     Warmly thank the candidate, acknowledge their contributions, state clearly that the oral questioning has concluded, and invite them to view their scorecard. Do NOT ask any further questions.
   - Interviewer-Initiated Conclusion (Needful Information Extracted): If this is Turn 4 or later and the candidate has demonstrated their technical architecture, trade-offs, and measurable outcomes:
     State that you have extracted all the needful signals required to convene the hiring committee scorecard, thank them warmly for their time, and conclude the interview naturally without asking another question.

5. MANDATORY CV & JOB ROLE DISCREPANCY CROSS-EXAMINATION:
   - Continuously cross-examine what {candidate_name} states in their answers against their documented Resume / CV highlights and target Job Role expectations:
     * Seniority or Scope Inflation: Candidate claiming executive, chief architect, or sole decision-maker authority on massive enterprise initiatives when their CV lists junior, intern, or entry-level roles.
     * Domain or Role Mismatch: Candidate claiming work completely unrelated to or conflicting with their documented track record (e.g. claiming low-level C++/CUDA kernel drivers for a purely qualitative UX Research role, or claiming marketing surveys for a distributed systems infrastructure role).
     * Contradictory Claims or Denials: Candidate contradicting their resume dates, tech stack, metrics, or claiming they have no experience with a core skill explicitly featured on their CV.
   - IMMEDIATE CROSS-EXAMINATION MANDATE:
     * If you detect any strong conflict or discrepancy between what {candidate_name} claims and what is documented on their CV or required by the target Job Role:
     * You MUST prioritize raising a direct, tactful cross-examination question on that exact discrepancy!
     * Politely challenge and probe the gap (e.g., 'Looking at your documented resume highlights, your background is at the [documented level/domain], yet you mentioned [spoken claim]. Could you clarify your exact individual contribution and help me reconcile that with what is documented on your CV?').

==================================================
MANDATORY HISTORY BUFFER & ACTIVE LISTENING PROTOCOL
==================================================
You are provided with the complete chronological conversation history buffer above.
Your question MUST directly investigate the specific decisions, trade-offs, deadlocks, or outcomes of what {candidate_name} just spoke about. Never ask detached, pre-canned, or generic questions that ignore what the candidate just told you.

Every time you respond:
1. EXPLICIT ACTIVE LISTENING: You MUST actively listen and acknowledge specific concepts, technical keywords, frameworks, company names, tools, or metrics that the candidate directly stated in their latest response (e.g., if they mention PyTorch, medical imaging, CUDA, Kafka, gRPC, user churn, or checkout funnels, you must explicitly weave that into your acknowledgment).
2. LOGICAL PROBE CONTINUITY: Your question MUST directly investigate the specific decisions, trade-offs, deadlocks, or outcomes of what they just spoke about. Never ask detached, pre-canned, or generic questions that ignore what the candidate just told you.
3. CONVERSATIONAL PROGRESSION: Follow the interview stages naturally based on the continuous dialogue history.
"""

    async def conduct_official_interview_turn(
        self,
        conversation_history: List[Dict[str, str]],
        user_message: str,
        candidate_name: str = "Candidate",
        job_role: str = "Software Engineer",
        target_company: str = "",
        experience_level: str = "",
        cv_text: str = "",
        job_description: str = "",
        interview_type: str = "Full Mixed Mock (Behavioral + Technical Architecture)",
        interview_duration: str = "Standard Round (6-7 Questions • ~45 mins)",
        interviewer_tone: str = "Neutral Corporate (Standard Hiring Bar / Objective)",
        turn_index: int = 1
    ) -> Dict[str, Any]:
        """
        Executes a natural, official one-by-one multi-turn interview turn.
        System prompt contains non-negotiable candidate ground truth, continuous history buffer, and active listening rules.
        """
        # Determine pacing cutoff based on interview duration
        max_turns = 7
        dur_lower = (interview_duration or "").lower()
        if "focused" in dur_lower or "screening" in dur_lower or "quick" in dur_lower or "25" in dur_lower:
            max_turns = 5
        elif "comprehensive" in dur_lower or "onsite" in dur_lower or "loop" in dur_lower or "60" in dur_lower:
            max_turns = 9
        else:
            max_turns = 7

        # User-Communicated Conclusion Trigger
        if self._is_user_requesting_wrapup(user_message):
            closing_speech = (
                f"Thank you, {candidate_name}. You have shared thoughtful, concrete insights today across your projects and decision-making. "
                f"We have covered all the requisite competencies and dimensions for the {job_role} position. "
                f"That officially concludes our oral interview questioning. Whenever you are ready, please proceed to review your comprehensive Hiring Committee Evaluation Scorecard."
            )
            return {
                "interviewer_message": closing_speech,
                "followup_question": closing_speech,
                "reasoning": "Candidate communicated wrap-up intent; concluding interview naturally.",
                "turn_index": turn_index + 1,
                "is_concluded": True,
                "source": "adaptive_ai_dialogue_engine"
            }

        # Determine AI provider priority
        openrouter_key = self.get_openrouter_api_key()
        gemini_key = self.get_gemini_api_key()
        is_openrouter_dummy = not openrouter_key or "testkey" in openrouter_key.lower()
        has_gemini = bool(gemini_key and not gemini_key.startswith("test_mock") and len(gemini_key) > 10)

        # Build official interview messages payload
        system_prompt = self.build_official_interview_system_prompt(
            candidate_name=candidate_name,
            job_role=job_role,
            target_company=target_company,
            experience_level=experience_level,
            cv_text=cv_text,
            job_description=job_description,
            interview_type=interview_type,
            interview_duration=interview_duration,
            interviewer_tone=interviewer_tone,
            turn_index=turn_index,
            max_turns=max_turns
        )
        messages = [{"role": "system", "content": system_prompt}]
        for msg in conversation_history:
            r = msg.get("role", "user")
            c = msg.get("content", "").strip()
            if c:
                messages.append({"role": r, "content": c})

        clean_user_msg = user_message.strip()
        if not messages or messages[-1].get("content") != clean_user_msg:
            messages.append({"role": "user", "content": clean_user_msg})

        # Tier 1A: If Gemini is active and OpenRouter is empty/dummy, prioritize Gemini directly
        if has_gemini and is_openrouter_dummy:
            try:
                gemini_content = await self.call_gemini_turn(messages, temperature=0.65)
                if gemini_content and len(gemini_content.strip()) > 15:
                    clean_reply = self._clean_llm_reply(gemini_content)
                    return {
                        "interviewer_message": clean_reply,
                        "followup_question": clean_reply,
                        "reasoning": f"Stage {turn_index + 1} official Google Gemini live probe.",
                        "turn_index": turn_index + 1,
                        "is_concluded": (turn_index >= max_turns or "conclude" in clean_reply.lower() or "evaluation" in clean_reply.lower()),
                        "source": "gemini_3.5_flash"
                    }
            except Exception as e:
                logger.warning(f"Primary Gemini official turn failed, falling back: {e}")

        # Tier 1B: Try OpenRouter (NVIDIA Nemotron 3.5 Super VL)
        if openrouter_key and not is_openrouter_dummy:
            try:
                content = await self.call_openrouter(messages, temperature=0.65, max_tokens=1500)
                if content and len(content.strip()) > 15:
                    clean_reply = self._clean_llm_reply(content)
                    return {
                        "interviewer_message": clean_reply,
                        "followup_question": clean_reply,
                        "reasoning": f"Stage {turn_index + 1} official Nemotron 3.5 live probe.",
                        "turn_index": turn_index + 1,
                        "is_concluded": (turn_index >= max_turns or "conclude" in clean_reply.lower() or "evaluation" in clean_reply.lower()),
                        "source": "openrouter_nemotron"
                    }
            except Exception as e:
                logger.warning(f"OpenRouter official turn failed, attempting secondary provider: {e}")

        # Tier 2: Try Google Gemini (gemini-3.5-flash) if not already run in Tier 1A
        if has_gemini:
            try:
                gemini_content = await self.call_gemini_turn(messages, temperature=0.65)
                if gemini_content and len(gemini_content.strip()) > 15:
                    clean_reply = self._clean_llm_reply(gemini_content)
                    return {
                        "interviewer_message": clean_reply,
                        "followup_question": clean_reply,
                        "reasoning": f"Stage {turn_index + 1} official Google Gemini live probe.",
                        "turn_index": turn_index + 1,
                        "is_concluded": (turn_index >= max_turns or "conclude" in clean_reply.lower() or "evaluation" in clean_reply.lower()),
                        "source": "gemini_3.5_flash"
                    }
            except Exception as e:
                logger.warning(f"Gemini official turn failed, engaging semantic dialogue engine: {e}")

        # Tier 3: Adaptive Semantic Dialogue Engine (High-Fidelity Context-Aware NLP)
        turn_res = self._synthesize_semantic_interview_turn(
            conversation_history=conversation_history,
            user_message=user_message,
            candidate_name=candidate_name,
            job_role=job_role,
            target_company=target_company,
            experience_level=experience_level,
            interview_type=interview_type,
            interview_duration=interview_duration,
            interviewer_tone=interviewer_tone,
            turn_index=turn_index,
            max_turns=max_turns,
            cv_text=cv_text,
            job_description=job_description
        )
        turn_res["openrouter_status"] = self.last_openrouter_status
        return turn_res

    def _clean_llm_reply(self, text: str) -> str:
        """Helper to extract clean dialogue from LLM replies, stripping markdown fences or nested JSON."""
        clean = text.strip().strip('"').strip("'")
        if clean.startswith("{") and "}" in clean:
            parsed = self._clean_json_output(clean)
            if isinstance(parsed, dict):
                clean = parsed.get("followup_question") or parsed.get("interviewer_message") or clean
        clean = re.sub(r'\*\*(.*?)\*\*', r'\1', str(clean))
        return clean.strip()

    async def call_gemini_turn(self, messages: List[Dict[str, str]], temperature: float = 0.65) -> Optional[str]:
        """Executes a multi-turn conversation turn using Google Gemini."""
        return await self.call_gemini(messages, temperature=temperature, max_tokens=600)

    def _extract_candidate_semantics(self, text: str, conversation_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Deep semantic entity extraction, action mining, and metric identification
        from candidate responses to dynamically ground interviewer turns in what the candidate actually spoke.
        """
        cleaned = text.strip()
        lowered = cleaned.lower()

        # Domain Taxonomy (Distributed, Languages, AI/ML, Cloud, Frontend, UX, Product, Finance, Healthcare, Hardware)
        domain_vocabulary = [
            "raft", "paxos", "consensus", "grpc", "rest", "graphql", "microservices", "kafka", "rabbitmq",
            "flink", "spark", "postgres", "postgresql", "mysql", "mongodb", "redis", "dynamodb", "cassandra",
            "elasticsearch", "docker", "kubernetes", "k8s", "terraform", "aws", "gcp", "azure", "ci/cd",
            "latency", "throughput", "concurrency", "distributed", "sharding", "replication", "partition",
            "caching", "2pc", "saga", "rate limiting", "load balancer", "websocket", "fault tolerance",
            "python", "java", "c++", "c#", "go", "golang", "rust", "typescript", "javascript", "scala",
            "kotlin", "swift", "php", "ruby", "sql", "bash", "shell", "unity",
            "pytorch", "tensorflow", "keras", "opencv", "tensorrt", "cuda", "ros", "ros2", "llm", "rag",
            "transformer", "nlp", "computer vision", "segmentation", "bert", "embeddings", "vector db",
            "react", "vue", "angular", "next.js", "tailwind", "swiftui", "jetpack compose", "flutter",
            "react native", "webrtc", "canvas", "webgl", "figma", "usability", "wireframe", "heuristic",
            "cognitive walkthrough", "sus", "user research", "a/b test", "conversion", "retention",
            "onboarding", "checkout funnel", "accessibility", "wcag",
            "prd", "roadmap", "backlog", "sprint", "agile", "scrum", "stakeholders", "kpi", "okr",
            "arr", "gmv", "roi", "ltv", "cac", "mvp", "feature toggle", "dynamic pricing",
            "telehealth", "mri", "imaging", "dicom", "hipaa", "clinical", "ledger", "checkout", "payment",
            "stripe", "billing", "fraud", "drone", "quadcopter", "robotics", "embedded", "firmware", "iot",
            "sensor", "telemetry", "monolith", "technical debt", "bottleneck", "failover", "resilience"
        ]

        found_tech = []
        for term in domain_vocabulary:
            if re.search(r'\b' + re.escape(term) + r'\b', lowered):
                found_tech.append(term)

        # PascalCase / Acronyms / CamelCase discovery (e.g. OpenCV, TensorRT, FastAPI, gRPC, NoSQL, ClickHouse)
        capitalized_terms = re.findall(r'\b(?:[A-Z]{2,}|[A-Z][a-z0-9]+[A-Z][a-zA-Z0-9]*)\b', cleaned)
        for cap in capitalized_terms:
            if cap.lower() not in [t.lower() for t in found_tech] and len(cap) > 2:
                if cap.lower() not in {"and", "the", "for", "with", "this", "that", "from", "doctor", "vance"}:
                    found_tech.append(cap)

        # Metrics, Timelines & Quantified Outcomes
        metrics = re.findall(
            r'(?:\$\d+(?:\.\d+)?[kKmMbB]?|\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\s*(?:ms|seconds|minutes|hours|days|weeks|months|years|tps|qps|requests|events|clusters|nodes|users|customers|drop-offs|pts)\b)',
            cleaned,
            re.IGNORECASE
        )

        # Action phrases and target achievements (e.g. "built an autonomous drone", "led the migration from Postgres")
        actions = re.findall(
            r'\b(?:i|we)\s+(?:spearheaded|built|designed|implemented|migrated|optimized|developed|architected|resolved|negotiated|launched|reduced|cut|increased|improved|scaled|benchmarked|managed|led|created|automated|refactored)\s+([^,.?!;]{4,60})',
            cleaned,
            re.IGNORECASE
        )
        clean_actions = []
        for a in actions:
            act = a.strip()
            act_clean = re.sub(r'^(?:a|an|the|our|my)\s+', '', act, flags=re.IGNORECASE).strip()
            if len(act_clean.split()) >= 2:
                clean_actions.append(act_clean)

        # Pull prior context from conversation history if current message is brief
        prior_tech = []
        if conversation_history:
            for past in conversation_history:
                if past.get("role") == "user":
                    past_low = past.get("content", "").lower()
                    for term in domain_vocabulary:
                        if re.search(r'\b' + re.escape(term) + r'\b', past_low) and term not in prior_tech:
                            prior_tech.append(term)

        return {
            "tech": found_tech,
            "metrics": metrics,
            "actions": clean_actions,
            "prior_tech": prior_tech
        }

    def _detect_cv_role_discrepancy(
        self,
        user_message: str,
        cv_text: str = "",
        job_role: str = "",
        experience_level: str = "",
        candidate_name: str = "Candidate"
    ) -> Optional[Dict[str, str]]:
        """
        Detects strong conflicting details between what the candidate stated and what is documented
        in their CV or target Job Role, returning a pointed, professional cross-examination probe if found.
        """
        user_lower = user_message.lower().strip()
        cv_lower = (cv_text or "").lower()
        role_lower = (job_role or "").lower()
        level_lower = (experience_level or "").lower()

        # 1. Seniority Inflation Check (Entry / Junior / Intern claiming C-suite or sole architecture authority)
        is_junior = any(k in level_lower for k in ["entry", "junior", "intern", "associate", "student", "early", "0-1", "1-2"]) or \
                    any(k in cv_lower for k in ["intern", "student", "junior engineer", "graduate student", "research intern"])
        
        seniority_patterns = [
            (r'\b(?:chief\s+architect|principal\s+architect|chief\s+technology\s+officer|cto|vp\s+of\s+engineering|director\s+of\s+engineering)\b', "executive leadership"),
            (r'\b(?:sole\s+architect|solely\s+architected|single-handedly\s+built|single\s+handedly\s+designed|single-handedly\s+architected)\b', "sole architectural authority"),
            (r'\b(?:directed\s+the\s+entire\s+engineering\s+team|oversaw\s+all\s+corporate\s+infrastructure|spearheaded\s+the\s+company-wide\s+overhaul)\b', "company-wide architectural oversight")
        ]
        if is_junior:
            for pattern, label in seniority_patterns:
                match = re.search(pattern, user_lower)
                if match:
                    claim = match.group(0)
                    reaction = f"I noted your remark regarding {claim}, {candidate_name}."
                    probe = (
                        f"Looking at your documented resume highlights, your experience is at the {experience_level or 'entry/associate'} level. "
                        f"Could you clarify the exact boundary of your individual contribution versus senior staff, and help me reconcile that with what is documented on your CV?"
                    )
                    return {
                        "reaction": reaction,
                        "probe": probe,
                        "reasoning": f"Seniority inflation discrepancy: candidate claimed '{claim}' while CV/level indicates '{experience_level or 'entry/junior'}'.",
                        "discrepancy_type": "seniority_inflation"
                    }

        # 2. Domain / Role Mismatch Check
        # A) UX / Design role candidate claiming low-level systems or CUDA kernel development
        is_ux_role = any(k in role_lower for k in ["ux", "user research", "product design", "ui designer"])
        systems_heavy_terms = ["cuda", "kernel driver", "raft consensus", "paxos", "fpga", "verilog", "high-frequency trading", "memory management in c++"]
        if is_ux_role:
            for term in systems_heavy_terms:
                if re.search(r'\b' + re.escape(term) + r'\b', user_lower):
                    reaction = f"I noted that you brought up {term}, {candidate_name}."
                    probe = (
                        f"Your target role is {job_role} and your CV focuses primarily on evaluative research and product design methodologies. "
                        f"Could you explain how your work with {term} connects back to your core user research background, and how it directly informs your qualifications for the {job_role} role?"
                    )
                    return {
                        "reaction": reaction,
                        "probe": probe,
                        "reasoning": f"Domain mismatch discrepancy: UX candidate claimed '{term}'.",
                        "discrepancy_type": "domain_mismatch"
                    }

        # B) Distributed Systems / Backend role candidate giving purely qualitative design responses
        is_backend_role = any(k in role_lower for k in ["backend", "distributed", "systems", "cloud", "devops", "infrastructure"])
        ux_exclusive_terms = ["paper prototypes", "usability test sessions", "color palette selection", "mood boards", "heuristic evaluation of wireframes"]
        if is_backend_role:
            for term in ux_exclusive_terms:
                if re.search(r'\b' + re.escape(term) + r'\b', user_lower):
                    reaction = f"I noted your emphasis on {term}, {candidate_name}."
                    probe = (
                        f"Given that this interview is specifically for the {job_role} position focusing on technical infrastructure and data scalability, "
                        f"could you clarify how {term} relates to the backend engineering and system scalability requirements documented for this role?"
                    )
                    return {
                        "reaction": reaction,
                        "probe": probe,
                        "reasoning": f"Domain mismatch discrepancy: backend candidate claimed '{term}'.",
                        "discrepancy_type": "domain_mismatch"
                    }

        # 3. Explicit Denial of Skills Documented on CV
        denial_patterns = [
            r'\bi\s+(?:have\s+never|haven\'t|never)\s+(?:used|worked\s+with|touched|learned)\s+([a-zA-Z0-9#\+\.]+)\b',
            r'\bi\s+(?:don\'t\s+know|do\s+not\s+know|have\s+no\s+experience\s+with)\s+([a-zA-Z0-9#\+\.]+)\b'
        ]
        for pat in denial_patterns:
            matches = re.finditer(pat, user_lower)
            for m in matches:
                tech_denied = m.group(1).strip()
                if len(tech_denied) >= 3 and re.search(r'\b' + re.escape(tech_denied) + r'\b', cv_lower):
                    reaction = f"I noticed you mentioned that you have no experience with {tech_denied}, {candidate_name}."
                    probe = (
                        f"Your CV specifically highlights {tech_denied} as one of your documented technical competencies. "
                        f"Could you clarify that discrepancy—what was the nature of your exposure to {tech_denied} during the projects listed on your resume?"
                    )
                    return {
                        "reaction": reaction,
                        "probe": probe,
                        "reasoning": f"Direct CV contradiction: candidate denied experience with '{tech_denied}', which is listed on their CV.",
                        "discrepancy_type": "cv_skill_denial"
                    }

        return None

    def _synthesize_semantic_interview_turn(
        self,
        conversation_history: List[Dict[str, str]],
        user_message: str,
        candidate_name: str,
        job_role: str,
        target_company: str,
        experience_level: str,
        interview_type: str,
        interview_duration: str,
        interviewer_tone: str,
        turn_index: int,
        max_turns: int,
        cv_text: str = "",
        job_description: str = ""
    ) -> Dict[str, Any]:
        """
        Generates deeply context-aware, adaptive official interview turns that interpret,
        quote, and probe candidate responses using semantic NLP.
        Adapts dynamically to the candidate's exact words, interview track, and technical domain.
        """
        semantics = self._extract_candidate_semantics(user_message, conversation_history)
        techs = semantics["tech"]
        metrics = semantics["metrics"]
        actions = semantics["actions"]
        prior_techs = semantics["prior_tech"]

        # Extract direct phrase from user message for authentic active listening quote
        clauses = re.findall(r'\b(?:we|i|our team)\s+([a-zA-Z0-9\s\-/]{12,50})(?:[,\.;]|$)', user_message, re.IGNORECASE)
        clean_quote = clauses[0].strip() if clauses else ""

        # Select primary conversational anchor from candidate statements
        if actions:
            primary_topic = actions[0]
        elif len(techs) >= 2:
            primary_topic = f"{techs[0]} and {techs[1]}"
        elif techs:
            primary_topic = techs[0]
        elif prior_techs:
            primary_topic = prior_techs[0]
        else:
            words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', user_message) if w.lower() not in {
                'this', 'that', 'with', 'from', 'have', 'been', 'would', 'could', 'their', 'about',
                'which', 'there', 'good', 'morning', 'afternoon', 'hello', 'thank', 'thanks', 'role'
            }]
            primary_topic = words[0] if words else f"{job_role} architecture"

        company_ref = f" at {target_company}" if target_company else ""
        metric_cite = f" (specifically achieving {metrics[0]})" if metrics else ""
        quote_cite = f", particularly when you noted that you “{clean_quote}”" if clean_quote else ""

        # 1. User-Communicated Conclusion Trigger
        if self._is_user_requesting_wrapup(user_message):
            closing_speech = (
                f"Thank you, {candidate_name}. You have shared thoughtful, concrete insights today across your projects and decision-making. "
                f"We have covered all the requisite competencies and dimensions for the {job_role} position. "
                f"That officially concludes our oral interview questioning. Whenever you are ready, please proceed to review your comprehensive Hiring Committee Evaluation Scorecard."
            )
            return {
                "interviewer_message": closing_speech,
                "followup_question": closing_speech,
                "reasoning": "Candidate communicated wrap-up intent; concluding interview naturally.",
                "turn_index": turn_index + 1,
                "is_concluded": True,
                "source": "adaptive_ai_dialogue_engine",
                "extracted_topic": primary_topic,
                "extracted_metrics": metrics
            }

        # 2. Mandatory CV & Job Role Discrepancy Cross-Examination
        discrepancy = self._detect_cv_role_discrepancy(
            user_message=user_message,
            cv_text=cv_text,
            job_role=job_role,
            experience_level=experience_level,
            candidate_name=candidate_name
        )
        if discrepancy:
            full_reply = f"{discrepancy['reaction']} {discrepancy['probe']}"
            return {
                "interviewer_message": full_reply,
                "followup_question": full_reply,
                "reasoning": discrepancy["reasoning"],
                "turn_index": turn_index + 1,
                "is_concluded": False,
                "source": "adaptive_ai_dialogue_engine",
                "extracted_topic": primary_topic,
                "extracted_metrics": metrics,
                "discrepancy_detected": True,
                "discrepancy_type": discrepancy["discrepancy_type"]
            }

        # 3. Interviewer-Initiated Conclusion: Needful Information Extracted
        # (Once technical architecture, trade-off/conflict, and measurable outcomes have been collected by Turn 4+)
        if turn_index >= max_turns or (turn_index >= 4 and (len(metrics) > 0 or len(techs) > 0 or turn_index >= 5)):
            reaction = (
                f"Thank you for sharing those comprehensive insights and verified outcomes on {primary_topic}{metric_cite}, {candidate_name}."
            )
            probe = (
                f"You have provided clear, concrete evidence across your system architecture, trade-off resolution, and measurable business impact. "
                f"I now have extracted all the needful signals required to convene our hiring committee and finalize your evaluation. "
                f"That brings our oral interview questioning to a natural close. Whenever you're ready, please proceed to review your official scorecard."
            )
            full_reply = f"{reaction} {probe}"
            return {
                "interviewer_message": full_reply,
                "followup_question": full_reply,
                "reasoning": f"Sufficient hiring signals extracted across all key competencies (Turn {turn_index}). Interview naturally concluded.",
                "turn_index": turn_index + 1,
                "is_concluded": True,
                "source": "adaptive_ai_dialogue_engine",
                "extracted_topic": primary_topic,
                "extracted_metrics": metrics
            }

        int_lower = (interview_type or "").lower()
        is_tech = "technical" in int_lower or "system" in int_lower or "architecture" in int_lower
        is_ux = "ux" in (job_role or "").lower() or "research" in (job_role or "").lower() or "design" in (job_role or "").lower()
        is_pm = "product" in (job_role or "").lower() or "apm" in (job_role or "").lower() or "strategy" in int_lower

        # Construct Stage-by-Stage tailored responses
        if turn_index == 1:
            if is_tech:
                reaction = (
                    f"Thank you for introducing yourself and walking me through your background, {candidate_name}. "
                    f"Your foundation across {primary_topic}{metric_cite} establishes strong context for our engineering discussion today{company_ref}."
                )
                probe = (
                    f"To start our technical deep-dive questions: looking at your direct work on {primary_topic}{quote_cite}, could you walk me through the end-to-end data flow when a request or write is committed, "
                    f"how you maintained strict consistency, and what specific design trade-offs you accepted along the way?"
                )
            elif is_ux:
                reaction = (
                    f"Thank you for introducing yourself and sharing your background, {candidate_name}. "
                    f"Grounding product iterations in structured user research around {primary_topic} is central to how we design{company_ref}."
                )
                probe = (
                    f"To begin our targeted questions: looking at that initiative on {primary_topic}{quote_cite}, walk me through your participant recruitment and research methodology—how did you ensure your sample was unbiased, and how did you translate raw qualitative observations into prioritized product recommendations?"
                )
            elif is_pm:
                reaction = (
                    f"Thank you for introducing yourself and walking through your career journey, {candidate_name}. "
                    f"Driving measurable business momentum across {primary_topic}{metric_cite} is exactly what we look for in our product leads{company_ref}."
                )
                probe = (
                    f"To start our product execution questions: zooming in on your ownership of {primary_topic}{quote_cite}, how did you define the North Star metric, and what framework did you use to prioritize feature scope when engineering capacity was constrained?"
                )
            else:
                reaction = (
                    f"Thank you for introducing yourself and walking through your background, {candidate_name}. "
                    f"Your track record across {primary_topic}{metric_cite} clearly aligns with the core requirements of this {job_role} role{company_ref}."
                )
                probe = (
                    f"To kick off our targeted questions: diving into your work on {primary_topic}{quote_cite}, could you walk me through the most technically or operationally complex initiative you spearheaded there, and what specific roadblock you had to overcome?"
                )

        elif turn_index == 2:
            if is_tech:
                reaction = (
                    f"I appreciate that deep-dive into {primary_topic}, {candidate_name}. "
                    f"Making architectural decisions under high-throughput constraints inevitably surfaces conflicting technical viewpoints among engineering peers."
                )
                probe = (
                    f"Tell me about a specific time while architecting {primary_topic} where you had a significant technical disagreement with a teammate, tech lead, or SRE partner regarding design trade-offs. "
                    f"What was the core debate, what objective benchmarks or prototypes did you use to substantiate your position, and how did you reach alignment?"
                )
            elif is_ux:
                reaction = (
                    f"That shows rigorous research discipline on {primary_topic}, {candidate_name}."
                )
                probe = (
                    f"Tell me about a time during that project where your evaluative research contradicted the strong intuitions or roadmap commitments of an engineering lead or product manager. "
                    f"How did you present the contradictory data diplomatically, and how did you resolve the friction?"
                )
            elif is_pm:
                reaction = (
                    f"That shows strong customer empathy and strategic thinking regarding {primary_topic}, {candidate_name}."
                )
                probe = (
                    f"Tell me about a high-stakes trade-off during that cycle where engineering pushed to address technical debt while business stakeholders demanded immediate feature delivery. "
                    f"How did you resolve the conflicting priorities and negotiate a phased milestone agreement?"
                )
            else:
                reaction = (
                    f"I appreciate that context around {primary_topic}, {candidate_name}. "
                    f"Navigating operational hurdles under those constraints inevitably creates cross-team tension."
                )
                probe = (
                    f"Tell me about a specific time during that project where you encountered a significant disagreement with a teammate or cross-functional partner. "
                    f"What was the dispute, how did you handle the interpersonal dynamics, and what was the resolution?"
                )

        elif turn_index == 3 and turn_index < max_turns:
            if is_tech:
                reaction = (
                    f"Resolving architectural debates with empirical benchmarks around {primary_topic} demonstrates senior engineering maturity, {candidate_name}."
                )
                probe = (
                    f"Looking at operational resilience: when sudden traffic surges, network partitions, or dependency failures struck that system{metric_cite}, how did your architecture respond? "
                    f"What failover mechanics, circuit breakers, or recovery runbooks did you put in place to ensure zero data anomalies?"
                )
            elif is_ux:
                reaction = (
                    f"Advocating for the user with indisputable evidence is the hallmark of great UX research, {candidate_name}."
                )
                probe = (
                    f"When sprint deadlines compress and product squads ask to skip full discovery cycles, how do you maintain research rigor? "
                    f"How do you decide between quick unmoderated tests versus in-depth longitudinal studies under time pressure?"
                )
            elif is_pm:
                reaction = (
                    f"Balancing technical debt against growth velocity requires rigorous commercial discipline, {candidate_name}."
                )
                probe = (
                    f"How did you validate that feature release using A/B experimentation or staged rollouts? "
                    f"What guardrail metrics did you monitor to ensure your primary conversion lift didn't cannibalize other key areas of the user journey?"
                )
            else:
                reaction = (
                    f"Navigating technical disagreements with objective data is essential in high-impact teams, {candidate_name}."
                )
                probe = (
                    f"Looking back on that solution: when unexpected scale surges, requirement changes, or system dependencies arose, how did you handle bottlenecks and failure modes to ensure reliability?"
                )

        elif turn_index == 4 and turn_index < max_turns:
            reaction = (
                f"That demonstrates strong systems thinking and execution discipline on {primary_topic}, {candidate_name}."
            )
            probe = (
                f"Beyond implementation delivery, how did you verify the measurable outcome and business impact? "
                f"What concrete quantitative metrics, KPIs, or telemetry dashboards validated that this project achieved its goal{metric_cite}?"
            )

        elif turn_index == 5 and turn_index < max_turns:
            reaction = (
                f"Those are compelling insights and verified outcomes for {primary_topic}{metric_cite}, {candidate_name}."
            )
            probe = (
                f"If you had to reflect on that entire lifecycle with the benefit of hindsight, what was the single biggest architectural compromise, assumption, or design choice you would do differently today?"
            )

        elif turn_index == 6 and turn_index < max_turns:
            reaction = (
                f"That reflective self-awareness and willingness to dissect technical debt are hallmarks of leadership, {candidate_name}."
            )
            probe = (
                f"Looking at organizational impact: how do you translate these complex technical or domain nuances to non-technical stakeholders, and how do you mentor junior teammates to raise engineering standards across the org?"
            )

        elif turn_index >= 7 and turn_index < max_turns:
            reaction = (
                f"Upholding standards across {primary_topic} while mentoring peers creates compounding leverage, {candidate_name}."
            )
            probe = (
                f"To round out our technical evaluation: how do you stay ahead of emerging industry standards and ensure your team's architecture remains resilient over a multi-year horizon?"
            )

        else:
            reaction = (
                f"Those are impressive insights and verified outcomes across {primary_topic}, {candidate_name}."
            )
            probe = (
                f"Thank you for sharing your experience and technical depth with me today—it gave me a great window into how you architect solutions, collaborate through friction, and deliver impact. "
                f"That brings our oral interview questioning to a close. When you're ready, proceed to review your official Hiring Committee Evaluation Scorecard."
            )

        full_reply = f"{reaction} {probe}"
        return {
            "interviewer_message": full_reply,
            "followup_question": full_reply,
            "reasoning": f"Adaptive Semantic Dialogue probe interpreting: {primary_topic}{metric_cite}.",
            "turn_index": turn_index + 1,
            "is_concluded": turn_index >= max_turns,
            "source": "semantic_dialogue_engine",
            "extracted_topic": primary_topic,
            "extracted_metrics": metrics
        }

    async def evaluate_answer_ai(
        self,
        question_text: str,
        answer_text: str,
        job_role: str = "General",
        attempt_number: int = 1,
        candidate_name: str = "Candidate",
        target_company: str = "",
        experience_level: str = "",
        cv_text: str = "",
        job_description: str = ""
    ) -> EvaluationResult:
        """
        Evaluates a candidate's answer against the STAR rubric.
        Priority:
        1. OpenRouter (NVIDIA Nemotron 3.5 Super VL)
        2. Gemini 1.5 Flash
        3. Deterministic STAR Rubric Evaluator
        """
        base_eval = self.evaluate_answer(question_text, answer_text, job_role, attempt_number)
        if len(answer_text.strip().split()) < 15:
            try:
                base_eval.adaptive_followup = await self.generate_adaptive_followup_ai(
                    previous_question=question_text,
                    user_answer=answer_text,
                    job_role=job_role,
                    candidate_name=candidate_name,
                    cv_text=cv_text
                )
            except Exception:
                pass
            return base_eval

        openrouter_success = False
        api_key = self.get_openrouter_api_key()
        if api_key:
            cand_profile_str = f"Candidate: {candidate_name}, Role: {job_role}"
            if target_company:
                cand_profile_str += f", Target Company: {target_company}"
            if experience_level:
                cand_profile_str += f", Level: {experience_level}"
            if cv_text:
                cand_profile_str += f"\nResume context: {cv_text[:300]}"

            system_prompt = (
                f"You are a master interview coach and evaluator reviewing answers for the role: '{job_role}'. "
                f"Tailor feedback to the candidate's target company and seniority expectations."
            )
            user_prompt = f"""Candidate Profile:
{cand_profile_str}

Question asked:
"{question_text}"

Candidate's spoken answer:
"{answer_text}"

Baseline automated rubric scores:
- Relevance: {base_eval.relevance.score}/10
- Specificity: {base_eval.specificity.score}/10
- Evidence & Outcome: {base_eval.evidence_outcome.score}/10
- Structure & Clarity: {base_eval.structure_clarity.score}/10

Please provide expert, constructive evaluation in JSON format:
1. 2 distinct strengths
2. 2 distinct areas for improvement
3. 1 concrete actionable recommendation following the STAR method
4. An improved model response demonstrating how to include measurable outcomes and concrete details tailored to this profile.

Respond ONLY with a JSON object in this format:
{{
  "strengths": ["...", "..."],
  "needs_improvement": ["...", "..."],
  "actionable_suggestions": ["..."],
  "example_improved_answer": "..."
}}
"""
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            try:
                content = await self.call_openrouter(messages, temperature=0.5, max_tokens=2500)
                if content:
                    parsed = self._clean_json_output(content)
                    if isinstance(parsed, dict):
                        strengths = parsed.get("strengths") or []
                        if isinstance(strengths, list) and strengths:
                            base_eval.strengths = [str(s) for s in strengths]

                        needs_imp = parsed.get("needs_improvement") or parsed.get("areas_for_improvement") or []
                        if isinstance(needs_imp, list) and needs_imp:
                            base_eval.needs_improvement = [str(n) for n in needs_imp]

                        actionable = parsed.get("actionable_suggestions") or parsed.get("recommendations") or []
                        if isinstance(actionable, list) and actionable:
                            base_eval.actionable_suggestions = [str(a) for a in actionable]

                        improved = parsed.get("example_improved_answer") or parsed.get("improved_answer") or parsed.get("sample_answer")
                        if improved:
                            base_eval.example_improved_answer = str(improved)

                        base_eval.why_feedback_summary["evaluator_engine"] = "openrouter_nemotron"
                        openrouter_success = True
            except Exception as e:
                logger.warning(f"OpenRouter answer evaluation failed, falling back: {e}")

        # Fallback to Gemini if OpenRouter did not evaluate
        if not openrouter_success:
            gemini_key = self.get_gemini_api_key()
            if gemini_key:
                try:
                    base_eval = await self.evaluate_answer_gemini(
                        question_text,
                        answer_text,
                        job_role,
                        attempt_number,
                        api_key=gemini_key,
                        candidate_name=candidate_name,
                        target_company=target_company,
                        experience_level=experience_level,
                        cv_text=cv_text
                    )
                except Exception as e:
                    logger.warning(f"Gemini answer evaluation failed, retaining deterministic base: {e}")

        # Always attach contextually grounded adaptive AI follow-up probe for next round / revision
        try:
            base_eval.adaptive_followup = await self.generate_adaptive_followup_ai(
                previous_question=question_text,
                user_answer=answer_text,
                job_role=job_role,
                candidate_name=candidate_name,
                target_company=target_company,
                experience_level=experience_level,
                cv_text=cv_text,
                job_description=job_description
            )
        except Exception as e:
            logger.warning(f"Failed to attach adaptive follow-up to evaluation result: {e}")

        return base_eval

    def get_track_competencies(self, interview_type: str = "") -> List[Dict[str, str]]:
        """
        Returns the 5 industry-standard competencies and behavioral rubrics for the given interview track,
        including a dedicated combined metric for politeness, refined language, open-ended inquiry, and follow-through.
        """
        politeness_metric = {
            "id": "politeness_refined_language_inquiry",
            "name": "Politeness, Refined Language & Inquiry Follow-Through",
            "weight": 0.15,
            "focus": "Professional courtesy, eloquent vocabulary without fillers, proactive open-ended questions, and conversational follow-through.",
            "definition": "Measures candidate interpersonal grace: courteous greetings and acknowledgments, polished and precise vocabulary without slang or fillers, engaging in constructive two-way dialogue by asking open-ended questions, and closing loops by following through on previous interviewer inquiries.",
            "high_anchor": "Consistently courteous and gracious (e.g., 'Thank you Dr. Vance'); uses eloquent, precise industry vocabulary; proactively poses insightful open-ended questions back to the evaluator; maintains seamless conversational follow-through connecting ideas across turns.",
            "mid_anchor": "Professional and polite baseline, but maintains an entirely passive conversational stance without posing open-ended questions; vocabulary is standard without noticeable polish or follow-through.",
            "low_anchor": "Abrupt, curt, or defensive tone; frequent conversational filler words or unrefined slang; completely ignores previous interviewer context and asks zero clarifying or follow-through questions."
        }

        t = (interview_type or "").lower()
        if "behavioral" in t or "star" in t or "leadership" in t:
            return [
                {
                    "id": "star_rigor",
                    "name": "STAR Framework Rigor & Specificity",
                    "weight": 0.25,
                    "focus": "Demarcation of Situation, Task, Action, and quantifiable Business Result.",
                    "definition": "Measures how systematically the candidate structures past experiences using the STAR method (Situation, Task, Action, Result), emphasizing distinct personal agency and verified quantitative outcomes.",
                    "high_anchor": "Structures answer seamlessly with exact context, personal ownership of actions, and measurable metrics.",
                    "mid_anchor": "Provides solid narrative but glosses over metrics or uses collective 'we' instead of personal action.",
                    "low_anchor": "Vague situational sketch without concrete actions or clear end results."
                },
                {
                    "id": "ownership_agency",
                    "name": "Ownership, Initiative & Bias for Action",
                    "weight": 0.20,
                    "focus": "Personal agency, taking responsibility for outcomes, and navigating ambiguity.",
                    "definition": "Assesses the candidate's proactive ownership, accountability for mistakes, and willingness to step outside their comfort zone to unblock initiatives without waiting for top-down direction.",
                    "high_anchor": "Demonstrates relentless ownership; unblocks teammates, challenges status quo, and embraces accountability.",
                    "mid_anchor": "Executes assigned responsibilities well, but hesitates to take unprompted initiative during ambiguity.",
                    "low_anchor": "Passes blame to external factors, stakeholders, or constraints; passive execution."
                },
                {
                    "id": "conflict_collaboration",
                    "name": "Stakeholder Alignment & Conflict Resolution",
                    "weight": 0.20,
                    "focus": "Active listening, empathy, resolving technical or interpersonal tension constructively.",
                    "definition": "Evaluates emotional intelligence, active listening, and the ability to navigate high-stakes technical or cross-functional disagreements constructively using objective data and mutual empathy.",
                    "high_anchor": "Employs data-backed de-escalation, seeks common ground, and rallies cross-functional stakeholders.",
                    "mid_anchor": "Manages interpersonal friction politely but tends to avoid difficult confrontations or rely on escalation.",
                    "low_anchor": "Shows defensiveness, rigid mindset, or dismissiveness toward dissenting perspectives."
                },
                {
                    "id": "growth_humility",
                    "name": "Learning Agility & Post-Mortem Reflection",
                    "weight": 0.20,
                    "focus": "Dissecting failures objectively, extracting systemic lessons, and coaching others.",
                    "definition": "Examines learning agility, self-awareness, receptiveness to constructive feedback, and the ability to conduct blameless post-mortems on past failures to implement systemic guardrails.",
                    "high_anchor": "Openly shares impactful missteps, highlights root causes, and implements lasting systemic guardrails.",
                    "mid_anchor": "Acknowledges errors with guidance, but focuses on tactical rather than systemic preventative measures.",
                    "low_anchor": "Reluctant to admit shortcomings or claims zero regrets/mistakes in past roles."
                },
                politeness_metric
            ]
        elif "technical" in t or "architecture" in t or "system design" in t:
            return [
                {
                    "id": "arch_soundness",
                    "name": "Architecture Soundness & Trade-off Analysis",
                    "weight": 0.25,
                    "focus": "Component decoupling, data store selection, and justifying CAP theorem trade-offs.",
                    "definition": "Evaluates architectural design choices, component modularity, distributed consensus protocols, and the ability to defend throughput, latency, and CAP theorem trade-offs under high-scale constraints.",
                    "high_anchor": "Articulates crisp architectural diagrams, explicitly evaluating throughput vs latency and consistency trade-offs.",
                    "mid_anchor": "Proposes viable standard architecture but struggles to justify specific database or protocol choices under scrutiny.",
                    "low_anchor": "Monolithic or brittle architecture; misses major bottlenecks or suggests anti-patterns."
                },
                {
                    "id": "scalability_concurrency",
                    "name": "Scalability, Concurrency & Bottleneck Handling",
                    "weight": 0.20,
                    "focus": "Horizontal scaling, sharding, caching tiers, and back-pressure mitigation.",
                    "definition": "Assesses understanding of horizontal partitioning, distributed caching, concurrency models, hot partition mitigation, and backpressure handling under peak traffic.",
                    "high_anchor": "Proactively addresses hot spots, cache invalidation, asynchronous queuing, and partition keys.",
                    "mid_anchor": "Applies standard caching (Redis) and load balancers, but overlooks database replication lag or write limits.",
                    "low_anchor": "Fails to scale past single-node limits; unable to identify single points of failure."
                },
                {
                    "id": "fault_tolerance",
                    "name": "Failure Modes, Edge Cases & Fault Tolerance",
                    "weight": 0.20,
                    "focus": "Graceful degradation, idempotency, circuit breakers, and retry storm resilience.",
                    "definition": "Measures resilience design, including graceful degradation, circuit breakers, dead-letter queues, idempotent writes, and disaster recovery strategies during downstream service outages.",
                    "high_anchor": "Anticipates network partitions, dead-letter queues, exactly-once vs at-least-once delivery, and recovery.",
                    "mid_anchor": "Acknowledges failure possibilities, but relies on naive retries without jitter or exponential backoff.",
                    "low_anchor": "Assumes 'happy path'; systems crash completely during downstream dependencies downtime."
                },
                {
                    "id": "production_depth",
                    "name": "Production Readiness & Operational Observability",
                    "weight": 0.20,
                    "focus": "Distributed tracing, SLO/SLA budgeting, zero-downtime deployments, and security.",
                    "definition": "Evaluates operational maturity, including distributed tracing (OpenTelemetry), SLO/SLA error budgets, canary deployment pipelines, rollback criteria, and zero-downtime database migrations.",
                    "high_anchor": "Integrates comprehensive OpenTelemetry metrics, canary releases, rollback criteria, and data encryption.",
                    "mid_anchor": "Mentions logs and basic CI/CD, but lacks depth on alerting thresholds, runbooks, or zero-downtime migrations.",
                    "low_anchor": "Treats deployment and monitoring as an afterthought; neglects security and operational health."
                },
                politeness_metric
            ]
        elif "product" in t or "analytical" in t or "strategy" in t:
            return [
                {
                    "id": "problem_framing",
                    "name": "Problem Framing & User Empathy",
                    "weight": 0.25,
                    "focus": "Deconstructing ambiguous market problems and pinpointing true user pain points.",
                    "definition": "Assesses user empathy, market opportunity sizing, and the ability to deconstruct ambiguous customer problems into clear, prioritized problem statements before jumping to solutions.",
                    "high_anchor": "Structures ambiguity with a disciplined user-first lens; identifies unarticulated user friction and opportunity size.",
                    "mid_anchor": "Understands the core user, but jumps too quickly to feature solutions without validating problem root causes.",
                    "low_anchor": "Builds features looking for a problem; lacks customer empathy and segment definition."
                },
                {
                    "id": "metrics_rigor",
                    "name": "Metric Definition & Analytical Rigor",
                    "weight": 0.20,
                    "focus": "North Star metric, input/guardrail metrics, and hypothesis-driven experimentation.",
                    "definition": "Measures the ability to define North Star metrics, input metrics, paired guardrail metrics (e.g. engagement vs cannibalization), and hypothesis-driven A/B testing methodologies.",
                    "high_anchor": "Designs nuanced metric trees with pairing guardrails (e.g., engagement vs churn) and statistical experiment rigor.",
                    "mid_anchor": "Proposes valid primary metrics (e.g., CTR or DAU), but misses cannibalization risks or counter-metrics.",
                    "low_anchor": "Relies on vanity metrics without clear causal links to business or user value."
                },
                {
                    "id": "strategic_tradeoffs",
                    "name": "Strategic Prioritization & Trade-off Calculus",
                    "weight": 0.20,
                    "focus": "RICE/MoSCoW frameworks, effort vs impact, defensibility, and competitive moat.",
                    "definition": "Evaluates ruthless prioritization frameworks (RICE, MoSCoW), competitive moat defensibility, and the conviction to articulate what NOT to build under severe resource constraints.",
                    "high_anchor": "Ruthlessly prioritizes high-leverage bets; articulates what NOT to build and defends rationale with conviction.",
                    "mid_anchor": "Prioritizes logically, but struggles when forced to cut favored features under severe engineering constraints.",
                    "low_anchor": "Attempts to do everything simultaneously; lacks strategic focus and clear priority criteria."
                },
                {
                    "id": "gtm_velocity",
                    "name": "Go-to-Market & Execution Roadmapping",
                    "weight": 0.20,
                    "focus": "Phased rollouts, cross-functional choreography, feedback loops, and scaling velocity.",
                    "definition": "Assesses roadmapping execution, alpha/beta cohort rollout staging, stakeholder alignment, feedback loops, and rapid product-market iteration velocity.",
                    "high_anchor": "Outlines detailed alpha/beta cohorts, sales/marketing enablement, and rapid feedback iteration cycles.",
                    "mid_anchor": "Creates a functional launch schedule, but overlooks edge-case user support or internal enablement bottlenecks.",
                    "low_anchor": "Treats shipping code as launch completion; neglects user adoption and iterative loops."
                },
                politeness_metric
            ]
        else:
            # Comprehensive Mixed Mock
            return [
                {
                    "id": "role_depth",
                    "name": "Role-Specific Technical Proficiency",
                    "weight": 0.25,
                    "focus": "Depth of specialized domain knowledge, practical craftsmanship, and technical fluency.",
                    "definition": "Assesses depth of specialized technical domain knowledge, practical craftsmanship, industry-standard toolchain fluency, and authoritative technical command.",
                    "high_anchor": "Speaks with seasoned authority; articulates complex concepts with clarity and precision.",
                    "mid_anchor": "Solid grasp of foundational concepts, but requires probing to reach deep architectural or domain nuances.",
                    "low_anchor": "Superficial knowledge; relies on buzzwords without understanding underlying mechanics."
                },
                {
                    "id": "behavioral_ownership",
                    "name": "STAR Behavioral Execution & Ownership",
                    "weight": 0.20,
                    "focus": "Structured storytelling, personal accountability for results, and measurable business outcomes.",
                    "definition": "Measures structured storytelling using the STAR framework, personal accountability for results, and clear demarcation of individual contribution versus team achievements.",
                    "high_anchor": "Delivers crisp STAR responses with distinct personal actions and verified quantitative impact.",
                    "mid_anchor": "Good stories with clear lessons, but uses generalized language rather than concrete personal actions.",
                    "low_anchor": "Meandering answers that fail to explain the actual challenge or candidate's personal contribution."
                },
                {
                    "id": "systemic_problem_solving",
                    "name": "Systemic Problem Solving & Trade-offs",
                    "weight": 0.20,
                    "focus": "Decomposing complex ambiguity, evaluating multiple options, and managing trade-offs.",
                    "definition": "Evaluates how logically the candidate decomposes complex ambiguity, surfaces hidden assumptions, weighs competing alternatives, and manages multi-variable trade-offs.",
                    "high_anchor": "Systematically breaks down problems, lists assumptions, and weighs pros/cons before choosing a path.",
                    "mid_anchor": "Finds a reasonable solution, but anchors on the first idea without exploring alternative designs.",
                    "low_anchor": "Impulsive decision making; unable to explain why one approach was chosen over another."
                },
                {
                    "id": "executive_communication",
                    "name": "Executive Communication & Strategic Alignment",
                    "weight": 0.20,
                    "focus": "Concise delivery, active listening, and alignment with target company mission and level bar.",
                    "definition": "Measures concise delivery, high signal-to-noise ratio, active listening, executive presence, and alignment with target company mission and level expectations.",
                    "high_anchor": "High signal-to-noise ratio; commands executive presence, listens actively, and adapts to interviewer cues.",
                    "mid_anchor": "Communicates effectively, but occasionally over-explains minor points or requires minor refocusing.",
                    "low_anchor": "Rambling, evasive, or unfocused; ignores interviewer prompts and questions."
                },
                politeness_metric
            ]

    def _extract_turn_pairs(self, conversation_history: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Extracts interviewer-question and candidate-response pairs from conversation history.
        """
        turns = []
        current_q = ""
        turn_idx = 1
        for msg in conversation_history:
            role = msg.get("role")
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role == "assistant":
                current_q = content
            elif role == "user":
                turns.append({
                    "turn_index": turn_idx,
                    "question": current_q or f"Question {turn_idx}",
                    "answer": content
                })
                current_q = ""
                turn_idx += 1
        return turns

    def _evaluate_simulation_deterministic(
        self,
        turns: List[Dict[str, Any]],
        candidate_name: str,
        job_role: str,
        target_company: str,
        experience_level: str,
        interview_type: str,
        interview_duration: str,
        interviewer_tone: str,
        cv_text: str,
        job_description: str
    ) -> Dict[str, Any]:
        """
        High-fidelity deterministic fallback for multi-turn simulation evaluation.
        Produces deep, track-specific, question-by-question evidence, JD audit, and rubric scores.
        """
        competencies = self.get_track_competencies(interview_type)
        all_user_text = " ".join([t["answer"] for t in turns])
        total_words = len(all_user_text.split())
        
        # Rigor multiplier
        is_probing = "challenging" in (interviewer_tone or "").lower() or "high bar" in (interviewer_tone or "").lower()
        is_supportive = "supportive" in (interviewer_tone or "").lower()
        
        # Analyze metrics and quantitative evidence
        numbers_found = re.findall(r'\b\d+(?:\.\d+)?%?\b', all_user_text)
        metric_signals = [n for n in numbers_found if not n.startswith("202") and n not in ["1", "2", "3", "4", "5"]]
        
        # Evaluate turns individually
        turn_evaluations = []
        turn_scores = []
        
        stage_names = [
            "Stage 1: Background, Trajectory & Role Alignment",
            "Stage 2: Technical & Project Execution Probe",
            "Stage 3: Behavioral, Conflict & Cross-Functional Alignment",
            "Stage 4: Quantified Business Impact & Edge Cases",
            "Stage 5: Synthesis, Reflection & Executive Delivery"
        ]

        for i, turn in enumerate(turns):
            ans = turn["answer"]
            words = len(ans.split())
            t_score = 6.0
            
            # Content richness
            if words > 70:
                t_score += 1.5
            elif words > 40:
                t_score += 0.8
            elif words < 20:
                t_score -= 1.5
                
            # Evidence of metrics or exact technical nouns
            has_metrics = bool(re.search(r'\b\d+(?:\.\d+)?%|\b\d+x\b|\b\d+\s*(?:ms|k|m|users|engineers|queries|qps)\b', ans, re.I))
            if has_metrics:
                t_score += 1.0
                
            # Ownership words
            if re.search(r'\b(?:i led|i designed|i architected|i decided|my responsibility|i identified)\b', ans, re.I):
                t_score += 0.7
            if re.search(r'\b(?:we just|someone else|not my fault)\b', ans, re.I):
                t_score -= 0.8
                
            # Track-specific keywords
            t_lower = (interview_type or "").lower()
            if "technical" in t_lower or "architecture" in t_lower:
                if re.search(r'\b(?:latency|throughput|cache|partition|sharding|kafka|consensus|bottleneck|redis|sql|api|microservices)\b', ans, re.I):
                    t_score += 0.8
            elif "behavioral" in t_lower or "star" in t_lower:
                if re.search(r'\b(?:situation|task|action|result|disagree|compromise|alignment|teammate|feedback)\b', ans, re.I):
                    t_score += 0.8
            elif "product" in t_lower:
                if re.search(r'\b(?:metric|kpi|user|funnel|retention|conversion|experiment|hypothesis|trade-off|north star)\b', ans, re.I):
                    t_score += 0.8

            if is_probing:
                t_score -= 0.4
            elif is_supportive:
                t_score += 0.3

            t_score = max(4.0, min(9.8, round(t_score, 1)))
            turn_scores.append(t_score)

            stage_name = stage_names[i] if i < len(stage_names) else f"Stage {i+1}: Advanced Domain Probe"
            
            # Extract sample quote for positive evidence
            sentences = [s.strip() for s in re.split(r'[.!?]', ans) if len(s.strip().split()) >= 4]
            sample_quote = sentences[0] if sentences else ans[:80]
            
            # Identify strengths & gaps
            strengths = []
            gaps = []
            if words >= 40:
                strengths.append(f'Demonstrated direct domain familiarity: "{sample_quote[:90]}..."')
            if has_metrics:
                strengths.append("Incorporated concrete quantitative outcomes and performance metrics into the response.")
            else:
                gaps.append("Omitted quantified baseline and end-result metrics (e.g. latency deltas, throughput figures, user volume).")
                
            if not re.search(r'\b(?:i|my)\b', ans, re.I) and "we" in ans.lower():
                gaps.append("Relied heavily on team pronoun 'we'; specify your personal direct architectural/strategic contribution.")
            else:
                strengths.append("Established clear personal ownership and agency in decision-making.")

            if not gaps:
                gaps.append("Could further contextualize alternative approaches considered before arriving at the chosen path.")

            comp_for_turn = competencies[i % len(competencies)]["name"]
            
            turn_evaluations.append({
                "turn_index": turn["turn_index"],
                "stage_name": stage_name,
                "interviewer_question": turn["question"],
                "candidate_response": ans,
                "turn_score": t_score,
                "competency_tested": comp_for_turn,
                "strengths_observed": strengths,
                "gaps_identified": gaps,
                "coached_exemplar": f"At {target_company or 'top-tier tech'}, elevate this response by structuring with exact context: 'When faced with [X bottleneck], I personally took ownership of [Y action], leading to [Z quantified metric delta] while managing [trade-off W].'"
            })

        # Ambiguity & Early Termination Analysis
        num_turns = len(turns)
        total_words = len(all_user_text.split())
        avg_words_per_turn = total_words / num_turns if num_turns > 0 else 0
        
        # An interview is ended early or lacks sufficient data if:
        # - Fewer than 3 turns were completed, OR
        # - Total words spoken by the candidate is under 110 words, OR
        # - 3 turns were completed but candidate answers were exceptionally sparse (avg < 30 words)
        is_ambiguous = (num_turns <= 2) or (total_words < 110) or (num_turns <= 3 and avg_words_per_turn < 30)

        ambiguity_notice = None
        if is_ambiguous:
            missing_dimensions = []
            if num_turns <= 1:
                missing_dimensions = [
                    "Technical Architecture & System Mechanics Deep Dive",
                    "Behavioral Conflict, Trade-Offs & Teammate Alignment",
                    "Edge-Case Resilience, Failure Modes & Fault Recovery",
                    "Quantified Business Impact & Measurable Outcome Substantiation"
                ]
            elif num_turns == 2:
                missing_dimensions = [
                    "Behavioral Conflict Resolution & High-Stakes Disagreement",
                    "System Resilience Under Partition & Error Recovery",
                    "Long-Term Quantitative Outcomes & Metric Accountability"
                ]
            else:
                missing_dimensions = [
                    "Deep-Dive Technical Trade-Off Defensibility Under Scrutiny",
                    "Comprehensive Edge-Case Fault Tolerance Verification"
                ]

            ambiguity_notice = {
                "is_ambiguous": True,
                "severity": "HIGH" if num_turns <= 2 else "MODERATE",
                "turn_count": num_turns,
                "word_count": total_words,
                "headline": "⚠️ Evaluation Ambiguity Notice: Premature Interview Conclusion",
                "explanation": (
                    f"This interview session concluded early after only {num_turns} conversational turn{'s' if num_turns != 1 else ''} "
                    f"({total_words} total words spoken). Because the dialogue terminated before the full questioning battery could be administered, "
                    f"critical competency dimensions could not be reliably probed or evidenced under realistic corporate hiring conditions."
                ),
                "unassessed_dimensions": missing_dimensions,
                "hiring_committee_advisory": (
                    "Ratings and scores displayed below represent provisional baseline estimates with elevated statistical ambiguity. "
                    "The hiring committee strongly recommends scheduling a 20–30 minute targeted technical follow-up session to resolve "
                    "these unassessed competencies before making an official hiring decision."
                )
            }

        confidence_rating = (
            f"Low Confidence / High Ambiguity (Only {num_turns} Turn{'s' if num_turns != 1 else ''} Completed • Sparse Evidence)"
            if is_ambiguous else
            f"High Confidence ({num_turns} Verified Dialogue Turns • {total_words} Spoken Words)"
        )

        # Calculate competency matrix scores
        avg_turn_score = sum(turn_scores) / len(turn_scores) if turn_scores else 7.5
        comp_matrix = []
        overall_weighted = 0.0
        
        for idx, comp in enumerate(competencies):
            if comp["id"] == "politeness_refined_language_inquiry":
                # Targeted semantic scoring for politeness, refined language, and open-ended inquiry follow-through
                polite_hits = re.findall(r'\b(thank you|thanks|appreciate|pleasure|good morning|dr\.? vance|glad to|honored|grateful|certainly|absolutely)\b', all_user_text, re.IGNORECASE)
                refined_hits = re.findall(r'\b(specifically|furthermore|consequently|fundamentally|systemically|architecturally|trade-off|tradeoff|substantiate|mitigate|leverage|holistic|scalable|paradigm|empirically|granular)\b', all_user_text, re.IGNORECASE)
                inquiry_hits = re.findall(r'(\?|\b(?:could|can|would)\s+you\s+(?:share|elaborate|clarify|tell me)|\b(?:curious|wondering|interested)\s+(?:about|how|what)|\bwhat is your\b|\bfrom your perspective\b)', all_user_text, re.IGNORECASE)
                ft_hits = re.findall(r'\b(as mentioned earlier|building on that|as i noted|previously mentioned|going back to|connecting to)\b', all_user_text, re.IGNORECASE)

                p_score = 7.0
                if len(polite_hits) >= 1: p_score += 0.6
                if len(polite_hits) >= 2: p_score += 0.4
                if len(refined_hits) >= 2: p_score += 0.6
                if len(refined_hits) >= 4: p_score += 0.4
                if len(inquiry_hits) >= 1: p_score += 0.6
                if len(inquiry_hits) >= 2: p_score += 0.4
                if len(ft_hits) >= 1: p_score += 0.4
                if is_ambiguous: p_score = min(p_score, 8.0)
                c_score = max(4.5, min(9.8, round(p_score, 1)))

                evidence_text = (
                    f"Candidate demonstrated courteous conversational conduct ({len(polite_hits)} courtesy markers), "
                    f"refined professional vocabulary ({len(refined_hits)} key terms), {len(inquiry_hits)} open-ended inquiries/questions to evaluator, "
                    f"and consistent follow-through across dialogue."
                )
            else:
                var = (idx * 0.3) - 0.3
                c_score = max(4.5, min(9.7, round(avg_turn_score + var, 1)))
                evidence_text = None

            if c_score >= 8.8:
                label = "Strong Mastery (Exceeds Bar)"
                anchor = comp["high_anchor"]
            elif c_score >= 7.3:
                label = "Solid Proficiency (Meets Bar)"
                anchor = comp["mid_anchor"]
            elif c_score >= 6.0:
                label = "Developing (Minor Gaps)"
                anchor = comp["mid_anchor"]
            else:
                label = "Below Bar (Significant Gaps)"
                anchor = comp["low_anchor"]

            if evidence_text is None:
                evidence_text = f"Candidate demonstrated {label.lower()} across interview exchanges with {len(metric_signals)} metric references observed."

            # If interview is ambiguous and this competency corresponds to unreached turns
            is_comp_ambiguous = is_ambiguous and (idx >= num_turns)
            if is_comp_ambiguous:
                if comp["id"] == "politeness_refined_language_inquiry":
                    evidence_text += " (⚠️ Provisional assessment due to early interview termination)."
                else:
                    evidence_text = "⚠️ Ambiguous Signal: Interview terminated early before this specific competency could be fully probed by the evaluator. Rating is provisional."

            overall_weighted += c_score * comp["weight"]
            
            comp_matrix.append({
                "id": comp["id"],
                "name": comp["name"],
                "score": c_score,
                "weight": comp["weight"],
                "rating_label": label,
                "focus": comp["focus"],
                "definition": comp.get("definition", comp["focus"]),
                "behavioral_anchor": anchor,
                "high_anchor": comp["high_anchor"],
                "mid_anchor": comp["mid_anchor"],
                "low_anchor": comp["low_anchor"],
                "evidence": evidence_text,
                "is_ambiguous": is_comp_ambiguous
            })

        overall_score = round(overall_weighted, 1)

        # Recommendation calibration
        hire_bar = 7.5 if not is_probing else 8.0
        strong_bar = 8.8 if not is_probing else 9.0
        
        if is_ambiguous and num_turns <= 2:
            recommendation = "Incomplete / Ambiguous Signal (Follow-Up Required)"
            rec_summary = (
                f"[AMBIGUITY NOTICE] {candidate_name} concluded the interview session prematurely after only {num_turns} question-and-answer exchange{'s' if num_turns != 1 else ''} "
                f"({total_words} words). While initial composure was demonstrated, insufficient dialogue exists to verify core competencies for {job_role} at {target_company or 'the target company'}. "
                f"A follow-up probe session is required to resolve critical ambiguities."
            )
        elif overall_score >= strong_bar:
            recommendation = "Strong Hire"
            rec_summary = f"{candidate_name} decisively clears the hiring bar for {job_role} at {target_company or 'target company'}. Demonstrates exceptional domain command, rigorous trade-off articulation, and strong ownership."
        elif overall_score >= hire_bar:
            recommendation = "Hire"
            rec_summary = f"{candidate_name} meets the core competencies required for {job_role}. Demonstrated clear problem-solving and structured communication with minor growth areas in edge-case depth."
        elif overall_score >= 6.4:
            recommendation = "Lean Hire"
            rec_summary = f"{candidate_name} exhibits promising foundational capabilities for {job_role}, but requires targeted leveling or mentorship on complex operational trade-offs and metrics."
        elif overall_score >= 5.0:
            recommendation = "Lean No Hire"
            rec_summary = f"{candidate_name} showed effort but leaves notable gaps against {experience_level} expectations, particularly in quantified results and comprehensive error resilience."
        else:
            recommendation = "Strong No Hire"
            rec_summary = f"{candidate_name} does not meet the baseline competency threshold for {job_role} at this time. Significant developmental coaching required."

        # Job Description & Resume Alignment Audit
        jd_alignment = []
        # Extract potential requirements from JD
        jd_lines = [line.strip("-•* \t") for line in (job_description or "").split("\n") if len(line.strip()) > 15]
        if not jd_lines:
            jd_lines = [
                f"Core competency in {job_role} methodology and modern toolchains",
                f"Experience architecting high-reliability systems and optimizing performance",
                f"Cross-functional collaboration, ownership, and stakeholder communication"
            ]
        
        for req in jd_lines[:3]:
            # Check overlap between requirement words and user answers
            req_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', req.lower()))
            overlap = req_words.intersection(set(re.findall(r'\b[a-zA-Z]{4,}\b', all_user_text.lower())))
            if len(overlap) >= 3:
                status = "Fully Demonstrated"
                analysis = f"Direct alignment verified. Candidate addressed key concepts ({', '.join(list(overlap)[:3])}) across spoken responses."
            elif len(overlap) >= 1:
                status = "Partially Demonstrated"
                analysis = f"Emerging signal detected for {list(overlap)[0]}, but lacks deep quantitative or architectural elaboration."
            else:
                status = "Not Assessed / Missing"
                analysis = "Candidate did not explicitly mention or substantiate this core requirement during the dialogue."

            jd_alignment.append({
                "requirement": req[:100],
                "status": status,
                "evidence_quote": f"Spoken terms identified: {', '.join(list(overlap)[:4])}" if overlap else "No direct evidence provided in transcript.",
                "alignment_analysis": analysis
            })

        # Key strengths and growth areas
        key_strengths = [
            f"Strong alignment with {job_role} core trajectory and authentic self-presentation.",
            f"Demonstrated technical fluency in primary problem decomposition ({len(turns)} multi-turn exchanges completed).",
            f"Maintained conversational composure and adapted to interviewer prompts throughout the session."
        ]
        if metric_signals:
            key_strengths.insert(1, f"Effectively incorporated quantitative metrics into project framing ({', '.join(metric_signals[:3])}).")
            key_strengths = key_strengths[:3]

        growth_areas = [
            f"Elevate answers from team-level narratives ('we') to distinct personal architectural decisions ('I architected / I drove').",
            f"Proactively articulate failure modes, rollbacks, and edge-case handling before being prompted.",
            f"Anchor every STAR result in business impact metrics (e.g. latency reduction %, revenue, or adoption rates)."
        ]

        actionable_plan = [
            f"Practice the 'Metric-First STAR' technique: state the measurable business outcome in the first 20 seconds of your answer.",
            f"Conduct mock whiteboarding drills specifically focused on CAP theorem trade-offs and disaster recovery.",
            f"Calibrate technical depth to target company ({target_company or 'FAANG'}) engineering rubrics using explicit architectural trade-off comparisons."
        ]

        return {
            "overall_score": overall_score,
            "hiring_recommendation": recommendation,
            "recommendation_summary": rec_summary,
            "assessed_level": f"{experience_level} • Evaluated for {target_company or 'Enterprise / FAANG'}",
            "confidence_rating": confidence_rating,
            "interviewer_rigor_notes": f"Evaluated under '{interviewer_tone or 'Professional & Rigorous'}' rubric bar with {interview_duration or 'Standard'} pacing.",
            "competency_matrix": comp_matrix,
            "turn_evaluations": turn_evaluations,
            "job_description_alignment": jd_alignment,
            "key_strengths": key_strengths,
            "priority_growth_areas": growth_areas,
            "actionable_recommendations": actionable_plan,
            "evaluator_engine": "deterministic_bars_rubric",
            "ambiguity_detected": is_ambiguous,
            "ambiguity_notice": ambiguity_notice
        }

    async def evaluate_official_simulation(
        self,
        conversation_history: List[Dict[str, str]],
        candidate_name: str = "Candidate",
        job_role: str = "Software Engineer",
        target_company: str = "",
        experience_level: str = "Mid-Level",
        interview_type: str = "Comprehensive (STAR Behavioral + Technical)",
        interview_duration: str = "Standard Round (6-7 Questions • ~45 mins)",
        interviewer_tone: str = "Professional & Rigorous (Standard FAANG/Corporate)",
        cv_text: str = "",
        job_description: str = ""
    ) -> Dict[str, Any]:
        """
        Executes comprehensive, track-specific, question-by-question hiring committee evaluation
        of a completed multi-turn interview simulation using NVIDIA Nemotron 3.5 Super VL with fallback.
        """
        turns = self._extract_turn_pairs(conversation_history)
        if not turns:
            turns = [{
                "turn_index": 1,
                "question": f"Official mock interview opening for {job_role}",
                "answer": "Candidate completed interview session."
            }]

        base_eval = self._evaluate_simulation_deterministic(
            turns=turns,
            candidate_name=candidate_name,
            job_role=job_role,
            target_company=target_company,
            experience_level=experience_level,
            interview_type=interview_type,
            interview_duration=interview_duration,
            interviewer_tone=interviewer_tone,
            cv_text=cv_text,
            job_description=job_description
        )

        openrouter_key = self.get_openrouter_api_key()
        gemini_key = self.get_gemini_api_key()
        is_openrouter_dummy = not openrouter_key or "testkey" in openrouter_key.lower()
        has_gemini = bool(gemini_key and not gemini_key.startswith("test_mock") and len(gemini_key) > 10)

        if not openrouter_key and not has_gemini:
            return base_eval

        # Build prompt for AI Committee Evaluation
        competencies = self.get_track_competencies(interview_type)
        comp_descriptions = "\n".join([f"- {c['name']} (Weight: {int(c['weight']*100)}%): {c['focus']} High Bar: {c['high_anchor']}" for c in competencies])

        transcript_str = ""
        for t in turns:
            transcript_str += f"\n--- TURN {t['turn_index']} ---\n"
            transcript_str += f"INTERVIEWER (DR. VANCE): {t['question']}\n"
            transcript_str += f"CANDIDATE ({candidate_name}): {t['answer']}\n"

        system_prompt = f"""You are the Lead Hiring Committee Evaluator for an elite tech hiring loop (FAANG / Fortune 500 bar).
Your goal is to conduct an authoritative, rigorous, evidence-based post-interview evaluation for {candidate_name} applying for {job_role}.

NON-NEGOTIABLE GROUND TRUTH CANDIDATE PROFILE:
- Candidate Name: {candidate_name}
- Target Role: {job_role}
- Target Company: {target_company or 'Tier-1 Tech Company'}
- Seniority Level: {experience_level}
- Interview Track / Focus Area: {interview_type}
- Interview Duration: {interview_duration}
- Interviewer Persona & Rigor: {interviewer_tone}

JOB DESCRIPTION CONTEXT:
\"\"\"{job_description[:600] if job_description else 'Standard requirements for ' + job_role}\"\"\"

CANDIDATE CV / RESUME CONTEXT:
\"\"\"{cv_text[:600] if cv_text else 'Demonstrated industry background'}\"\"\"

TRACK-SPECIFIC EVALUATION RUBRICS & COMPETENCIES:
{comp_descriptions}

EVALUATION RULES:
1. CITATION OF EVIDENCE: You MUST quote specific phrases and technical terms spoken by the candidate in each turn. Do not give vague impressions.
2. TRACK-SPECIFIC: Evaluate strictly against the 4 competencies listed above for '{interview_type}'.
3. RIGOR CALIBRATION: Calibrate scores against '{interviewer_tone}' and '{experience_level}'. A Senior/Staff candidate must show quantified metrics and systemic trade-offs.
4. RECOMMENDATION: Choose from: 'Strong Hire' (8.8-10.0), 'Hire' (7.5-8.7), 'Lean Hire' (6.4-7.4), 'Lean No Hire' (5.0-6.3), 'Strong No Hire' (<5.0).
5. FORMAT: Return ONLY a valid JSON object matching the requested schema. No markdown formatting outside JSON.
"""

        user_prompt = f"""Please evaluate the following complete multi-turn interview transcript:
{transcript_str}

Return a valid JSON object with EXACTLY this structure:
{{
  "overall_score": 8.6,
  "hiring_recommendation": "Strong Hire",
  "recommendation_summary": "Comprehensive 2-3 sentence hiring committee consensus rationale.",
  "assessed_level": "{experience_level} • Assessed for {target_company or 'Tier-1 Tech'}",
  "confidence_rating": "High Confidence (Detailed signal across {len(turns)} turns)",
  "interviewer_rigor_notes": "Calibrated against {interviewer_tone}.",
  "competency_matrix": [
    {{
      "name": "Competency Name",
      "score": 8.5,
      "rating_label": "Exceeds Bar",
      "behavioral_anchor": "Observed behavioral pattern",
      "evidence": "Direct quote and observation from answers"
    }}
  ],
  "turn_evaluations": [
    {{
      "turn_index": 1,
      "stage_name": "Stage 1: ...",
      "interviewer_question": "...",
      "candidate_response": "...",
      "turn_score": 8.5,
      "competency_tested": "...",
      "strengths_observed": ["...", "..."],
      "gaps_identified": ["...", "..."],
      "coached_exemplar": "..."
    }}
  ],
  "job_description_alignment": [
    {{
      "requirement": "Key requirement from JD",
      "status": "Fully Demonstrated",
      "evidence_quote": "Exact candidate quote",
      "alignment_analysis": "Analysis of alignment"
    }}
  ],
  "key_strengths": ["...", "...", "..."],
  "priority_growth_areas": ["...", "...", "..."],
  "actionable_recommendations": ["...", "...", "..."]
}}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Tier 1 AI: Try OpenRouter (NVIDIA Nemotron 3.5 Super VL)
        if openrouter_key and not is_openrouter_dummy:
            try:
                content = await self.call_openrouter(messages, temperature=0.3, max_tokens=3200)
                if content:
                    parsed = self._clean_json_output(content)
                    if isinstance(parsed, dict) and "overall_score" in parsed and "competency_matrix" in parsed:
                        parsed["evaluator_engine"] = "openrouter_nemotron"
                        parsed["ambiguity_detected"] = base_eval.get("ambiguity_detected", False)
                        parsed["ambiguity_notice"] = base_eval.get("ambiguity_notice")
                        if base_eval.get("ambiguity_detected"):
                            parsed["confidence_rating"] = base_eval["confidence_rating"]
                            if len(turns) <= 2:
                                parsed["hiring_recommendation"] = base_eval["hiring_recommendation"]
                                parsed["recommendation_summary"] = base_eval["recommendation_summary"]

                        # Validate and enrich turn_evaluations
                        if "turn_evaluations" not in parsed or not parsed["turn_evaluations"]:
                            parsed["turn_evaluations"] = base_eval["turn_evaluations"]
                        if "job_description_alignment" not in parsed or not parsed["job_description_alignment"]:
                            parsed["job_description_alignment"] = base_eval["job_description_alignment"]

                        # Enrich competency_matrix with definitions and rubric anchors
                        comp_by_id = {c["id"]: c for c in competencies}
                        comp_by_name = {c["name"].lower(): c for c in competencies}
                        
                        enriched_matrix = []
                        existing_ids = set()
                        for item in parsed.get("competency_matrix", []):
                            c_id = item.get("id") or ""
                            c_name = item.get("name") or ""
                            match = comp_by_id.get(c_id) or comp_by_name.get(c_name.lower())
                            if match:
                                existing_ids.add(match["id"])
                                item["id"] = match["id"]
                                item["definition"] = match.get("definition", match["focus"])
                                item["high_anchor"] = match.get("high_anchor", "")
                                item["mid_anchor"] = match.get("mid_anchor", "")
                                item["low_anchor"] = match.get("low_anchor", "")
                                item["focus"] = match.get("focus", "")
                                if "weight" not in item or not item["weight"]:
                                    item["weight"] = match.get("weight", 0.2)
                            enriched_matrix.append(item)
                        
                        for base_c in base_eval.get("competency_matrix", []):
                            if base_c.get("id") not in existing_ids and not any(base_c.get("name", "").lower() in item.get("name", "").lower() for item in enriched_matrix):
                                enriched_matrix.append(base_c)
                        
                        parsed["competency_matrix"] = enriched_matrix
                        return parsed
            except Exception as e:
                logger.warning(f"Nemotron simulation evaluation failed, attempting secondary provider: {e}")

        # Tier 2 AI: Try Google Gemini (gemini-3.5-flash)
        if has_gemini:
            try:
                print(f"[Gemini Simulation Evaluation] Engaging Google Gemini for official hiring committee evaluation...", flush=True)
                gem_content = await self.call_gemini(messages, temperature=0.25, max_tokens=3200, response_json=True)
                if gem_content:
                    parsed = self._clean_json_output(gem_content)
                    if isinstance(parsed, dict) and "overall_score" in parsed and "competency_matrix" in parsed:
                        parsed["evaluator_engine"] = "gemini_3.5_flash"
                        parsed["ambiguity_detected"] = base_eval.get("ambiguity_detected", False)
                        parsed["ambiguity_notice"] = base_eval.get("ambiguity_notice")
                        if base_eval.get("ambiguity_detected"):
                            parsed["confidence_rating"] = base_eval["confidence_rating"]
                            if len(turns) <= 2:
                                parsed["hiring_recommendation"] = base_eval["hiring_recommendation"]
                                parsed["recommendation_summary"] = base_eval["recommendation_summary"]

                        if "turn_evaluations" not in parsed or not parsed["turn_evaluations"]:
                            parsed["turn_evaluations"] = base_eval["turn_evaluations"]
                        if "job_description_alignment" not in parsed or not parsed["job_description_alignment"]:
                            parsed["job_description_alignment"] = base_eval["job_description_alignment"]

                        comp_by_id = {c["id"]: c for c in competencies}
                        comp_by_name = {c["name"].lower(): c for c in competencies}
                        
                        enriched_matrix = []
                        existing_ids = set()
                        for item in parsed.get("competency_matrix", []):
                            c_id = item.get("id") or ""
                            c_name = item.get("name") or ""
                            match = comp_by_id.get(c_id) or comp_by_name.get(c_name.lower())
                            if match:
                                existing_ids.add(match["id"])
                                item["id"] = match["id"]
                                item["definition"] = match.get("definition", match["focus"])
                                item["high_anchor"] = match.get("high_anchor", "")
                                item["mid_anchor"] = match.get("mid_anchor", "")
                                item["low_anchor"] = match.get("low_anchor", "")
                                item["focus"] = match.get("focus", "")
                                if "weight" not in item or not item["weight"]:
                                    item["weight"] = match.get("weight", 0.2)
                            enriched_matrix.append(item)
                        
                        for base_c in base_eval.get("competency_matrix", []):
                            if base_c.get("id") not in existing_ids and not any(base_c.get("name", "").lower() in item.get("name", "").lower() for item in enriched_matrix):
                                enriched_matrix.append(base_c)
                        
                        parsed["competency_matrix"] = enriched_matrix
                        print(f"[Gemini Simulation Evaluation] [SUCCESS] Completed committee scorecard via Gemini!", flush=True)
                        return parsed
            except Exception as e:
                logger.warning(f"Gemini simulation evaluation failed, retaining deterministic base: {e}")

        return base_eval


evaluator = InterviewEvaluator()
