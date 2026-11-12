import unittest
import asyncio
from app.evaluator import InterviewEvaluator, GEMINI_MODELS
from app.data_manager import get_question_bank_for_role
from starlette.testclient import TestClient
from main import app


class TestGeminiAndAIConfiguration(unittest.TestCase):
    def setUp(self):
        self.evaluator = InterviewEvaluator()
        self.client = TestClient(app)

    def test_gemini_models_configured(self):
        self.assertIsInstance(GEMINI_MODELS, list)
        self.assertIn("gemini-1.5-flash", GEMINI_MODELS)

    def test_fallback_custom_questions_when_key_empty(self):
        # Empty API keys should seamlessly return curated profile-grounded questions
        self.evaluator.get_gemini_api_key = lambda: ""
        questions = asyncio.run(self.evaluator.generate_custom_interview_questions(
            candidate_name="Test Candidate",
            job_role="Software Engineer",
            target_company="Google",
            count=3
        ))
        self.assertIsInstance(questions, list)
        self.assertGreaterEqual(len(questions), 3)
        self.assertEqual(questions[0]["id"], 1)
        self.assertIn("text", questions[0])
        self.assertIn("competency", questions[0])

    def test_fallback_adaptive_followup_when_key_empty(self):
        self.evaluator.get_gemini_api_key = lambda: ""
        res = asyncio.run(self.evaluator.generate_adaptive_followup_ai(
            previous_question="Tell me about a time you had a conflict with an engineering teammate.",
            user_answer="I discussed the issue with them and we came to an agreement.",
            job_role="Associate Product Manager",
            candidate_name="Rahul"
        ))
        self.assertIn("followup_question", res)
        self.assertIn("reasoning", res)
        self.assertIn(res.get("source"), ["deterministic_engine", "gemini_1.5_flash", "adaptive_ai_dialogue_engine"])

    def test_fallback_evaluate_answer_when_key_empty(self):
        self.evaluator.get_gemini_api_key = lambda: ""
        eval_res = asyncio.run(self.evaluator.evaluate_answer_ai(
            question_text="Tell me about a time you resolved a disagreement.",
            answer_text="At my previous job, I organized a sprint review with the lead engineer to align on product priorities.",
            job_role="Product Manager",
            attempt_number=1,
            candidate_name="Rohan Kulkarni"
        ))
        self.assertIsNotNone(eval_res)
        self.assertGreater(eval_res.overall_score, 0)
        self.assertIsNotNone(eval_res.relevance)
        self.assertIsNotNone(eval_res.specificity)
        self.assertIsNotNone(eval_res.adaptive_followup)
        self.assertIn("followup_question", eval_res.adaptive_followup)

    def test_api_config_gemini_primary_endpoint(self):
        # Test GET /api/config
        get_res = self.client.get("/api/config")
        self.assertEqual(get_res.status_code, 200)
        data = get_res.json()
        self.assertIn("gemini_active", data)
        self.assertIn("gemini_model", data)
        self.assertNotIn("openrouter_model", data)
        self.assertNotIn("openrouter_active", data)

        # Test ConfigUpdateRequest accepts gemini_api_key
        from app.models import ConfigUpdateRequest
        req = ConfigUpdateRequest(gemini_api_key="AIzaSyTestMockKey")
        self.assertEqual(req.gemini_api_key, "AIzaSyTestMockKey")

    def test_dotenv_file_exists_and_loads(self):
        from app.env_loader import DOTENV_PATH
        self.assertTrue(DOTENV_PATH.exists())
        content = DOTENV_PATH.read_text(encoding="utf-8")
        self.assertIn("GEMINI_API_KEY", content)
        self.assertNotIn("OPENROUTER_API_KEY", content)

    def test_gemini_diagnostic_endpoint(self):
        res = self.client.get("/api/gemini/test")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue("api_key_masked" in data or "status" in data)


if __name__ == "__main__":
    unittest.main()
