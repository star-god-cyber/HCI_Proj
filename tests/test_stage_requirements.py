import unittest
import asyncio
from app.evaluator import InterviewEvaluator


class TestStageMinimumRequirements(unittest.TestCase):
    def setUp(self):
        self.evaluator = InterviewEvaluator()

    def test_short_answer_fails_substance_check(self):
        is_met, reason, probe = self.evaluator.check_stage_minimum_requirements(
            stage_index=1,
            user_answer="Yes I am ready.",
            job_role="Software Engineer"
        )
        self.assertFalse(is_met)
        self.assertIn("too brief", reason.lower())
        self.assertIn("elaborate", probe.lower())

    def test_stage_1_background_missing_context(self):
        # 10 words but no background / role context
        is_met, reason, probe = self.evaluator.check_stage_minimum_requirements(
            stage_index=1,
            user_answer="I am really happy to be here today for this interview call.",
            job_role="Software Engineer"
        )
        self.assertFalse(is_met)
        self.assertIn("background", probe.lower())

    def test_stage_1_background_sufficient_context(self):
        is_met, reason, probe = self.evaluator.check_stage_minimum_requirements(
            stage_index=1,
            user_answer="I have 4 years of experience as a full stack software engineer building cloud services.",
            job_role="Software Engineer"
        )
        self.assertTrue(is_met)
        self.assertEqual(probe, "")

    def test_stage_2_technical_missing_tools_or_system(self):
        is_met, reason, probe = self.evaluator.check_stage_minimum_requirements(
            stage_index=2,
            user_answer="In my previous work I helped the company do their tasks properly and quickly.",
            job_role="Software Engineer"
        )
        self.assertFalse(is_met)
        self.assertIn("technical", probe.lower())

    def test_stage_2_technical_sufficient_system(self):
        is_met, reason, probe = self.evaluator.check_stage_minimum_requirements(
            stage_index=2,
            user_answer="I architected a distributed microservices backend using Python, FastAPI, and Docker to process real-time data.",
            job_role="Software Engineer"
        )
        self.assertTrue(is_met)

    def test_stage_3_behavioral_tradeoff_missing(self):
        is_met, reason, probe = self.evaluator.check_stage_minimum_requirements(
            stage_index=3,
            user_answer="Our team got along very well and everyone agreed with all plans every week.",
            job_role="Software Engineer"
        )
        self.assertFalse(is_met)
        self.assertIn("trade-off", probe.lower())

    def test_stage_3_behavioral_tradeoff_sufficient(self):
        is_met, reason, probe = self.evaluator.check_stage_minimum_requirements(
            stage_index=3,
            user_answer="The tech lead wanted to ship features immediately, but I advocated for prioritizing database migration to avoid latency trade-offs, and we reached consensus.",
            job_role="Software Engineer"
        )
        self.assertTrue(is_met)

    def test_stage_4_resilience_missing(self):
        is_met, reason, probe = self.evaluator.check_stage_minimum_requirements(
            stage_index=4,
            user_answer="Everything ran normally without any problems during the entire deployment cycle.",
            job_role="Software Engineer"
        )
        self.assertFalse(is_met)
        self.assertIn("failure mode", probe.lower())

    def test_stage_4_resilience_sufficient(self):
        is_met, reason, probe = self.evaluator.check_stage_minimum_requirements(
            stage_index=4,
            user_answer="When traffic spiked during product launches, we implemented circuit breakers and Redis fallback caching to safeguard against database crashes.",
            job_role="Software Engineer"
        )
        self.assertTrue(is_met)

    def test_stage_5_impact_missing(self):
        is_met, reason, probe = self.evaluator.check_stage_minimum_requirements(
            stage_index=5,
            user_answer="The business stakeholders seemed satisfied with what we built.",
            job_role="Software Engineer"
        )
        self.assertFalse(is_met)
        self.assertIn("measure", probe.lower())

    def test_stage_5_impact_sufficient(self):
        is_met, reason, probe = self.evaluator.check_stage_minimum_requirements(
            stage_index=5,
            user_answer="We reduced API response latency by 42% and improved daily active user conversion by 18 percent.",
            job_role="Software Engineer"
        )
        self.assertTrue(is_met)

    def test_interview_turn_stays_on_same_stage_when_insufficient(self):
        # When user gives an insufficient 3-word answer on turn 1
        res = asyncio.run(self.evaluator.conduct_official_interview_turn(
            conversation_history=[],
            user_message="Yes sounds fine.",
            candidate_name="Priya",
            turn_index=1
        ))
        self.assertTrue(res["is_clarification"])
        self.assertFalse(res["stage_requirement_met"])
        self.assertEqual(res["turn_index"], 1, "Must remain on Stage 1 to resolve minimum context requirements.")

    def test_interview_turn_advances_stage_when_requirements_met(self):
        # When user provides substantive context on turn 1
        res = asyncio.run(self.evaluator.conduct_official_interview_turn(
            conversation_history=[],
            user_message="I have 5 years of software engineering experience focusing on building high-throughput Python backends and distributed architectures.",
            candidate_name="Priya",
            turn_index=1
        ))
        self.assertFalse(res["is_clarification"])
        self.assertTrue(res["stage_requirement_met"])
        self.assertEqual(res["turn_index"], 2, "Must advance to Stage 2 once Stage 1 requirements are satisfied.")


if __name__ == "__main__":
    unittest.main()
