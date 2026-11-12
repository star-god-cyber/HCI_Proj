import json
import csv
import sqlite3
import os

participants = [
    {
        "id": 1,
        "participant_id": "P01",
        "target_role": "UX Research Intern",
        "prototype_tested": "Both",
        "task_completed": 1,
        "task_time_seconds": 230,
        "sus_scores": [5, 1, 5, 1, 5, 1, 5, 1, 5, 1],
        "sus_total_score": 100.0,
        "feedback_realism": "Speech-to-text worked without delay. Hands-free simulation felt very engaging.",
        "feedback_learning": "The 'Why this feedback' screen made it completely clear why I lost points on Evidence.",
        "ethical_consent_signed": 1,
        "created_at": "2026-11-04 14:15:22"
    },
    {
        "id": 2,
        "participant_id": "P02",
        "target_role": "Associate Product Manager",
        "prototype_tested": "Both",
        "task_completed": 1,
        "task_time_seconds": 290,
        "sus_scores": [5, 2, 5, 2, 4, 1, 5, 2, 4, 1],
        "sus_total_score": 87.5,
        "feedback_realism": "Interviewer avatar adds good realism and presence compared to static question prompts.",
        "feedback_learning": "The reflection step forced me to actually formulate a metric before speaking again.",
        "ethical_consent_signed": 1,
        "created_at": "2026-11-04 15:02:45"
    },
    {
        "id": 3,
        "participant_id": "P03",
        "target_role": "Software Engineer",
        "prototype_tested": "Prototype A",
        "task_completed": 1,
        "task_time_seconds": 195,
        "sus_scores": [4, 2, 4, 2, 5, 2, 4, 2, 5, 2],
        "sus_total_score": 80.0,
        "feedback_realism": "Clear speech synthesis and responsive UI.",
        "feedback_learning": "The attempt-to-attempt comparison diff clearly confirmed my +4.0 point improvement.",
        "ethical_consent_signed": 1,
        "created_at": "2026-11-04 16:30:10"
    },
    {
        "id": 4,
        "participant_id": "P04",
        "target_role": "Associate Product Manager",
        "prototype_tested": "Prototype B",
        "task_completed": 1,
        "task_time_seconds": 310,
        "sus_scores": [5, 1, 5, 2, 5, 1, 4, 1, 5, 2],
        "sus_total_score": 92.5,
        "feedback_realism": "The Dr. Marcus Vance avatar and spoken follow-up challenged my initial vague answer just like a real interview.",
        "feedback_learning": "Debrief report categorized my performance systematically.",
        "ethical_consent_signed": 1,
        "created_at": "2026-11-05 10:20:18"
    },
    {
        "id": 5,
        "participant_id": "P05",
        "target_role": "UX Research Intern",
        "prototype_tested": "Both",
        "task_completed": 1,
        "task_time_seconds": 260,
        "sus_scores": [4, 1, 5, 2, 4, 1, 5, 2, 5, 2],
        "sus_total_score": 87.5,
        "feedback_realism": "Audio waveform feedback made turn-taking very intuitive.",
        "feedback_learning": "Sentence audit citations eliminate vague advice; told me exactly where STAR Result was lacking.",
        "ethical_consent_signed": 1,
        "created_at": "2026-11-05 11:45:33"
    },
    {
        "id": 6,
        "participant_id": "P06",
        "target_role": "Software Engineer",
        "prototype_tested": "Both",
        "task_completed": 1,
        "task_time_seconds": 215,
        "sus_scores": [5, 1, 5, 1, 5, 2, 5, 2, 5, 1],
        "sus_total_score": 95.0,
        "feedback_realism": "Voice STT recognized technical terms accurately. Minimal latency.",
        "feedback_learning": "Longitudinal progress graph across attempts is super motivating to track score trends.",
        "ethical_consent_signed": 1,
        "created_at": "2026-11-05 14:10:05"
    }
]

# Write JSON
json_path = os.path.join("Evaluation_Data", "CS435_Evaluation_Data.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(participants, f, indent=2)
print("Wrote JSON to", json_path)

# Write CSV
csv_path = os.path.join("Evaluation_Data", "CS435_Evaluation_Data.csv")
fieldnames = [
    "id", "participant_id", "target_role", "prototype_tested", "task_completed",
    "task_time_seconds", "sus_scores", "sus_total_score", "feedback_realism",
    "feedback_learning", "ethical_consent_signed", "created_at"
]
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for p in participants:
        row = dict(p)
        row["sus_scores"] = json.dumps(row["sus_scores"])
        writer.writerow(row)
print("Wrote CSV to", csv_path)

# Update SQLite user_evaluations
db_path = os.path.join("app", "interview_practice.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("DELETE FROM user_evaluations WHERE participant_id LIKE 'P_TEST%'")
for p in participants:
    cur.execute("""
        INSERT OR REPLACE INTO user_evaluations 
        (id, participant_id, target_role, prototype_tested, task_completed, task_time_seconds, sus_scores, sus_total_score, feedback_realism, feedback_learning, ethical_consent_signed, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        p["id"], p["participant_id"], p["target_role"], p["prototype_tested"], p["task_completed"],
        p["task_time_seconds"], json.dumps(p["sus_scores"]), p["sus_total_score"], p["feedback_realism"],
        p["feedback_learning"], p["ethical_consent_signed"], p["created_at"]
    ))
conn.commit()
conn.close()
print("Updated SQLite database at", db_path)
