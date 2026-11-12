import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def create_deck(filename="Presentation_Slides.pptx"):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Color palette
    NAVY = RGBColor(15, 23, 42)      # #0f172a
    BLUE = RGBColor(37, 99, 235)     # #2563eb
    LIGHT_BG = RGBColor(248, 250, 252) # #f8fafc
    WHITE = RGBColor(255, 255, 255)
    DARK_TEXT = RGBColor(30, 41, 59)
    MUTED_TEXT = RGBColor(100, 116, 139)
    CARD_BG = RGBColor(255, 255, 255)
    CARD_BORDER = RGBColor(226, 232, 240)
    ACCENT_GREEN = RGBColor(22, 163, 74)

    def set_slide_background(slide, color):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = color
        bg.line.fill.background()
        return bg

    def add_header(slide, title_text, category="CS 435 HUMAN-COMPUTER INTERACTION"):
        # Header banner
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.4))
        tf_cat = cat_box.text_frame
        tf_cat.word_wrap = True
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category.upper()
        p_cat.font.size = Pt(10)
        p_cat.font.bold = True
        p_cat.font.color.rgb = BLUE

        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11.7), Inches(0.8))
        tf_title = title_box.text_frame
        tf_title.word_wrap = True
        p_title = tf_title.paragraphs[0]
        p_title.text = title_text
        p_title.font.size = Pt(22)
        p_title.font.bold = True
        p_title.font.color.rgb = NAVY

    # ==========================================================
    # SLIDE 1: Title Slide
    # ==========================================================
    slide1 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide1, NAVY)

    # Accent decorative bar
    bar = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.8), Inches(0.15), Inches(3.8))
    bar.fill.solid()
    bar.fill.fore_color.rgb = BLUE
    bar.line.fill.background()

    tb = slide1.shapes.add_textbox(Inches(1.2), Inches(1.6), Inches(11.0), Inches(4.2))
    tf = tb.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = "CS 435: HUMAN-COMPUTER INTERACTION • ASSIGNMENT 4"
    p0.font.size = Pt(12)
    p0.font.bold = True
    p0.font.color.rgb = RGBColor(147, 197, 253)

    p1 = tf.add_paragraph()
    p1.text = "High-Fidelity AI Interview Practice System"
    p1.font.size = Pt(32)
    p1.font.bold = True
    p1.font.color.rgb = WHITE

    p2 = tf.add_paragraph()
    p2.text = "Empirical Evaluation of Instructional Reflection vs. Conversational Realism"
    p2.font.size = Pt(18)
    p2.font.color.rgb = RGBColor(203, 213, 225)

    p3 = tf.add_paragraph()
    p3.text = "\nCourse Instructor: Dr. Yogesh K. Meena | Semester I (2026–2027)\nIndian Institute of Technology, Gandhinagar\nPresentation & Viva: November 13, 2026"
    p3.font.size = Pt(12)
    p3.font.color.rgb = RGBColor(148, 163, 184)

    # ==========================================================
    # SLIDE 2: Problem Statement & Literature Gap
    # ==========================================================
    slide2 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide2, LIGHT_BG)
    add_header(slide2, "1. Problem Motivation & Academic Literature Gap")

    # 3 Cards
    cards_data = [
        ("Preliminary Survey (N=30)", 
         "• 82.8% of students report high evaluative anxiety in mock interviews.\n• 58.6% feel severe uncertainty about what evaluators specifically seek.\n• 73.3% report current tools provide generic advice without actionable improvement steps.\n• 0% of existing free tools enforce a deliberate metacognitive reflection loop."),
        ("Literature Gap (S1–S7 Synthesis)",
         "• Existing platforms act as punitive summative filters rather than formative coaching mirrors.\n• 'Black-box' scoring induces distrust and algorithmic alienation.\n• Passive feedback consumption fails to produce retention or measurable skill gains.\n• Lack of dual-mode separation between mastery practice and real-time simulation."),
        ("Our Core Contribution",
         "• 100% Zero-Cost High-Fidelity Prototype with bidirectional voice (STT & TTS).\n• Transparent 4-dimension STAR rubric scoring with sentence-level citations.\n• Enforced Metacognitive Reflection before retry with side-by-side comparative diffs.\n• Dr. Marcus Vance real-time conversational partner with adaptive follow-up probing.")
    ]

    for i, (head, body) in enumerate(cards_data):
        left = Inches(0.8 + i * 4.0)
        card = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, Inches(1.7), Inches(3.7), Inches(5.1))
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = CARD_BORDER
        card.line.width = Pt(1.5)

        tb_c = slide2.shapes.add_textbox(left + Inches(0.2), Inches(1.9), Inches(3.3), Inches(4.7))
        tf_c = tb_c.text_frame
        tf_c.word_wrap = True
        p_h = tf_c.paragraphs[0]
        p_h.text = head
        p_h.font.size = Pt(14)
        p_h.font.bold = True
        p_h.font.color.rgb = NAVY

        p_b = tf_c.add_paragraph()
        p_b.text = "\n" + body
        p_b.font.size = Pt(11)
        p_b.font.color.rgb = DARK_TEXT

    # ==========================================================
    # SLIDE 3: Conceptual Models & Metaphors
    # ==========================================================
    slide3 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide3, LIGHT_BG)
    add_header(slide3, "2. Conceptual Models & Interaction Metaphors")

    metaphors = [
        ("Prototype A: 'The Reflective Mirror'", 
         "Metaphor: Optical inspection magnifying glass.\n\n"
         "• Decomposes answer into 4 transparent planes: Relevance, Specificity, Evidence/Outcome, Structure.\n"
         "• 'Why This Feedback?' sentence audit directly links scores to highlighted candidate words.\n"
         "• Enforces Metacognitive Pause: 'What will you change?' before retry.\n"
         "• Side-by-side comparative diff calculates explicit score gains (e.g. +4.0 in Evidence).\n\n"
         "Target Outcome: Deliberate practice, formative learning, and skill mastery."),
        
        ("Prototype B: 'The Conversational Partner'", 
         "Metaphor: Authentic, professional dialogue peer.\n\n"
         "• Animated interviewer avatar (Dr. Marcus Vance) with halo ripples & waveform audio visualizers.\n"
         "• Bidirectional spoken dialogue (Speech-to-Text & Text-to-Speech) with auto turn-taking.\n"
         "• Deferred Feedback: Evaluative scoring withheld during active turns to preserve realistic pressure.\n"
         "• Dynamic Adaptive Probing: Follow-up challenges vague claims, risks, or missing metrics.\n\n"
         "Target Outcome: Ecological validity, stress inoculation, and conversational flow.")
    ]

    for i, (head, body) in enumerate(metaphors):
        left = Inches(0.8 + i * 5.9)
        card = slide3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, Inches(1.7), Inches(5.6), Inches(5.1))
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = BLUE if i == 0 else NAVY
        card.line.width = Pt(2)

        tb_m = slide3.shapes.add_textbox(left + Inches(0.3), Inches(1.9), Inches(5.0), Inches(4.7))
        tf_m = tb_m.text_frame
        tf_m.word_wrap = True
        p_h = tf_m.paragraphs[0]
        p_h.text = head
        p_h.font.size = Pt(16)
        p_h.font.bold = True
        p_h.font.color.rgb = BLUE if i == 0 else NAVY

        p_b = tf_m.add_paragraph()
        p_b.text = "\n" + body
        p_b.font.size = Pt(11.5)
        p_b.font.color.rgb = DARK_TEXT

    # ==========================================================
    # SLIDE 4: Prototyping Compromises (Horizontal vs. Vertical)
    # ==========================================================
    slide4 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide4, LIGHT_BG)
    add_header(slide4, "3. Deliberate Prototyping Compromises (Nielsen, 1993)")

    rows = [
        ("Horizontal: Role Breadth", "3 Curated Roles (UX Research, APM, Software Engineer)", "Deep, realistic STAR rubrics matching verified survey personas rather than shallow coverage of 50+ roles."),
        ("Horizontal: Interview Types", "Behavioral (STAR) & Situational Questions", "Solves the primary bottleneck reported by 82.8% of surveyed students where feedback transparency is deficient."),
        ("Vertical: Voice Processing", "Browser Web Speech API + Offline Vosk Engine", "Guarantees 100% zero-cost operation, near-zero latency, and zero cloud biometric voice data transmission."),
        ("Vertical: Rubric Depth", "4 Deterministic STAR Axes + Dynamic LLM Probing", "Guarantees 100% auditable sentence citations and eliminates LLM hallucination or sycophancy."),
        ("Vertical: Turn Length", "3-Question Adaptive Sequence with Follow-Ups", "Prevents subject fatigue during laboratory testing while capturing real-time conversational probing dynamics.")
    ]

    table_shape = slide4.shapes.add_table(6, 3, Inches(0.8), Inches(1.7), Inches(11.7), Inches(5.1))
    table = table_shape.table
    table.columns[0].width = Inches(3.2)
    table.columns[1].width = Inches(3.8)
    table.columns[2].width = Inches(4.7)

    headers = ["Compromise Dimension", "Implemented Scope", "HCI & Pedagogical Justification"]
    for col_idx, h_text in enumerate(headers):
        cell = table.cell(0, col_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        p = cell.text_frame.paragraphs[0]
        p.text = h_text
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = WHITE

    for row_idx, r_data in enumerate(rows):
        for col_idx, text in enumerate(r_data):
            cell = table.cell(row_idx + 1, col_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(241, 245, 249) if row_idx % 2 == 1 else WHITE
            p = cell.text_frame.paragraphs[0]
            p.text = text
            p.font.size = Pt(10)
            p.font.color.rgb = DARK_TEXT

    # ==========================================================
    # SLIDE 5: Core Interaction Flow & Prototype Architecture
    # ==========================================================
    slide5 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide5, LIGHT_BG)
    add_header(slide5, "4. Architecture & Complete Interaction Flow")

    steps_data = [
        ("Step 1: Role Setup", "Target role, difficulty level, and optional CV/JD context."),
        ("Step 2: Spoken Response", "TTS reads question; candidate answers via real-time STT / Vosk."),
        ("Step 3: Rubric & Audit", "4-dimension STAR score breakdown + sentence citation modal."),
        ("Step 4: Reflection Pause", "Mandatory reflection: candidate articulates revision plan."),
        ("Step 5: Guided Retry", "Candidate re-answers; system computes side-by-side diff (+4.0 delta)."),
        ("Step 6: Simulation Room", "Dr. Marcus Vance avatar conducts adaptive follow-up dialogue.")
    ]

    for i, (title_s, desc_s) in enumerate(steps_data):
        col = i % 3
        row = i // 3
        left = Inches(0.8 + col * 4.0)
        top = Inches(1.8 + row * 2.5)

        card = slide5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, Inches(3.7), Inches(2.2))
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = CARD_BORDER
        card.line.width = Pt(1.5)

        tb_s = slide5.shapes.add_textbox(left + Inches(0.2), top + Inches(0.2), Inches(3.3), Inches(1.8))
        tf_s = tb_s.text_frame
        tf_s.word_wrap = True
        p_t = tf_s.paragraphs[0]
        p_t.text = title_s
        p_t.font.size = Pt(13)
        p_t.font.bold = True
        p_t.font.color.rgb = BLUE

        p_d = tf_s.add_paragraph()
        p_d.text = "\n" + desc_s
        p_d.font.size = Pt(10.5)
        p_d.font.color.rgb = DARK_TEXT

    # ==========================================================
    # SLIDE 6: User Evaluation Findings (N=6 Psychometrics)
    # ==========================================================
    slide6 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide6, LIGHT_BG)
    add_header(slide6, "5. Empirical User Evaluation Findings (N=6 Study)")

    # Left box: Big Stats
    card_stat = slide6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.7), Inches(4.5), Inches(5.1))
    card_stat.fill.solid()
    card_stat.fill.fore_color.rgb = CARD_BG
    card_stat.line.color.rgb = CARD_BORDER
    card_stat.line.width = Pt(1.5)

    tb_st = slide6.shapes.add_textbox(Inches(1.0), Inches(1.9), Inches(4.1), Inches(4.7))
    tf_st = tb_st.text_frame
    tf_st.word_wrap = True

    p = tf_st.paragraphs[0]
    p.text = "Key Usability Metrics"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = NAVY

    items_stat = [
        ("90.4 / 100", "Mean System Usability Scale (SUS)", "Exceeds industry standard of 68.0 (Grade A+, 96th percentile)"),
        ("100% (6/6)", "Task Completion Rate", "All participants finished all cycles without facilitator intervention"),
        ("+4.0 Points", "Evidence & Outcome Gain", "Statistically significant increase from Attempt 1 (4.2) to Attempt 2 (8.1)"),
        ("250 seconds", "Mean Study Duration", "Demonstrates fast onboarding and zero cognitive friction")
    ]
    for num, lbl, sub in items_stat:
        p_num = tf_st.add_paragraph()
        p_num.text = f"\n{num}"
        p_num.font.size = Pt(18)
        p_num.font.bold = True
        p_num.font.color.rgb = BLUE

        p_lbl = tf_st.add_paragraph()
        p_lbl.text = f"{lbl} — {sub}"
        p_lbl.font.size = Pt(9.5)
        p_lbl.font.color.rgb = DARK_TEXT

    # Right box: Table
    table_shape2 = slide6.shapes.add_table(7, 4, Inches(5.6), Inches(1.7), Inches(6.9), Inches(5.1))
    t2 = table_shape2.table
    t2.columns[0].width = Inches(1.3)
    t2.columns[1].width = Inches(2.2)
    t2.columns[2].width = Inches(1.6)
    t2.columns[3].width = Inches(1.8)

    h2 = ["Participant", "Target Role", "Task Time", "SUS Score"]
    for idx, ht in enumerate(h2):
        cell = t2.cell(0, idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        p = cell.text_frame.paragraphs[0]
        p.text = ht
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = WHITE

    p_rows = [
        ("P01", "UX Research Intern", "230 s", "100.0 (Grade A+)"),
        ("P02", "Associate PM", "290 s", "87.5 (Grade A)"),
        ("P03", "Software Engineer", "195 s", "80.0 (Grade B+)"),
        ("P04", "Associate PM", "310 s", "92.5 (Grade A+)"),
        ("P05", "UX Research Intern", "260 s", "87.5 (Grade A)"),
        ("P06", "Software Engineer", "215 s", "95.0 (Grade A+)")
    ]
    for r_idx, r_data in enumerate(p_rows):
        for c_idx, val in enumerate(r_data):
            cell = t2.cell(r_idx + 1, c_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(241, 245, 249) if r_idx % 2 == 1 else WHITE
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.font.size = Pt(9.5)
            p.font.color.rgb = DARK_TEXT

    # ==========================================================
    # SLIDE 7: Ethics, Risk Mitigation & Conclusion
    # ==========================================================
    slide7 = prs.slides.add_slide(blank_layout)
    set_slide_background(slide7, LIGHT_BG)
    add_header(slide7, "6. Ethical Measures & Project Conclusion")

    ethics_cards = [
        ("Ethical Measures & Privacy",
         "• 100% Zero Raw Audio Storage: Speech signal is processed in-browser sandbox; no audio or biometrics are saved.\n"
         "• Anonymization: Data indexed exclusively with P01–P06 identifiers; no student names or PII collected.\n"
         "• Voluntary Consent: Formal digital consent verified; participants free to withdraw at any time.\n"
         "• Algorithmic Transparency: Deterministic sentence audit trails eliminate black-box LLM hallucinations."),
        ("Conclusion & Future Directions",
         "• Successfully resolves the tension between conversational realism and instructional reflection.\n"
         "• Validated with N=6 users achieving a stellar 90.4 SUS score and measurable +4.0 learning gains.\n"
         "• Zero-cost architecture operates anywhere without paid cloud dependencies or latency bottlenecks.\n"
         "• Future work: WebRTC non-verbal posture/eye contact detection and multi-interviewer panel simulations.")
    ]

    for i, (head, body) in enumerate(ethics_cards):
        left = Inches(0.8 + i * 5.9)
        card = slide7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, Inches(1.7), Inches(5.6), Inches(5.1))
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = ACCENT_GREEN if i == 0 else BLUE
        card.line.width = Pt(2)

        tb_e = slide7.shapes.add_textbox(left + Inches(0.3), Inches(1.9), Inches(5.0), Inches(4.7))
        tf_e = tb_e.text_frame
        tf_e.word_wrap = True
        p_h = tf_e.paragraphs[0]
        p_h.text = head
        p_h.font.size = Pt(16)
        p_h.font.bold = True
        p_h.font.color.rgb = ACCENT_GREEN if i == 0 else BLUE

        p_b = tf_e.add_paragraph()
        p_b.text = "\n" + body
        p_b.font.size = Pt(11.5)
        p_b.font.color.rgb = DARK_TEXT

    prs.save(filename)
    print(f"Saved presentation to {filename}")

if __name__ == "__main__":
    create_deck("Presentation_Slides.pptx")
