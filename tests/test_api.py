"""
API Endpoint integration tests.
Tests complete interaction flow through FastAPI TestClient.
"""

import unittest
from starlette.testclient import TestClient
from main import app


class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Interview Practice System", response.text)

    def test_personas(self):
        resp_p = self.client.get("/api/personas")
        self.assertEqual(resp_p.status_code, 200)
        self.assertIn("aditi", resp_p.json())
        self.assertIn("rahul", resp_p.json())

    def test_prototype_a_flow(self):
        # 1. Setup
        setup_resp = self.client.post("/api/setup", json={
            "prototype_type": "A",
            "job_role": "UX Research Intern",
            "interview_type": "Behavioral",
            "difficulty": "Medium",
            "cv_text": "HCI student with user testing experience",
            "job_description": "UX Research Intern role",
            "persona_id": "aditi"
        })
        self.assertEqual(setup_resp.status_code, 200)
        sess_data = setup_resp.json()
        session_id = sess_data["session_id"]
        self.assertTrue(session_id.startswith("sess_"))

        # 2. Evaluate Attempt 1 (weak on outcome)
        eval_resp1 = self.client.post("/api/evaluate", json={
            "session_id": session_id,
            "question_id": 1,
            "question_text": "Tell me about a time when you worked with a difficult teammate.",
            "answer_text": "I had a conflict with my peer and we had a meeting and compromised.",
            "attempt_number": 1
        })
        self.assertEqual(eval_resp1.status_code, 200)
        eval1_json = eval_resp1.json()
        self.assertIn("evidence_outcome", eval1_json)

        # 3. Submit Reflection
        ref_resp = self.client.post("/api/reflect", json={
            "session_id": session_id,
            "question_id": 1,
            "what_would_you_change": "I would add the 28% completion metric and delivery timeline.",
            "what_did_you_learn": "Give evidence and outcomes, not just actions."
        })
        self.assertEqual(ref_resp.status_code, 200)

        # 4. Evaluate Attempt 2 (strong on outcome)
        eval_resp2 = self.client.post("/api/evaluate", json={
            "session_id": session_id,
            "question_id": 1,
            "question_text": "Tell me about a time when you worked with a difficult teammate.",
            "answer_text": "During our sprint, I resolved a teammate disagreement by showing recorded user testing clips. As a result, our team shipped 2 days early with a 28% higher task completion rate.",
            "attempt_number": 2
        })
        self.assertEqual(eval_resp2.status_code, 200)
        eval2_json = eval_resp2.json()
        self.assertGreater(eval2_json["overall_score"], eval1_json["overall_score"])

        # 5. Compare Attempts
        comp_resp = self.client.post(f"/api/compare?session_id={session_id}&question_id=1")
        self.assertEqual(comp_resp.status_code, 200)
        comp_json = comp_resp.json()
        self.assertGreater(comp_json["deltas"]["overall"], 0)

        # 6. Check Longitudinal Progress
        prog_resp = self.client.get("/api/progress?persona_id=aditi")
        self.assertEqual(prog_resp.status_code, 200)
        self.assertGreaterEqual(prog_resp.json()["total_attempts"], 2)

        # 7. Test Export DOCX and PPTX
        docx_resp = self.client.get(f"/api/export-docx/{session_id}")
        self.assertEqual(docx_resp.status_code, 200)

        pptx_resp = self.client.get(f"/api/export-pptx/{session_id}")
        self.assertEqual(pptx_resp.status_code, 200)

    def test_prototype_b_followup(self):
        followup_resp = self.client.post("/api/followup", json={
            "session_id": "test_b",
            "question_id": 1,
            "previous_question": "Tell me about a conflict",
            "user_answer": "I talked to the designer and we agreed on a plan.",
            "job_role": "Associate Product Manager"
        })
        self.assertEqual(followup_resp.status_code, 200)
        self.assertIn("followup_question", followup_resp.json())

    def test_prototype_b_official_multi_turn(self):
        # 1. Setup Prototype B session
        setup_resp = self.client.post("/api/setup", json={
            "prototype_type": "B",
            "candidate_name": "Elena Rostova",
            "job_role": "Staff Distributed Systems Engineer",
            "target_company": "Stripe",
            "experience_level": "Senior",
            "cv_text": "Led multi-region consensus protocol redesign and ledger latency optimization",
            "job_description": "Architect high-throughput payment ledgers with sub-50ms latency"
        })
        self.assertEqual(setup_resp.status_code, 200)
        sess_data = setup_resp.json()
        session_id = sess_data["session_id"]
        first_q = sess_data["first_question"]["text"]
        self.assertIn("Elena", first_q)
        self.assertIn("Good morning", first_q)

        # 2. Turn 1 (Self-introduction)
        turn1_resp = self.client.post("/api/interview/turn", json={
            "session_id": session_id,
            "user_message": "Good morning Dr. Vance! I'm Elena, a backend systems engineer specializing in distributed consensus and payment ledgers.",
            "turn_index": 1,
            "job_role": "Staff Distributed Systems Engineer"
        })
        self.assertEqual(turn1_resp.status_code, 200)
        turn1_data = turn1_resp.json()
        self.assertIn("interviewer_message", turn1_data)
        self.assertEqual(turn1_data["turn_index"], 2)
        # Verify no duplicate "Good morning" greeting on subsequent turn
        self.assertNotIn("Good morning", turn1_data["interviewer_message"])
        self.assertFalse(turn1_data["is_concluded"])

        # 3. Turn 2 (Project Deep Dive Response)
        turn2_resp = self.client.post("/api/interview/turn", json={
            "session_id": session_id,
            "user_message": "We experienced partition stalls on cross-region 2PC. I redesigned our lease manager using Raft quorum leases, cutting commit latency from 450ms to 42ms.",
            "turn_index": 2,
            "job_role": "Staff Distributed Systems Engineer"
        })
        self.assertEqual(turn2_resp.status_code, 200)
        turn2_data = turn2_resp.json()
        self.assertIn("interviewer_message", turn2_data)
        self.assertEqual(turn2_data["turn_index"], 3)
        self.assertNotIn("Good morning", turn2_data["interviewer_message"])

        # 4. User-communicated wrap-up ending
        wrap_resp = self.client.post("/api/interview/turn", json={
            "session_id": session_id,
            "user_message": "Thank you Dr. Vance, that covers everything from my side and I am ready to wrap up.",
            "turn_index": 3,
            "job_role": "Staff Distributed Systems Engineer"
        })
        self.assertEqual(wrap_resp.status_code, 200)
        wrap_data = wrap_resp.json()
        self.assertTrue(wrap_data["is_concluded"])
        self.assertIn("conclude", wrap_data["interviewer_message"].lower())

        # 5. Interviewer-initiated ending once needful info extracted (Turn 4+)
        turn4_resp = self.client.post("/api/interview/turn", json={
            "session_id": session_id,
            "user_message": "Our Prometheus and Datadog telemetry verified p99 latency dropped by 38ms, achieving 99.999% uptime across all multi-region clusters.",
            "turn_index": 4,
            "job_role": "Staff Distributed Systems Engineer"
        })
        self.assertEqual(turn4_resp.status_code, 200)
        turn4_data = turn4_resp.json()
        self.assertTrue(turn4_data["is_concluded"])
        self.assertTrue(
            "needful" in turn4_data["interviewer_message"].lower() or 
            "conclude" in turn4_data["interviewer_message"].lower() or
            "scorecard" in turn4_data["interviewer_message"].lower()
        )

    def test_config_endpoints(self):
        # GET config
        resp = self.client.get("/api/config")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("stt_engine", resp.json())
        self.assertEqual(resp.json()["stt_engine"], "web_speech_api")

        # POST config
        post_resp = self.client.post("/api/config", json={
            "gemini_api_key": "test_mock_key_123",
            "voice_speed": 1.1,
            "auto_speak": True
        })
        self.assertEqual(post_resp.status_code, 200)
        self.assertTrue(post_resp.json()["gemini_active"])
        # Reset back
        self.client.post("/api/config", json={"gemini_api_key": ""})

    def test_evaluation_study_endpoints(self):
        # Submit evaluation
        payload = {
            "participant_id": "P_TEST",
            "target_role": "UX Research",
            "prototype_tested": "Both",
            "task_completed": True,
            "task_time_seconds": 180,
            "sus_scores": [5, 1, 5, 1, 5, 1, 5, 1, 5, 1],
            "sus_total_score": 100.0,
            "feedback_realism": "Excellent speech and voice response.",
            "feedback_learning": "Rubric deltas were clear.",
            "ethical_consent_signed": True
        }
        post_resp = self.client.post("/api/evaluation-study", json=payload)
        self.assertEqual(post_resp.status_code, 200)
        self.assertEqual(post_resp.json()["participant_id"], "P_TEST")

        # Retrieve evaluations
        get_resp = self.client.get("/api/evaluation-study")
        self.assertEqual(get_resp.status_code, 200)
        evals = get_resp.json()
        self.assertTrue(any(e["participant_id"] == "P_TEST" for e in evals))

    def test_websocket_live_streaming_transcribe(self):
        # Verify real-time streaming WebSocket endpoint connects and handles frames concurrently during recording
        with self.client.websocket_connect("/api/ws/transcribe") as websocket:
            # Send small 16kHz mono 16-bit PCM silence frame (3200 bytes = 100ms)
            silence_frame = b"\x00" * 3200
            websocket.send_bytes(silence_frame)
            # Send finish action
            websocket.send_text('{"action": "finish"}')
            data = websocket.receive_json()
            self.assertIn("type", data)
            self.assertEqual(data["type"], "complete")
            self.assertIn("text", data)

    def test_prototype_b_hiring_committee_evaluation(self):
        # 1. Test Technical Track Evaluation
        tech_payload = {
            "session_id": "sess_test_tech",
            "candidate_name": "Elena Rostova",
            "job_role": "Staff Distributed Systems Engineer",
            "target_company": "Stripe",
            "experience_level": "Staff / Lead (8+ yrs)",
            "interview_type": "Technical & System Architecture Focus",
            "interview_duration": "Standard Interview (3-4 Questions • ~20 mins)",
            "interviewer_tone": "Challenging & Highly Probing (High Bar / Edge-case testing)",
            "cv_text": "Led multi-region consensus protocol redesign and ledger latency optimization",
            "job_description": "Architect high-throughput payment ledgers with sub-50ms latency across multi-region clusters",
            "conversation_history": [
                {"role": "assistant", "content": "Good morning Elena! Welcome. Could you introduce yourself and your background?"},
                {"role": "user", "content": "Good morning Dr. Vance! Over the past 8 years as a Staff Engineer at Stripe, I led our consensus protocol redesign, reducing multi-region commit latency by 35% across 14 zones."},
                {"role": "assistant", "content": "What trade-offs did you consider when handling partition tolerance?"},
                {"role": "user", "content": "We chose Raft with quorum leases over Paxos for operational debuggability. During cross-datacenter fiber cuts, we strictly favored consistency over availability to prevent duplicate payouts."}
            ]
        }
        res_tech = self.client.post("/api/simulation/evaluate", json=tech_payload)
        self.assertEqual(res_tech.status_code, 200)
        data_tech = res_tech.json()

        self.assertIn("overall_score", data_tech)
        self.assertIn("hiring_recommendation", data_tech)
        self.assertIn("competency_matrix", data_tech)
        self.assertEqual(len(data_tech["competency_matrix"]), 5)
        tech_comp_names = [c["name"] for c in data_tech["competency_matrix"]]
        self.assertTrue(any("Architecture Soundness" in name for name in tech_comp_names))
        self.assertTrue(any("Politeness" in name for name in tech_comp_names))
        self.assertTrue(data_tech.get("ambiguity_detected"))
        self.assertIn("ambiguity_notice", data_tech)

        self.assertIn("turn_evaluations", data_tech)
        self.assertEqual(len(data_tech["turn_evaluations"]), 2)
        self.assertIn("job_description_alignment", data_tech)
        self.assertIn("key_strengths", data_tech)
        self.assertIn("priority_growth_areas", data_tech)
        self.assertIn("actionable_recommendations", data_tech)

        # 2. Test STAR Behavioral Track Evaluation (Different criteria)
        beh_payload = {
            "session_id": "sess_test_beh",
            "candidate_name": "Aditi Sharma",
            "job_role": "UX Research Intern",
            "target_company": "Google",
            "experience_level": "Intern / Entry-Level",
            "interview_type": "STAR Behavioral Deep-Dive",
            "interview_duration": "Quick Screening (2-3 Questions • ~15 mins)",
            "interviewer_tone": "Supportive & Conversational (Encouraging / Guided probing)",
            "cv_text": "Led 14 cognitive usability field studies and improved navigation clarity",
            "job_description": "Conduct qualitative usability tests and cross-functional design sprints",
            "conversation_history": [
                {"role": "assistant", "content": "Good morning Aditi! Walk me through your design background."},
                {"role": "user", "content": "Good morning Dr. Vance! I conducted 14 cognitive field studies for accessible navigation, reducing task abandonment by 28%."}
            ]
        }
        res_beh = self.client.post("/api/simulation/evaluate", json=beh_payload)
        self.assertEqual(res_beh.status_code, 200)
        data_beh = res_beh.json()

        self.assertEqual(len(data_beh["competency_matrix"]), 5)
        beh_comp_names = [c["name"] for c in data_beh["competency_matrix"]]
        # Verify criteria are completely different from technical track
        self.assertTrue(any("STAR Framework Rigor" in name for name in beh_comp_names))
        self.assertTrue(any("Politeness" in name for name in beh_comp_names))
        self.assertFalse(any("Architecture Soundness" in name for name in beh_comp_names))
        self.assertTrue(data_beh.get("ambiguity_detected"))
        self.assertIn("ambiguity_notice", data_beh)

    def test_progress_reset(self):
        reset_resp = self.client.post("/api/progress/reset")
        self.assertEqual(reset_resp.status_code, 200)
        self.assertEqual(reset_resp.json()["status"], "success")

        # Verify empty trajectory
        prog_resp = self.client.get("/api/progress")
        self.assertEqual(prog_resp.status_code, 200)
        self.assertEqual(prog_resp.json()["total_attempts"], 0)
        self.assertEqual(len(prog_resp.json()["trajectory"]), 0)

        # Re-initialize DB seeds for other test cases
        from app.database import init_db
        init_db()

    def test_user_study_feedback_submission(self):
        feedback_payload = {
            "participant_name": "Test User P05",
            "prototype_evaluated": "Both Prototypes (Full Experience)",
            "candidate_role": "Staff Distributed Systems Engineer",
            "rating_overall": 9,
            "rating_voice": 10,
            "rating_ai_feedback": 9,
            "rating_learning_value": 9,
            "what_worked_well": "Real-time speech-to-text transcript was fast and accurate. Speed slider works great.",
            "suggestions_for_improvement": "Add more question domains."
        }
        res = self.client.post("/api/feedback", json=feedback_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("submission_count", data)

        # Verify retrieval via GET /api/feedback
        get_res = self.client.get("/api/feedback")
        self.assertEqual(get_res.status_code, 200)
        items = get_res.json()
        self.assertIsInstance(items, list)
        self.assertTrue(any(item.get("participant_name") == "Test User P05" for item in items))


if __name__ == "__main__":
    unittest.main()
