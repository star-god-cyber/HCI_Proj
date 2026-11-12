import unittest
import asyncio
import uuid
from app.evaluator import InterviewEvaluator
from app.models import EvaluationResult, SessionSetupRequest, AnswerSubmitRequest
from app.database import init_db, save_session, save_attempt, get_session
import main


class TestPrototypeAFixes(unittest.TestCase):
    def setUp(self):
        init_db()
        self.evaluator = InterviewEvaluator()

    def test_why_feedback_criteria_breakdown(self):
        """Verify that evaluate_answer produces a complete criteria_breakdown for all 4 rubric dimensions."""
        q_text = "Tell me about a time when you had to resolve a technical disagreement with a teammate."
        ans_text = (
            "During our sprint, we disagreed on whether to use Redis or Memcached for our caching tier. "
            "I set up a benchmark test comparing throughput and eviction behavior under 10k RPS. "
            "As a result, we selected Redis, improved cache hit rates by 34%, and launched on schedule."
        )
        res = self.evaluator.evaluate_answer(q_text, ans_text, job_role="Software Engineer", attempt_number=1)
        self.assertIsInstance(res, EvaluationResult)
        
        breakdown = res.why_feedback_summary.get("criteria_breakdown")
        self.assertIsNotNone(breakdown, "criteria_breakdown must exist in why_feedback_summary")
        
        required_keys = ["evidence_outcome", "relevance", "specificity", "structure_clarity"]
        for key in required_keys:
            self.assertIn(key, breakdown, f"Missing {key} in criteria_breakdown")
            crit = breakdown[key]
            self.assertIn("name", crit)
            self.assertIn("score", crit)
            self.assertIn("standard", crit)
            self.assertIn("reason", crit)
            self.assertIn("excerpt", crit)
            self.assertIn("recommendation", crit)
            self.assertIsInstance(crit["score"], (int, float))

    def test_compare_uses_actual_evaluations(self):
        """Verify that compare_attempts in evaluator.py computes delta accurately."""
        q_text = "Tell me about a conflict."
        ans1 = "We disagreed on the architecture so we talked and chose one."
        ans2 = (
            "We disagreed on whether to use Raft or 2PC for the payment ledger. "
            "I ran a chaos partition benchmark. We rolled out Raft quorum leases, "
            "reducing P99 commit latency from 450ms to 42ms with zero customer downtime."
        )
        eval1 = self.evaluator.evaluate_answer(q_text, ans1, "Software Engineer", 1)
        eval2 = self.evaluator.evaluate_answer(q_text, ans2, "Software Engineer", 2)
        
        comp = self.evaluator.compare_attempts(1, q_text, ans1, ans2, eval1, eval2)
        self.assertIsNotNone(comp)
        self.assertGreater(comp.attempt2_scores["evidence"], comp.attempt1_scores["evidence"])
        self.assertGreater(comp.deltas["evidence_outcome"], 0)
        self.assertTrue(len(comp.improvements) > 0)

    def test_session_persistence_and_retrieval(self):
        """Verify get_session recovers the session, attempt evaluations, and reflections."""
        session_id = f"test_proto_a_sess_{uuid.uuid4().hex[:8]}"
        session_data = {
            "id": session_id,
            "prototype_type": "A",
            "candidate_name": "Aarav Mehta",
            "job_role": "Staff Distributed Systems Engineer",
            "target_company": "Stripe",
            "experience_level": "Senior",
            "interview_type": "Technical & System Architecture (Deep Dive)",
            "interview_duration": "Focused Screening (4-5 Questions • ~25 mins)",
            "difficulty": "Neutral Corporate (Standard Hiring Bar / Objective)",
            "persona_id": "aarav",
            "current_question_index": 0,
            "questions": [{"id": 1, "text": "Question 1"}, {"id": 2, "text": "Question 2"}],
            "turn_index": 1,
            "overall_score": 8.0,
            "status": "in_progress"
        }
        save_session(session_data)

        # Save an attempt
        eval_dict = {
            "overall_score": 7.5,
            "relevance": {"name": "Relevance", "score": 8.0, "status": "Good", "reason": "Good", "rubric_definition": "Def"},
            "specificity": {"name": "Specificity", "score": 7.0, "status": "Good", "reason": "Good", "rubric_definition": "Def"},
            "evidence_outcome": {"name": "Evidence & Outcome", "score": 7.5, "status": "Good", "reason": "Good", "rubric_definition": "Def"},
            "structure_clarity": {"name": "Structure & Clarity", "score": 7.5, "status": "Good", "reason": "Good", "rubric_definition": "Def"},
            "strengths": ["Clear technical depth"],
            "needs_improvement": ["Could add SLA impact"],
            "actionable_suggestions": ["Include metrics"],
            "why_feedback_summary": {}
        }
        save_attempt(session_id, 1, 1, "Question 1", "Sample answer with benchmarks", eval_dict)

        retrieved = get_session(session_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["job_role"], "Staff Distributed Systems Engineer")
        self.assertEqual(len(retrieved["attempts"]), 1)
        self.assertIn("evaluation", retrieved["attempts"][0])
        self.assertEqual(retrieved["attempts"][0]["evaluation"]["overall_score"], 7.5)


if __name__ == "__main__":
    unittest.main()



if __name__ == "__main__":
    unittest.main()
