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
from typing import Dict, Any, List, Optional
import httpx
from app.models import EvaluationResult, RubricCriterion, AttemptComparison
from app.data_manager import get_question_bank_for_role
from app.env_loader import get_env_variable

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "nvidia/nemotron-3.5-super-vl:free"


class InterviewEvaluator:
    def __init__(self):
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.openrouter_model = os.environ.get("OPENROUTER_MODEL", OPENROUTER_MODEL)
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
        key = self.openrouter_api_key or get_env_variable("OPENROUTER_API_KEY", "")
        clean_key = key.strip().strip('"').strip("'")
        if clean_key:
            if clean_key.startswith("v1-"):
                clean_key = f"sk-or-{clean_key}"
            elif not clean_key.startswith("sk-"):
                clean_key = f"sk-or-v1-{clean_key}"
        return clean_key

    def get_gemini_api_key(self) -> str:
        key = self.gemini_api_key or get_env_variable("GEMINI_API_KEY", "")
        return key.strip().strip('"').strip("'")

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
            "recommended_addition": "A single sentence quantifying impact (e.g., 'As a result, we finished the sprint 2 days early with 100% test coverage')."
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

    async def generate_adaptive_followup_gemini(
        self,
        previous_question: str,
        user_answer: str,
        job_role: str,
        api_key: Optional[str] = None
    ) -> Dict[str, str]:
        key = api_key or self.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        if not key:
            res = self.generate_adaptive_followup(previous_question, user_answer, job_role)
            res["source"] = "deterministic_engine"
            return res

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
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{GEMINI_API_URL}?key={key}",
                    json={
                        "contents": [
                            {"parts": [{"text": prompt}]}
                        ],
                        "generationConfig": {
                            "temperature": 0.7,
                            "maxOutputTokens": 300,
                            "responseMimeType": "application/json"
                        }
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        parsed = json.loads(text_part)
                        if "followup_question" in parsed:
                            parsed["source"] = "gemini_1.5_flash"
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
        api_key: Optional[str] = None
    ) -> EvaluationResult:
        base_eval = self.evaluate_answer(question_text, answer_text, job_role, attempt_number)
        key = api_key or self.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        if not key or len(answer_text.strip().split()) < 15:
            return base_eval

        prompt = f"""You are an expert interview coach evaluating a candidate for the role: "{job_role}".
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
4. An improved model response demonstrating how to include measurable outcomes.

Respond ONLY with a JSON object in this format:
{{
  "strengths": ["...", "..."],
  "needs_improvement": ["...", "..."],
  "actionable_suggestions": ["..."],
  "example_improved_answer": "..."
}}
"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{GEMINI_API_URL}?key={key}",
                    json={
                        "contents": [
                            {"parts": [{"text": prompt}]}
                        ],
                        "generationConfig": {
                            "temperature": 0.6,
                            "maxOutputTokens": 600,
                            "responseMimeType": "application/json"
                        }
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text_part = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        parsed = json.loads(text_part)
                        if "strengths" in parsed and parsed["strengths"]:
                            base_eval.strengths = parsed["strengths"]
                        if "needs_improvement" in parsed and parsed["needs_improvement"]:
                            base_eval.needs_improvement = parsed["needs_improvement"]
                        if "actionable_suggestions" in parsed and parsed["actionable_suggestions"]:
                            base_eval.actionable_suggestions = parsed["actionable_suggestions"]
                        if "example_improved_answer" in parsed and parsed["example_improved_answer"]:
                            base_eval.example_improved_answer = parsed["example_improved_answer"]
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
        Zero cost free tier reasoning model.
        """
        api_key = self.get_openrouter_api_key()
        if not api_key:
            return None

        model_name = (self.openrouter_model or OPENROUTER_MODEL).strip()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://127.0.0.1:8000",
            "Referer": "http://127.0.0.1:8000",
            "X-Title": "CS 435 AI Interview Practice",
            "Content-Type": "application/json"
        }
        # Nemotron 3.5 requires sufficient token budget for reasoning + output
        token_budget = max(max_tokens, 2800)
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": token_budget
        }

        try:
            # 60 second timeout with 15s connect for reasoning model completion
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                resp = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        msg = choices[0].get("message", {})
                        content = msg.get("content")
                        if content and content.strip():
                            return content.strip()
                        # Fallback if reasoning model placed answer in reasoning
                        reasoning = msg.get("reasoning", "")
                        if reasoning and ("[" in reasoning or "{" in reasoning):
                            return reasoning.strip()
                else:
                    logger.warning(f"OpenRouter HTTP {resp.status_code}: {resp.text[:300]}")
        except Exception as e:
            logger.warning(f"OpenRouter API call exception: {e}")

        return None

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
        fallback_questions = get_question_bank_for_role(job_role)

        if not api_key:
            logger.info("OpenRouter API key not configured; using curated fallback question bank.")
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

        logger.info("Retaining curated question bank fallback.")
        return fallback_questions

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

        # Fallback to deterministic
        res = self.generate_adaptive_followup(previous_question, user_answer, job_role)
        res["source"] = "deterministic_engine"
        return res

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
            stage_instruction = f"""CURRENT MANDATORY STAGE TARGET: STAGE 2 (Technical Project Deep Dive)
- The candidate has ALREADY completed their self-introduction in Turn 1!
- CRITICAL NEGATIVE CONSTRAINT: Under NO circumstances should you ask {candidate_name} to introduce themselves, walk through their background, or state what brings them to the role. That stage is completely finished!
- YOUR MANDATORY GOAL FOR THIS TURN:
  1. Actively listen and mirror back 1 to 2 specific technologies, frameworks, company names, or accomplishments {candidate_name} just mentioned in their introduction.
  2. Ask ONE focused, technical deep-dive question about a major project, system architecture, or core engineering challenge they highlighted."""
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

        api_key = self.get_openrouter_api_key()
        if api_key:
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

            # Add existing conversation turns from the history buffer
            for msg in conversation_history:
                r = msg.get("role", "user")
                c = msg.get("content", "").strip()
                if c:
                    messages.append({"role": r, "content": c})

            # Append latest user prompt only if not already at the end of the history buffer
            clean_user_msg = user_message.strip()
            if not messages or messages[-1].get("content") != clean_user_msg:
                messages.append({"role": "user", "content": clean_user_msg})

            # Tier 1: Try OpenRouter (NVIDIA Nemotron 3.5 Super VL)
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

        # Tier 2: Try Google Gemini 1.5 Flash
        gemini_key = self.get_gemini_api_key()
        if gemini_key and not gemini_key.startswith("test_mock") and len(gemini_key) > 10:
            try:
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
                    c = msg.get("content", "").strip()
                    if c:
                        messages.append({"role": msg.get("role", "user"), "content": c})
                if not messages or messages[-1].get("content") != user_message.strip():
                    messages.append({"role": "user", "content": user_message.strip()})

                gemini_content = await self.call_gemini_turn(messages, temperature=0.65)
                if gemini_content and len(gemini_content.strip()) > 15:
                    clean_reply = self._clean_llm_reply(gemini_content)
                    return {
                        "interviewer_message": clean_reply,
                        "followup_question": clean_reply,
                        "reasoning": f"Stage {turn_index + 1} official Gemini 1.5 Flash live probe.",
                        "turn_index": turn_index + 1,
                        "is_concluded": (turn_index >= max_turns or "conclude" in clean_reply.lower() or "evaluation" in clean_reply.lower()),
                        "source": "gemini_1.5_flash"
                    }
            except Exception as e:
                logger.warning(f"Gemini official turn failed, engaging semantic dialogue engine: {e}")

        # Tier 3: Adaptive Semantic Dialogue Engine (High-Fidelity Context-Aware NLP)
        return self._synthesize_semantic_interview_turn(
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
            max_turns=max_turns
        )

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
        """Executes a multi-turn conversation turn using Google Gemini 1.5 Flash."""
        key = self.get_gemini_api_key()
        if not key or key.startswith("test_mock") or len(key) < 10:
            return None

        contents = []
        for msg in messages:
            role = "user" if msg.get("role") in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{GEMINI_API_URL}?key={key}",
                    json={
                        "contents": contents,
                        "generationConfig": {
                            "temperature": temperature,
                            "maxOutputTokens": 600
                        }
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text and len(text.strip()) > 15:
                            return text.strip()
                else:
                    logger.warning(f"Gemini turn HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Gemini turn call failed: {e}")
        return None

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
        max_turns: int
    ) -> Dict[str, Any]:
        """
        Generates deeply context-aware, adaptive official interview turns that interpret,
        quote, and probe candidate responses using semantic NLP.
        """
        semantics = self._extract_candidate_semantics(user_message, conversation_history)
        techs = semantics["tech"]
        metrics = semantics["metrics"]
        actions = semantics["actions"]
        prior_techs = semantics["prior_tech"]

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
        metric_cite = f", particularly achieving {metrics[0]}" if metrics else ""

        # Construct Stage-by-Stage tailored responses
        if turn_index == 1:
            reaction = (
                f"Thank you for that thorough introduction, {candidate_name}. "
                f"Your background with {primary_topic}{metric_cite} directly aligns with what we look for in our {job_role} team{company_ref}."
            )
            probe = (
                f"Diving into your direct work on {primary_topic}: could you walk me through the most technically complex project or architecture you spearheaded there, "
                f"and what specific engineering hurdle or bottleneck you had to overcome?"
            )
        elif turn_index == 2:
            reaction = (
                f"I appreciate that deep-dive into {primary_topic}, {candidate_name}. "
                f"Building systems under those operational constraints{metric_cite} inevitably surfaces competing technical priorities and team friction."
            )
            probe = (
                f"Tell me about a specific time during that project where you encountered a significant disagreement or differing viewpoint with a teammate, tech lead, or product partner over technical priorities or architecture trade-offs. "
                f"What was the core debate, and how did you resolve it?"
            )
        elif turn_index == 3 and turn_index < max_turns:
            reaction = (
                f"Navigating technical deadlocks around {primary_topic} with objective data is essential in high-impact engineering teams, {candidate_name}."
            )
            probe = (
                f"Looking back on that solution: when requirements, scale surges, or system dependencies unexpectedly spiked, how did you handle bottlenecks, failure modes, or architectural trade-offs to ensure resilience?"
            )
        elif turn_index == 4 and turn_index < max_turns:
            reaction = (
                f"That demonstrates strong systems thinking and operational resilience regarding {primary_topic}, {candidate_name}."
            )
            probe = (
                f"Beyond the engineering delivery, how did you verify the measurable outcome and business impact? "
                f"What concrete quantitative metrics, KPIs, or user feedback validated that this implementation succeeded?"
            )
        elif turn_index == 5 and turn_index < max_turns:
            reaction = (
                f"Those are compelling insights and quantified outcomes for {primary_topic}{metric_cite}, {candidate_name}."
            )
            probe = (
                f"If you had to reflect on that entire lifecycle from inception to deployment, what was your single biggest retrospective takeaway or architectural choice you would redesign with hindsight?"
            )
        elif turn_index == 6 and turn_index < max_turns:
            reaction = (
                f"That self-awareness and iterative engineering mindset are critical for senior leadership, {candidate_name}."
            )
            probe = (
                f"Moving into cross-functional execution: how do you typically bridge the gap between engineering complexities and non-technical stakeholders or product managers when roadmap deadlines are under pressure?"
            )
        elif turn_index >= 7 and turn_index < max_turns:
            reaction = (
                f"Managing stakeholder expectations while upholding quality across {primary_topic} is a vital leadership balance, {candidate_name}."
            )
            probe = (
                f"Can you describe how you mentor peers, elevate team engineering standards, or drive technical strategy across broader initiatives?"
            )
        else:
            reaction = (
                f"Those are thorough insights and impressive results across {primary_topic}, {candidate_name}."
            )
            probe = (
                f"Thank you for walking through your experience with me today—it gave me a great window into how you lead and solve complex challenges. "
                f"That brings our interview questions to a close, and I'll now finalize your comprehensive rubric scorecard."
            )

        full_reply = f"{reaction} {probe}"
        return {
            "interviewer_message": full_reply,
            "followup_question": full_reply,
            "reasoning": f"Adaptive Semantic NLP probe interpreting: {primary_topic}{metric_cite}.",
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
            return base_eval

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
                        return base_eval
            except Exception as e:
                logger.warning(f"OpenRouter answer evaluation failed, falling back: {e}")

        # Fallback to Gemini if configured
        gemini_key = self.get_gemini_api_key()
        if gemini_key:
            return await self.evaluate_answer_gemini(question_text, answer_text, job_role, attempt_number, api_key=gemini_key)

        return base_eval

    def get_track_competencies(self, interview_type: str = "") -> List[Dict[str, str]]:
        """
        Returns the 4 industry-standard competencies and behavioral rubrics for the given interview track.
        """
        t = (interview_type or "").lower()
        if "behavioral" in t or "star" in t or "leadership" in t:
            return [
                {
                    "id": "star_rigor",
                    "name": "STAR Framework Rigor & Specificity",
                    "weight": 0.30,
                    "focus": "Demarcation of Situation, Task, Action, and quantifiable Business Result.",
                    "high_anchor": "Structures answer seamlessly with exact context, personal ownership of actions, and measurable metrics.",
                    "mid_anchor": "Provides solid narrative but glosses over metrics or uses collective 'we' instead of personal action.",
                    "low_anchor": "Vague situational sketch without concrete actions or clear end results."
                },
                {
                    "id": "ownership_agency",
                    "name": "Ownership, Initiative & Bias for Action",
                    "weight": 0.25,
                    "focus": "Personal agency, taking responsibility for outcomes, and navigating ambiguity.",
                    "high_anchor": "Demonstrates relentless ownership; unblocks teammates, challenges status quo, and embraces accountability.",
                    "mid_anchor": "Executes assigned responsibilities well, but hesitates to take unprompted initiative during ambiguity.",
                    "low_anchor": "Passes blame to external factors, stakeholders, or constraints; passive execution."
                },
                {
                    "id": "conflict_collaboration",
                    "name": "Stakeholder Alignment & Conflict Resolution",
                    "weight": 0.25,
                    "focus": "Active listening, empathy, resolving technical or interpersonal tension constructively.",
                    "high_anchor": "Employs data-backed de-escalation, seeks common ground, and rallies cross-functional stakeholders.",
                    "mid_anchor": "Manages interpersonal friction politely but tends to avoid difficult confrontations or rely on escalation.",
                    "low_anchor": "Shows defensiveness, rigid mindset, or dismissiveness toward dissenting perspectives."
                },
                {
                    "id": "growth_humility",
                    "name": "Learning Agility & Post-Mortem Reflection",
                    "weight": 0.20,
                    "focus": "Dissecting failures objectively, extracting systemic lessons, and coaching others.",
                    "high_anchor": "Openly shares impactful missteps, highlights root causes, and implements lasting systemic guardrails.",
                    "mid_anchor": "Acknowledges errors with guidance, but focuses on tactical rather than systemic preventative measures.",
                    "low_anchor": "Reluctant to admit shortcomings or claims zero regrets/mistakes in past roles."
                }
            ]
        elif "technical" in t or "architecture" in t or "system design" in t:
            return [
                {
                    "id": "arch_soundness",
                    "name": "Architecture Soundness & Trade-off Analysis",
                    "weight": 0.30,
                    "focus": "Component decoupling, data store selection, and justifying CAP theorem trade-offs.",
                    "high_anchor": "Articulates crisp architectural diagrams, explicitly evaluating throughput vs latency and consistency trade-offs.",
                    "mid_anchor": "Proposes viable standard architecture but struggles to justify specific database or protocol choices under scrutiny.",
                    "low_anchor": "Monolithic or brittle architecture; misses major bottlenecks or suggests anti-patterns."
                },
                {
                    "id": "scalability_concurrency",
                    "name": "Scalability, Concurrency & Bottleneck Handling",
                    "weight": 0.25,
                    "focus": "Horizontal scaling, sharding, caching tiers, and back-pressure mitigation.",
                    "high_anchor": "Proactively addresses hot spots, cache invalidation, asynchronous queuing, and partition keys.",
                    "mid_anchor": "Applies standard caching (Redis) and load balancers, but overlooks database replication lag or write limits.",
                    "low_anchor": "Fails to scale past single-node limits; unable to identify single points of failure."
                },
                {
                    "id": "fault_tolerance",
                    "name": "Failure Modes, Edge Cases & Fault Tolerance",
                    "weight": 0.25,
                    "focus": "Graceful degradation, idempotency, circuit breakers, and retry storm resilience.",
                    "high_anchor": "Anticipates network partitions, dead-letter queues, exactly-once vs at-least-once delivery, and recovery.",
                    "mid_anchor": "Acknowledges failure possibilities, but relies on naive retries without jitter or exponential backoff.",
                    "low_anchor": "Assumes 'happy path'; systems crash completely during downstream dependencies downtime."
                },
                {
                    "id": "production_depth",
                    "name": "Production Readiness & Operational Observability",
                    "weight": 0.20,
                    "focus": "Distributed tracing, SLO/SLA budgeting, zero-downtime deployments, and security.",
                    "high_anchor": "Integrates comprehensive OpenTelemetry metrics, canary releases, rollback criteria, and data encryption.",
                    "mid_anchor": "Mentions logs and basic CI/CD, but lacks depth on alerting thresholds, runbooks, or zero-downtime migrations.",
                    "low_anchor": "Treats deployment and monitoring as an afterthought; neglects security and operational health."
                }
            ]
        elif "product" in t or "analytical" in t or "strategy" in t:
            return [
                {
                    "id": "problem_framing",
                    "name": "Problem Framing & User Empathy",
                    "weight": 0.30,
                    "focus": "Deconstructing ambiguous market problems and pinpointing true user pain points.",
                    "high_anchor": "Structures ambiguity with a disciplined user-first lens; identifies unarticulated user friction and opportunity size.",
                    "mid_anchor": "Understands the core user, but jumps too quickly to feature solutions without validating problem root causes.",
                    "low_anchor": "Builds features looking for a problem; lacks customer empathy and segment definition."
                },
                {
                    "id": "metrics_rigor",
                    "name": "Metric Definition & Analytical Rigor",
                    "weight": 0.25,
                    "focus": "North Star metric, input/guardrail metrics, and hypothesis-driven experimentation.",
                    "high_anchor": "Designs nuanced metric trees with pairing guardrails (e.g., engagement vs churn) and statistical experiment rigor.",
                    "mid_anchor": "Proposes valid primary metrics (e.g., CTR or DAU), but misses cannibalization risks or counter-metrics.",
                    "low_anchor": "Relies on vanity metrics without clear causal links to business or user value."
                },
                {
                    "id": "strategic_tradeoffs",
                    "name": "Strategic Prioritization & Trade-off Calculus",
                    "weight": 0.25,
                    "focus": "RICE/MoSCoW frameworks, effort vs impact, defensibility, and competitive moat.",
                    "high_anchor": "Ruthlessly prioritizes high-leverage bets; articulates what NOT to build and defends rationale with conviction.",
                    "mid_anchor": "Prioritizes logically, but struggles when forced to cut favored features under severe engineering constraints.",
                    "low_anchor": "Attempts to do everything simultaneously; lacks strategic focus and clear priority criteria."
                },
                {
                    "id": "gtm_velocity",
                    "name": "Go-to-Market & Execution Roadmapping",
                    "weight": 0.20,
                    "focus": "Phased rollouts, cross-functional choreography, feedback loops, and scaling velocity.",
                    "high_anchor": "Outlines detailed alpha/beta cohorts, sales/marketing enablement, and rapid feedback iteration cycles.",
                    "mid_anchor": "Creates a functional launch schedule, but overlooks edge-case user support or internal enablement bottlenecks.",
                    "low_anchor": "Treats shipping code as launch completion; neglects user adoption and iterative loops."
                }
            ]
        else:
            # Comprehensive Mixed Mock
            return [
                {
                    "id": "role_depth",
                    "name": "Role-Specific Technical Proficiency",
                    "weight": 0.30,
                    "focus": "Depth of specialized domain knowledge, practical craftsmanship, and technical fluency.",
                    "high_anchor": "Speaks with seasoned authority; articulates complex concepts with clarity and precision.",
                    "mid_anchor": "Solid grasp of foundational concepts, but requires probing to reach deep architectural or domain nuances.",
                    "low_anchor": "Superficial knowledge; relies on buzzwords without understanding underlying mechanics."
                },
                {
                    "id": "behavioral_ownership",
                    "name": "STAR Behavioral Execution & Ownership",
                    "weight": 0.25,
                    "focus": "Structured storytelling, personal accountability for results, and measurable business outcomes.",
                    "high_anchor": "Delivers crisp STAR responses with distinct personal actions and verified quantitative impact.",
                    "mid_anchor": "Good stories with clear lessons, but uses generalized language rather than concrete personal actions.",
                    "low_anchor": "Meandering answers that fail to explain the actual challenge or candidate's personal contribution."
                },
                {
                    "id": "systemic_problem_solving",
                    "name": "Systemic Problem Solving & Trade-offs",
                    "weight": 0.25,
                    "focus": "Decomposing complex ambiguity, evaluating multiple options, and managing trade-offs.",
                    "high_anchor": "Systematically breaks down problems, lists assumptions, and weighs pros/cons before choosing a path.",
                    "mid_anchor": "Finds a reasonable solution, but anchors on the first idea without exploring alternative designs.",
                    "low_anchor": "Impulsive decision making; unable to explain why one approach was chosen over another."
                },
                {
                    "id": "executive_communication",
                    "name": "Executive Communication & Strategic Alignment",
                    "weight": 0.20,
                    "focus": "Concise delivery, active listening, and alignment with target company mission and level bar.",
                    "high_anchor": "High signal-to-noise ratio; commands executive presence, listens actively, and adapts to interviewer cues.",
                    "mid_anchor": "Communicates effectively, but occasionally over-explains minor points or requires minor refocusing.",
                    "low_anchor": "Rambling, evasive, or unfocused; ignores interviewer prompts and questions."
                }
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

        # Calculate competency matrix scores
        avg_turn_score = sum(turn_scores) / len(turn_scores) if turn_scores else 7.5
        comp_matrix = []
        overall_weighted = 0.0
        
        for idx, comp in enumerate(competencies):
            # Modulate each competency score slightly around average turn score
            var = (idx * 0.3) - 0.3
            c_score = max(4.5, min(9.7, round(avg_turn_score + var, 1)))
            
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

            overall_weighted += c_score * comp["weight"]
            
            comp_matrix.append({
                "id": comp["id"],
                "name": comp["name"],
                "score": c_score,
                "weight": comp["weight"],
                "rating_label": label,
                "focus": comp["focus"],
                "behavioral_anchor": anchor,
                "evidence": f"Candidate demonstrated {label.lower()} across interview exchanges with {len(metric_signals)} metric references observed."
            })

        overall_score = round(overall_weighted, 1)

        # Recommendation calibration
        hire_bar = 7.5 if not is_probing else 8.0
        strong_bar = 8.8 if not is_probing else 9.0
        
        if overall_score >= strong_bar:
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
            "confidence_rating": f"High Confidence ({len(turns)} Verified Dialogue Turns • {total_words} Spoken Words)",
            "interviewer_rigor_notes": f"Evaluated under '{interviewer_tone or 'Professional & Rigorous'}' rubric bar with {interview_duration or 'Standard'} pacing.",
            "competency_matrix": comp_matrix,
            "turn_evaluations": turn_evaluations,
            "job_description_alignment": jd_alignment,
            "key_strengths": key_strengths,
            "priority_growth_areas": growth_areas,
            "actionable_recommendations": actionable_plan,
            "evaluator_engine": "deterministic_bars_rubric"
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

        api_key = self.get_openrouter_api_key()
        if not api_key:
            return base_eval

        # Build prompt for Nemotron 3.5 Super VL
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

        try:
            content = await self.call_openrouter(messages, temperature=0.3, max_tokens=3200)
            if content:
                parsed = self._clean_json_output(content)
                if isinstance(parsed, dict) and "overall_score" in parsed and "competency_matrix" in parsed:
                    parsed["evaluator_engine"] = "openrouter_nemotron"
                    # Validate turn_evaluations format
                    if "turn_evaluations" not in parsed or not parsed["turn_evaluations"]:
                        parsed["turn_evaluations"] = base_eval["turn_evaluations"]
                    if "competency_matrix" not in parsed or not parsed["competency_matrix"]:
                        parsed["competency_matrix"] = base_eval["competency_matrix"]
                    if "job_description_alignment" not in parsed or not parsed["job_description_alignment"]:
                        parsed["job_description_alignment"] = base_eval["job_description_alignment"]
                    return parsed
        except Exception as e:
            logger.warning(f"Nemotron simulation evaluation failed, using deterministic fallback: {e}")

        return base_eval


evaluator = InterviewEvaluator()
