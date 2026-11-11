import unittest
import asyncio
from app.evaluator import InterviewEvaluator

class TestPromptAndConflictRules(unittest.TestCase):
    def setUp(self):
        self.evaluator = InterviewEvaluator()

    def test_opening_question_always_greets_and_asks_intro_first(self):
        """Verify opening questions across all tracks always start with greeting and ask for intro/background first."""
        tracks = [
            ("Technical Architecture", "Staff Distributed Systems Engineer", "Google"),
            ("UX Design Research", "Lead UX Researcher", "Figma"),
            ("Product Execution", "Principal Product Manager", "Stripe"),
            ("General Behavioral", "Operations Lead", "McKinsey")
        ]
        
        for interview_type, role, company in tracks:
            q = self.evaluator.generate_opening_question(
                candidate_name="Aarav Sharma",
                job_role=role,
                target_company=company,
                interview_type=interview_type,
                cv_text="Led distributed database replication and built Raft consensus algorithms handling 100k QPS."
            )
            # 1. Greeting
            self.assertTrue(
                q.startswith("Good morning, Aarav Sharma!"),
                f"Failed greeting check for {role}: {q}"
            )
            # 2. Introduction of Dr. Vance
            self.assertIn("Dr. Marcus Vance", q)
            # 3. Asks for intro and background first
            self.assertIn("introduce yourself", q.lower())
            self.assertIn("background", q.lower())

    def test_system_prompt_contains_conflict_rules_and_intro_acknowledgment(self):
        """Verify system prompt includes mandatory discrepancy cross-examination rules."""
        prompt = self.evaluator.build_official_interview_system_prompt(
            candidate_name="Priya Patel",
            job_role="Senior Frontend Architect",
            target_company="Vercel",
            cv_text="5+ years building Next.js and React web applications.",
            turn_index=1
        )
        self.assertIn("MANDATORY CV & JOB ROLE DISCREPANCY CROSS-EXAMINATION", prompt)
        self.assertIn("Seniority or Scope Inflation", prompt)
        self.assertIn("Domain or Role Mismatch", prompt)
        self.assertIn("ACKNOWLEDGE THE INTRODUCTION & BACKGROUND FIRST", prompt)
        self.assertIn("START WITH QUESTIONS", prompt)

    def test_turn1_acknowledges_intro_before_questions(self):
        """Verify Turn 1 response explicitly acknowledges the introduction/background first, then asks questions."""
        resp = self.evaluator._synthesize_semantic_interview_turn(
            conversation_history=[],
            user_message="Hi Dr. Vance, I'm Aarav. Over the last 4 years at CloudScale, I've worked primarily with Kafka, Go, and Redis building high-throughput microservices.",
            candidate_name="Aarav",
            job_role="Senior Backend Engineer",
            target_company="Stripe",
            experience_level="Senior",
            interview_type="System Architecture",
            interview_duration="Standard",
            interviewer_tone="Neutral Corporate",
            turn_index=1,
            max_turns=7
        )
        msg = resp["interviewer_message"]
        # Must acknowledge intro/background
        self.assertTrue(
            "introducing yourself" in msg.lower() or "background" in msg.lower(),
            f"Expected acknowledgment of introduction in Turn 1: {msg}"
        )
        # Must start with questions
        self.assertTrue(
            "start our" in msg.lower() or "questions:" in msg.lower(),
            f"Expected question transition in Turn 1: {msg}"
        )

    def test_detect_seniority_inflation_discrepancy(self):
        """Verify candidate claiming principal/chief architect when CV/level is junior triggers cross-examination."""
        discrepancy = self.evaluator._detect_cv_role_discrepancy(
            user_message="In my last role, I was the sole principal architect and single-handedly built the entire corporate distributed cloud architecture.",
            cv_text="Software Engineering Intern (Summer 2023). Contributed to bug fixes in Python.",
            job_role="Junior Software Engineer",
            experience_level="Junior (0-1 years)",
            candidate_name="Rohan"
        )
        self.assertIsNotNone(discrepancy)
        self.assertEqual(discrepancy["discrepancy_type"], "seniority_inflation")
        self.assertIn("reconcile", discrepancy["probe"].lower())
        self.assertIn("cv", discrepancy["probe"].lower())

    def test_detect_domain_mismatch_discrepancy(self):
        """Verify UX Researcher candidate claiming CUDA kernel programming triggers cross-examination."""
        discrepancy = self.evaluator._detect_cv_role_discrepancy(
            user_message="I spent most of my time writing custom CUDA kernels and optimizing low-level memory management in C++ for GPU acceleration.",
            cv_text="User Experience Researcher with expertise in usability testing, interviews, and Figma.",
            job_role="Senior UX Researcher",
            experience_level="Senior",
            candidate_name="Ananya"
        )
        self.assertIsNotNone(discrepancy)
        self.assertEqual(discrepancy["discrepancy_type"], "domain_mismatch")
        self.assertIn("target role is Senior UX Researcher", discrepancy["probe"])
        self.assertIn("cuda", discrepancy["probe"].lower())

    def test_detect_cv_skill_denial_discrepancy(self):
        """Verify candidate denying experience with a core skill explicitly listed on their CV."""
        discrepancy = self.evaluator._detect_cv_role_discrepancy(
            user_message="To be honest, I have never used Kubernetes and don't know anything about container orchestration.",
            cv_text="Technical Skills: Docker, Kubernetes, Terraform, AWS, Go. Deployed 20+ production Kubernetes clusters.",
            job_role="DevOps Engineer",
            experience_level="Mid-Level",
            candidate_name="Vikram"
        )
        self.assertIsNotNone(discrepancy)
        self.assertEqual(discrepancy["discrepancy_type"], "cv_skill_denial")
        self.assertIn("kubernetes", discrepancy["probe"].lower())
        self.assertIn("clarify that discrepancy", discrepancy["probe"].lower())

    def test_semantic_turn_raises_conflict_probe_on_discrepancy(self):
        """Verify _synthesize_semantic_interview_turn immediately returns a discrepancy probe when a conflict exists."""
        turn_resp = self.evaluator._synthesize_semantic_interview_turn(
            conversation_history=[],
            user_message="I acted as the chief technology officer and directed the entire company-wide overhaul alone.",
            candidate_name="Dev",
            job_role="Software Engineering Intern",
            target_company="Amazon",
            experience_level="Intern",
            interview_type="General Mock",
            interview_duration="Standard",
            interviewer_tone="Neutral Corporate",
            turn_index=2,
            max_turns=6,
            cv_text="Summer Research Intern (3 months). Studied algorithmic complexity."
        )
        self.assertTrue(turn_resp.get("discrepancy_detected"))
        self.assertEqual(turn_resp.get("discrepancy_type"), "seniority_inflation")
        self.assertIn("reconcile", turn_resp["interviewer_message"].lower())

if __name__ == "__main__":
    unittest.main()
