import unittest
from app.evaluator import InterviewEvaluator

class TestMetricsAndAmbiguity(unittest.TestCase):
    def setUp(self):
        self.evaluator = InterviewEvaluator()

    def test_all_tracks_have_five_competencies_summing_to_one(self):
        """Verify every track returns 5 competencies with weights summing to 1.00."""
        tracks = [
            "Behavioral & STAR Leadership",
            "Technical & System Architecture",
            "Product Strategy & Execution",
            "Full Mixed Comprehensive Mock"
        ]
        for t in tracks:
            comps = self.evaluator.get_track_competencies(t)
            self.assertEqual(len(comps), 5, f"Expected 5 competencies for track '{t}', got {len(comps)}")
            total_weight = sum(c["weight"] for c in comps)
            self.assertAlmostEqual(total_weight, 1.00, places=2, msg=f"Weights in track '{t}' must sum to 1.0")

    def test_every_competency_has_detailed_definition_and_anchors(self):
        """Verify each metric has a comprehensive definition, focus, and 3-tier behavioral anchors."""
        tracks = ["STAR Behavioral", "System Architecture", "Product Strategy", "General"]
        for t in tracks:
            for c in self.evaluator.get_track_competencies(t):
                self.assertTrue(bool(c.get("definition")), f"Missing definition for {c['name']} in {t}")
                self.assertTrue(len(c["definition"]) > 30, f"Definition too short for {c['name']}")
                self.assertTrue(bool(c.get("high_anchor")), f"Missing high_anchor for {c['name']}")
                self.assertTrue(bool(c.get("mid_anchor")), f"Missing mid_anchor for {c['name']}")
                self.assertTrue(bool(c.get("low_anchor")), f"Missing low_anchor for {c['name']}")

    def test_politeness_metric_present_across_all_tracks(self):
        """Verify the combined politeness, refined language, and inquiry follow-through metric is present in every track."""
        for t in ["Behavioral", "Technical", "Product", "Mixed"]:
            comps = self.evaluator.get_track_competencies(t)
            matching = [c for c in comps if c["id"] == "politeness_refined_language_inquiry"]
            self.assertEqual(len(matching), 1, f"Expected politeness metric in track {t}")
            metric = matching[0]
            self.assertIn("Politeness", metric["name"])
            self.assertIn("Refined Language", metric["name"])
            self.assertIn("Inquiry Follow-Through", metric["name"])
            self.assertEqual(metric["weight"], 0.15)

    def test_early_termination_detects_ambiguity(self):
        """Verify that an interview terminated after 1 or 2 turns triggers high ambiguity notices."""
        turns = [
            {
                "turn_index": 1,
                "question": "Good morning Aarav, could you introduce yourself?",
                "answer": "Good morning Dr. Vance! I am a distributed systems engineer with Go and Kafka experience."
            }
        ]
        result = self.evaluator._evaluate_simulation_deterministic(
            turns=turns,
            candidate_name="Aarav",
            job_role="Staff Systems Engineer",
            target_company="Stripe",
            experience_level="Staff",
            interview_type="System Architecture",
            interview_duration="Standard Round",
            interviewer_tone="Neutral Corporate",
            cv_text="Go, Kafka, Redis",
            job_description="Distributed consensus and low latency"
        )
        self.assertTrue(result["ambiguity_detected"], "Should detect ambiguity for 1-turn interview")
        self.assertIsNotNone(result["ambiguity_notice"])
        notice = result["ambiguity_notice"]
        self.assertTrue(notice["is_ambiguous"])
        self.assertEqual(notice["turn_count"], 1)
        self.assertIn("Ambiguity", notice["headline"])
        self.assertTrue(len(notice["unassessed_dimensions"]) >= 3)
        self.assertIn("Low Confidence / High Ambiguity", result["confidence_rating"])
        self.assertIn("Incomplete / Ambiguous Signal", result["hiring_recommendation"])

    def test_full_interview_has_no_ambiguity(self):
        """Verify that a full 5-turn interview with substantive dialogue has high confidence and no ambiguity."""
        turns = [
            {"turn_index": 1, "question": "Introduce yourself.", "answer": "Good morning Dr. Vance. I have led scalable distributed systems at scale for 6 years, architecting high-throughput Go and Kafka streaming pipelines."},
            {"turn_index": 2, "question": "Walk me through the architecture.", "answer": "We partitioned our event stream into 32 Kafka topics with Raft-backed quorum consensus, ensuring exactly-once processing across our multi-region clusters."},
            {"turn_index": 3, "question": "How did you resolve trade-offs?", "answer": "When our team debated availability versus consistency, I championed strong consistency for ledger writes to avoid financial discrepancies. Could you share how your team balances write latency versus replication lag?"},
            {"turn_index": 4, "question": "Tell me about failure recovery.", "answer": "We deployed circuit breakers with exponential backoff and dead-letter queues, recovering gracefully within 350ms of network partitions without data corruption."},
            {"turn_index": 5, "question": "What were the measured outcomes?", "answer": "Our Prometheus metrics verified p99 latency dropped by 38ms, achieving 99.999% uptime across 12 clusters and handling over 40k queries per second."}
        ]
        result = self.evaluator._evaluate_simulation_deterministic(
            turns=turns,
            candidate_name="Aarav",
            job_role="Staff Systems Engineer",
            target_company="Stripe",
            experience_level="Staff",
            interview_type="System Architecture",
            interview_duration="Standard Round",
            interviewer_tone="Neutral Corporate",
            cv_text="Go, Kafka, Redis, Distributed consensus",
            job_description="Distributed consensus and low latency"
        )
        self.assertFalse(result["ambiguity_detected"], "Full interview should not be flagged as ambiguous")
        self.assertIsNone(result["ambiguity_notice"])
        self.assertIn("High Confidence", result["confidence_rating"])

    def test_politeness_scoring_and_open_ended_questions(self):
        """Verify that polite candidate who poses open-ended inquiries scores highly on the politeness & inquiry metric."""
        polite_turns = [
            {"turn_index": 1, "question": "Introduce yourself.", "answer": "Good morning Dr. Vance! Thank you very much for having me today. I am truly honored to speak with you about this opportunity."},
            {"turn_index": 2, "question": "Tell me about your project.", "answer": "Certainly. Furthermore, from an architectural standpoint, we systematically mitigated latency bottlenecks. Building on that, I am curious: what is your team's current approach to zero-downtime database sharding?"}
        ]
        result = self.evaluator._evaluate_simulation_deterministic(
            turns=polite_turns,
            candidate_name="Priya",
            job_role="Senior Engineer",
            target_company="Google",
            experience_level="Senior",
            interview_type="System Architecture",
            interview_duration="Standard Round",
            interviewer_tone="Neutral Corporate",
            cv_text="Go, Kubernetes",
            job_description="Backend architecture"
        )
        comp = next(c for c in result["competency_matrix"] if c["id"] == "politeness_refined_language_inquiry")
        self.assertGreaterEqual(comp["score"], 7.5)
        self.assertIn("courteous", comp["evidence"].lower())
        self.assertIn("inquiries", comp["evidence"].lower())

if __name__ == "__main__":
    unittest.main()
