"""Flu Dynamics S&F Tutor — Streamlit entry point."""

import html as html_lib
import threading
import uuid
from pathlib import Path

_APP_DIR = Path(__file__).parent

import plotly.graph_objects as go
import streamlit as st

from assess import get_pre_assessment_extraction, score_assessment
from guardrails import apply_tutor_response
from llm import evaluate_bot_answer, get_tutor_response
from logger import (
    init_session,
    log_turn,
    save_bot_results,
    save_pre_assessment,
    save_pre_assessment_raw,
    save_quiz_results,
    save_session_outcome,
    save_session_transcript,
    save_survey,
)
from models import CASE_STUDY
from quiz import BOT_QUESTIONS, QUESTIONS, TOTAL_BOT, TOTAL_QUESTIONS
from render import render_sfd
from simulation import peak_infected, simulate

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Flu Dynamics S&F Tutor",
    layout="wide",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        max-width: 100% !important;
    }
    .top-bar {
        display: inline-flex;
        align-items: center;
        gap: 14px;
        background: #1e293b;
        color: #e2e8f0;
        border-radius: 8px;
        padding: 5px 12px;
        font-size: 0.78rem;
        margin-bottom: 10px;
        flex-wrap: wrap;
        max-width: 320px;
    }
.top-bar .label { color: #94a3b8; margin-right: 3px; }
    .top-bar .value { font-weight: 600; color: #f1f5f9; }
    .top-bar .tag {
        background: #334155;
        border-radius: 4px;
        padding: 1px 7px;
        font-family: monospace;
        font-size: 0.75rem;
        color: #7dd3fc;
    }
    .case-study-bar {
        background: #0f172a;
        border: 1px solid #1e3a5f;
        border-radius: 8px;
        padding: 10px 16px;
        font-size: 0.9rem;
        line-height: 1.6;
        color: #cbd5e1;
        max-height: 100px;
        overflow-y: auto;
        margin-bottom: 10px;
    }
    .case-study-bar .cs-title {
        font-size: 0.7rem;
        letter-spacing: 0.07em;
        color: #60a5fa;
        text-transform: uppercase;
        font-weight: 700;
        display: block;
        margin-bottom: 5px;
    }
    [data-testid="collapsedControl"] { display: none !important; }
    section[data-testid="stSidebar"] { display: none !important; }
    .info-scroll {
        max-height: 420px;
        overflow-y: auto;
        padding-right: 4px;
    }
    .info-scroll::-webkit-scrollbar { width: 4px; }
    .info-scroll::-webkit-scrollbar-track { background: transparent; }
    .info-scroll::-webkit-scrollbar-thumb {
        background: #334155;
        border-radius: 4px;
    }
    [data-testid="stGraphVizChart"] svg {
        max-width: 100% !important;
        max-height: 380px !important;
        height: auto !important;
    }
    .chat-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 0.4rem;
    }
    .chat-header h3 { margin: 0; font-size: 1.1rem; font-weight: 700; }
    .thinking-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #1e3a5f;
        color: #7dd3fc;
        border-radius: 20px;
        padding: 2px 10px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        animation: pulse 1.2s ease-in-out infinite;
    }
    .thinking-pill .dot {
        width: 6px; height: 6px;
        background: #38bdf8;
        border-radius: 50%;
        display: inline-block;
        animation: bounce 1.2s ease-in-out infinite;
    }
    .thinking-pill .dot:nth-child(2) { animation-delay: 0.2s; }
    .thinking-pill .dot:nth-child(3) { animation-delay: 0.4s; }
    @keyframes bounce {
        0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
        40% { transform: translateY(-4px); opacity: 1; }
    }
    @keyframes pulse {
        0%, 100% { opacity: 0.85; }
        50% { opacity: 1; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state initialisation ──────────────────────────────────────────────
_defaults = {
    "messages": [],
    "stocks": [],
    "flows": [],
    "parameters": [],
    "loops": [],
    "guardrail_errors": [],
    "is_thinking": False,
    "pending_input": None,
    "last_response_debug": None,
    "log_error": None,
    "session_id": None,
    "student_id": None,
    "phase": "pre_assessment",
    "quiz_question_idx": 0,
    "quiz_answers": {},
    "quiz_saved": False,
    "quiz_started": False,
    # BOT state
    "bot_question_idx": 0,
    "bot_messages": [],
    "bot_correct": False,
    "bot_evaluating": False,
    "bot_attempts": {},
    "bot_results": {},
    # Misc
    "confirm_finish": False,
    "survey_saved": False,
    "survey_step": 0,
    "survey_data": {},
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Anonymous ID (Python-only, no JS required) ───────────────────────────────
# On first visit: generate a short random ID, write it into the URL query param,
# and rerun — the URL becomes ?anon_id=anon-xxxxxx.
# On every subsequent visit/rerun the param is already in the URL and we just read it.
# Bookmarking the URL with the param preserves the same ID across browser sessions.
if "anon_id" not in st.query_params:
    st.query_params["anon_id"] = "anon-" + uuid.uuid4().hex[:6]
    st.rerun()

_anon_id = st.query_params["anon_id"]

# Initialise student_id + session once per Streamlit session (or after reset)
if not st.session_state.student_id:
    st.session_state.student_id = _anon_id
    try:
        st.session_state.session_id = init_session(_anon_id)
    except Exception as e:
        st.error(f"Could not connect to database: {e}")
        st.stop()

# ── Pre-assessment phase ──────────────────────────────────────────────────────
if st.session_state.phase == "pre_assessment":
    st.title("Flu Dynamics S&F Tutor")
    st.markdown(
        f'<div class="case-study-bar">'
        f'<span class="cs-title">Case Study — RC4 Flu Outbreak</span>'
        f'{CASE_STUDY}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("### Before we begin — sketch the system yourself")
    st.markdown(
        "Read the case study above. Before the tutor guides you, describe what you think "
        "the **key stocks** (accumulations) and **flows** (rates) are. "
        "What parameters drive the infection? Are there any feedback loops?\n\n"
        "_There are no right or wrong answers — this captures your starting mental model._"
    )

    pre_text = st.text_area(
        "Your response",
        height=180,
        placeholder=(
            "e.g. I think there are two main groups: healthy people and sick people. "
            "People move from healthy to sick at an infection rate that depends on "
            "how many contacts they make and how likely they are to meet someone infected..."
        ),
        key="pre_assessment_input",
    )

    btn_col1, btn_col2, _ = st.columns([1.8, 1.2, 3])
    with btn_col1:
        submit_pressed = st.button(
            "Submit & start guided session",
            type="primary",
            use_container_width=True,
        )
    with btn_col2:
        skip_pressed = st.button(
            "Skip →",
            use_container_width=True,
            help="Skip straight to the Socratic guided session.",
        )

    if submit_pressed:
        if not pre_text.strip():
            st.warning("Please write something before submitting, or click Skip.")
        else:
            session_id = st.session_state.session_id
            text = pre_text.strip()
            try:
                save_pre_assessment_raw(session_id, text)
            except Exception:
                pass

            def _score_and_save(sid: str, raw: str) -> None:
                try:
                    extraction = get_pre_assessment_extraction(raw)
                    score = score_assessment(
                        [s.model_dump() for s in extraction.extracted_stocks],
                        [f.model_dump() for f in extraction.extracted_flows],
                        [p.model_dump() for p in extraction.extracted_parameters],
                        [lp.model_dump() for lp in extraction.extracted_loops],
                    )
                    save_pre_assessment(sid, score, raw)
                except Exception:
                    pass

            threading.Thread(target=_score_and_save, args=(session_id, text), daemon=True).start()
            st.session_state.phase = "tutoring"
            st.rerun()

    if skip_pressed:
        if pre_text.strip():
            try:
                save_pre_assessment_raw(st.session_state.session_id, pre_text.strip())
            except Exception:
                pass
        st.session_state.phase = "tutoring"
        st.rerun()

    st.stop()

# ── Quiz phase ────────────────────────────────────────────────────────────────
if st.session_state.phase == "quiz_mcq":
    st.title("What did we learn? — The 'Limits to Growth' Archetype")

    if st.button("← Back to Chat"):
        st.session_state.phase = "tutoring"
        st.rerun()

    idx = st.session_state.quiz_question_idx

    if idx >= TOTAL_QUESTIONS:
        correct = sum(
            1
            for q_idx, ans in st.session_state.quiz_answers.items()
            if ans == QUESTIONS[q_idx]["answer"]
        )

        if correct == TOTAL_QUESTIONS:
            st.success(f"Perfect score — {correct}/{TOTAL_QUESTIONS}!")
        elif correct >= TOTAL_QUESTIONS - 1:
            st.success(f"Great work — {correct}/{TOTAL_QUESTIONS} correct.")
        else:
            st.info(f"Quiz complete — {correct}/{TOTAL_QUESTIONS} correct.")

        st.markdown(
            "### Key Takeaway\n"
            "The **'Limits to Growth'** archetype describes any system where a reinforcing "
            "growth engine is eventually constrained by a balancing loop.\n\n"
            "In the RC4 flu model:\n"
            "- **R1** (Reinforcing) drives the epidemic: more infected → higher chance of "
            "contact → faster spread → even more infected.\n"
            "- **B1** (Balancing) is the constraint: as susceptibles are depleted, "
            "the fuel for R1 runs out and the epidemic slows.\n"
            "- **B2** (Balancing) is the recovery engine: infected residents heal and "
            "return to susceptible.\n\n"
            "**The policy insight:** targeting the reinforcing loop (reduce contact rate) "
            "is far more effective than trying to fight the growth after it has started. "
            "This is why early social distancing 'flattens the curve' — it weakens R1 "
            "before B1 can do its work."
        )

        if st.button("Continue →", type="primary"):
            st.session_state.phase = "quiz_bot"
            st.rerun()
        st.stop()

    st.progress(idx / TOTAL_QUESTIONS, text=f"Question {idx + 1} of {TOTAL_QUESTIONS}")
    q = QUESTIONS[idx]

    st.markdown(f"#### Question {idx + 1}")
    st.markdown(q["question"])

    already_answered = idx in st.session_state.quiz_answers

    selected = st.radio(
        "Choose your answer:",
        options=q["options"],
        key=f"quiz_radio_{idx}",
        index=None,
        disabled=already_answered,
    )

    if not already_answered:
        if st.button("Submit answer", type="primary", disabled=(selected is None)):
            ans_idx = q["options"].index(selected)
            st.session_state.quiz_answers[idx] = ans_idx
            # Persist the running answer set immediately (per-answer save)
            try:
                answer_log = [
                    {
                        "question": QUESTIONS[q_idx]["question"],
                        "selected": QUESTIONS[q_idx]["options"][a],
                        "correct_answer": QUESTIONS[q_idx]["options"][QUESTIONS[q_idx]["answer"]],
                        "is_correct": a == QUESTIONS[q_idx]["answer"],
                    }
                    for q_idx, a in st.session_state.quiz_answers.items()
                ]
                correct_so_far = sum(
                    1 for q_idx, a in st.session_state.quiz_answers.items()
                    if a == QUESTIONS[q_idx]["answer"]
                )
                save_quiz_results(
                    st.session_state.session_id,
                    {"score": correct_so_far, "total": TOTAL_QUESTIONS, "answers": answer_log},
                )
            except Exception:
                pass
            st.rerun()
    else:
        student_ans = st.session_state.quiz_answers[idx]
        correct_ans = q["answer"]
        if student_ans == correct_ans:
            st.success("Correct! ✓")
        else:
            st.error(f"Not quite. The correct answer: **{q['options'][correct_ans]}**")
        st.info(f"**Why:** {q['explanation']}")

        # Question 4 (idx 3) — show the Limits to Growth archetype diagram
        if idx == 3:
            img_path = _APP_DIR / "limitstogrowth.jpg"
            if img_path.exists():
                st.image(str(img_path), caption="The 'Limits to Growth' archetype", use_container_width=True)

        label = "Next question →" if idx < TOTAL_QUESTIONS - 1 else "See results →"
        if st.button(label, type="primary"):
            st.session_state.quiz_question_idx += 1
            st.rerun()

    st.stop()

# ── Quiz BOT phase (chat-based Behaviour Over Time) ──────────────────────────
if st.session_state.phase == "quiz_bot":
    nav_left, nav_right = st.columns([1, 1])
    with nav_left:
        if st.button("← Back to Chat", key="back_bot"):
            st.session_state.phase = "tutoring"
            st.rerun()
    with nav_right:
        if st.button("Skip to Feedback →", key="skip_to_feedback"):
            st.session_state.phase = "survey"
            st.rerun()

    bot_idx = st.session_state.bot_question_idx

    if bot_idx >= TOTAL_BOT:
        # All BOT questions done
        st.title("Reflection Complete")
        st.success(
            f"You answered all {TOTAL_BOT} Behaviour Over Time questions. "
            "Great systems thinking!"
        )
        st.markdown(
            "### Key Takeaway\n"
            "In the RC4 flu model, **timing** is everything. R1 drives explosive early "
            "growth, but B1 (susceptible depletion) and B2 (recovery) gradually neutralise "
            "it — producing the S-shaped endemic equilibrium. Tracing *how* each variable "
            "behaves over time reveals *why* the system reaches a steady state rather than "
            "burning out to zero.\n\n"
            "**The policy insight:** intervening on R1 early (reducing contact rate) "
            "is far more effective than waiting for B1 and B2 to do the work."
        )
        if st.button("Continue to Feedback →", type="primary"):
            st.session_state.phase = "survey"
            st.rerun()
        st.stop()

    total_all = TOTAL_QUESTIONS + TOTAL_BOT
    global_idx = TOTAL_QUESTIONS + bot_idx
    st.title("Part 2 — Behaviour Over Time")
    st.progress(global_idx / total_all, text=f"Question {global_idx + 1} of {total_all}")

    bot_q = BOT_QUESTIONS[bot_idx]
    st.markdown(f"#### Question {global_idx + 1}")
    st.markdown(bot_q["question"])

    chat_container = st.container(height=320)
    with chat_container:
        for msg in st.session_state.bot_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if st.session_state.bot_correct:
        st.success("You've got it! ✓")
        label = "Next question →" if bot_idx < TOTAL_BOT - 1 else "See reflection →"
        if st.button(label, type="primary"):
            st.session_state.bot_question_idx += 1
            st.session_state.bot_messages = []
            st.session_state.bot_correct = False
            st.session_state.bot_evaluating = False
            st.rerun()
    else:
        if user_input := st.chat_input("Type your answer...", key="bot_chat_input"):
            st.session_state.bot_messages.append({"role": "user", "content": user_input})
            st.session_state.bot_evaluating = True
            st.session_state.bot_attempts[bot_idx] = (
                st.session_state.bot_attempts.get(bot_idx, 0) + 1
            )
            st.rerun()

    if st.session_state.bot_evaluating:
        try:
            result = evaluate_bot_answer(
                question=bot_q["question"],
                reference_answer=bot_q["reference_answer"],
                chat_history=st.session_state.bot_messages,
                minimum_criteria=bot_q.get("minimum_criteria", ""),
            )
            st.session_state.bot_messages.append(
                {"role": "assistant", "content": result.feedback}
            )
            st.session_state.bot_correct = result.is_correct
            if result.is_correct:
                st.session_state.bot_results[bot_idx] = {
                    "question": bot_q["question"],
                    "attempts": st.session_state.bot_attempts.get(bot_idx, 1),
                    "correct": True,
                }
                try:
                    save_bot_results(st.session_state.session_id, st.session_state.bot_results)
                except Exception:
                    pass
        except Exception as e:
            st.session_state.bot_messages.append(
                {"role": "assistant", "content": f"Sorry, evaluation failed: {e}. Please try again."}
            )
        st.session_state.bot_evaluating = False
        st.rerun()

    st.stop()

# ── Survey phase (single page) ────────────────────────────────────────────────
if st.session_state.phase == "survey":
    if st.button("← Back to Chat", key="back_survey"):
        st.session_state.phase = "tutoring"
        st.rerun()

    if st.session_state.survey_saved:
        st.title("Thank you!")
        st.balloons()
        st.markdown(
            "Your feedback has been submitted. Thank you for participating!\n\n"
            "You may now close this tab, or return to review your diagram."
        )
        if st.button("← Return to my diagram", type="primary"):
            st.session_state.phase = "tutoring"
            st.rerun()
        st.stop()

    st.title("Session Feedback")
    st.markdown(
        "Thank you for completing the session! Your feedback helps improve the tutor. "
        "All responses are anonymous."
    )

    _SCALE = ["1 — Not at all", "2 — A little", "3 — Moderately",
              "4 — Quite a lot", "5 — Very much"]

    with st.form("survey_form"):
        learning_points = st.text_area(
            "What are your key learning points from this session?",
            height=120,
            placeholder="e.g. I learned how reinforcing and balancing loops interact to produce S-shaped growth...",
        )

        st.markdown("##### Ratings")
        r_col1, r_col2, r_col3 = st.columns(3)
        with r_col1:
            llm_help = st.radio(
                "How much did the tutor help you learn?",
                options=_SCALE, index=None, key="sv_r1",
            )
        with r_col2:
            junior_seminar = st.radio(
                "Does it aid understanding of Junior Seminar courses?",
                options=_SCALE, index=None, key="sv_r2",
            )
        with r_col3:
            fundamentals = st.radio(
                "Did it help with System Dynamics fundamentals?",
                options=_SCALE, index=None, key="sv_r3",
            )

        strength = st.text_area(
            "What do you think is the strength of this LLM tutor?",
            height=90,
            placeholder="e.g. It guides without giving away answers...",
        )
        improvement = st.text_area(
            "What is something that could be improved?",
            height=90,
            placeholder="e.g. Sometimes the questions felt repetitive...",
        )

        submitted = st.form_submit_button(
            "Submit Feedback", type="primary", use_container_width=True
        )

    if submitted:
        survey_data = {
            "learning_points": learning_points.strip(),
            "llm_helpfulness": int(llm_help[0]) if llm_help else None,
            "junior_seminar_understanding": int(junior_seminar[0]) if junior_seminar else None,
            "sd_fundamentals_understanding": int(fundamentals[0]) if fundamentals else None,
            "strength": strength.strip(),
            "improvement": improvement.strip(),
        }
        try:
            save_survey(st.session_state.session_id, survey_data)
        except Exception:
            pass
        st.session_state.survey_saved = True
        st.rerun()

    st.stop()

# ── Build S&F diagram ─────────────────────────────────────────────────────────
sfd = render_sfd(
    st.session_state.stocks,
    st.session_state.flows,
    st.session_state.parameters,
    st.session_state.loops,
)

# ── Top bar ───────────────────────────────────────────────────────────────────
info_left, info_right = st.columns([1, 2])
with info_left:
    safe_student_id = html_lib.escape(str(st.session_state.student_id or ""))
    safe_log_error = html_lib.escape(str(st.session_state.log_error)) if st.session_state.log_error else ""
    st.markdown(
        f'<div style="display:inline-flex;align-items:center;gap:8px;'
        f'background:#1e293b;border-radius:6px;padding:5px 12px;font-size:0.78rem;">'
        f'<span style="color:#94a3b8">Your ID</span>'
        f'<span style="background:#334155;border-radius:4px;padding:1px 7px;'
        f'font-family:monospace;font-size:0.73rem;color:#7dd3fc">{safe_student_id}</span>'
        + (f'<span style="color:#f87171;font-size:0.72rem">⚠ {safe_log_error}</span>'
           if safe_log_error else '')
        + '</div>',
        unsafe_allow_html=True,
    )
with info_right:
    if st.session_state.quiz_started:
        # Already entered quiz — smart-route back to the right sub-phase
        if st.session_state.quiz_question_idx < TOTAL_QUESTIONS:
            dest = "quiz_mcq"
        elif st.session_state.bot_question_idx < TOTAL_BOT:
            dest = "quiz_bot"
        else:
            dest = "survey"
        btn_back, btn_reset = st.columns(2)
        with btn_back:
            if st.button("Back to Quiz →", use_container_width=True, type="primary"):
                st.session_state.phase = dest
                st.rerun()
        with btn_reset:
            if st.button("Reset", use_container_width=True):
                for k in _defaults:
                    st.session_state[k] = _defaults[k]
                st.session_state.session_id = None
                st.session_state.student_id = None
                st.rerun()
    elif st.session_state.confirm_finish:
        # Inline confirmation: label | Yes | No
        c_lbl, c_yes, c_no = st.columns([1.4, 1, 1])
        with c_lbl:
            st.markdown(
                '<span style="font-size:0.75rem;color:#fbbf24;white-space:nowrap">'
                '⚠ End session?</span>',
                unsafe_allow_html=True,
            )
        with c_yes:
            if st.button("Yes", type="primary", use_container_width=True):
                try:
                    outcome = score_assessment(
                        st.session_state.stocks,
                        st.session_state.flows,
                        st.session_state.parameters,
                        st.session_state.loops,
                    )
                    save_session_outcome(st.session_state.session_id, outcome)
                except Exception:
                    pass
                try:
                    transcript_lines = []
                    for m in st.session_state.messages:
                        role = "You" if m["role"] == "user" else "Tutor"
                        transcript_lines.append(f"[{role}]\n{m['content']}\n")
                    save_session_transcript(
                        st.session_state.session_id,
                        "\n".join(transcript_lines),
                        sfd.source,
                    )
                except Exception:
                    pass
                st.session_state.confirm_finish = False
                st.session_state.quiz_started = True
                st.session_state.phase = "quiz_mcq"
                st.rerun()
        with c_no:
            if st.button("No", use_container_width=True):
                st.session_state.confirm_finish = False
                st.rerun()
    else:
        # Normal state — Finish + Reset side by side
        btn_finish, btn_reset = st.columns(2)
        with btn_finish:
            if st.button("Finish →", use_container_width=True, type="primary",
                         help="End session and go to the archetype quiz"):
                st.session_state.confirm_finish = True
                st.rerun()
        with btn_reset:
            if st.button("Reset", use_container_width=True):
                for k in _defaults:
                    st.session_state[k] = _defaults[k]
                st.session_state.session_id = None
                st.session_state.student_id = None
                st.rerun()

# ── Case study banner ─────────────────────────────────────────────────────────
st.markdown(
    f'<div class="case-study-bar">'
    f'<span class="cs-title">Case Study — RC4 Flu Outbreak</span>'
    f'{CASE_STUDY}</div>',
    unsafe_allow_html=True,
)

chat_col, diagram_col, info_col = st.columns([1, 1.4, 0.6])

# ── Middle column: S&F diagram + simulation + export ─────────────────────────
with diagram_col:
    st.subheader("Stock & Flow Diagram")
    st.graphviz_chart(sfd, use_container_width=True)

    # ── Simulation (shown once both stocks and both flows are approved) ──────
    has_stocks = len(st.session_state.stocks) >= 2
    has_flows = len(st.session_state.flows) >= 2
    if has_stocks and has_flows:
        with st.expander("Simulate the model (6 months)", expanded=False):
            sim = simulate()
            peak_i, peak_t = peak_infected(sim)

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=sim["t"], y=sim["susceptible"],
                name="SUSCEPTIBLE",
                line={"color": "#2563eb", "width": 2},
            ))
            fig.add_trace(go.Scatter(
                x=sim["t"], y=sim["infected"],
                name="INFECTED",
                line={"color": "#dc2626", "width": 2},
            ))
            fig.update_layout(
                xaxis_title="Time (months)",
                yaxis_title="People",
                legend={"orientation": "h", "y": -0.2},
                margin={"t": 10, "b": 10, "l": 10, "r": 10},
                height=280,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(15,23,42,0.4)",
                font={"color": "#cbd5e1", "size": 11},
                xaxis={"gridcolor": "#1e293b"},
                yaxis={"gridcolor": "#1e293b"},
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                f"Peak infected: **{peak_i:.0f} people** at month **{peak_t:.1f}**. "
                "Notice the S-shaped curve for INFECTED — rapid exponential growth "
                "driven by R1, then levelling off as B1 (susceptible depletion) and "
                "B2 (recovery) neutralise the reinforcing loop. "
                "This is the 'Limits to Growth' archetype."
            )

    # ── Export ───────────────────────────────────────────────────────────────
    has_chat = bool(st.session_state.messages)
    has_diagram = bool(st.session_state.stocks)

    if has_chat or has_diagram:
        st.markdown(
            '<p style="font-size:0.68rem;color:#64748b;margin:4px 0 4px;">Export:</p>',
            unsafe_allow_html=True,
        )
        exp_cols = st.columns(2)

        if has_chat:
            transcript_lines = []
            for m in st.session_state.messages:
                role = "You" if m["role"] == "user" else "Tutor"
                transcript_lines.append(f"[{role}]\n{m['content']}\n")
            with exp_cols[0]:
                st.download_button(
                    "📄 Transcript",
                    "\n".join(transcript_lines),
                    file_name=f"transcript_{st.session_state.student_id}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

        if has_diagram:
            with exp_cols[1]:
                st.download_button(
                    "🔗 SFD (DOT)",
                    sfd.source,
                    file_name=f"sfd_{st.session_state.student_id}.gv",
                    mime="text/plain",
                    use_container_width=True,
                    help="Open the .gv file at graphviz.online to render it.",
                )

# ── Right column: model elements ──────────────────────────────────────────────
with info_col:
    stocks_html = ""
    def _count_badge(n: int, color: str) -> str:
        if n == 0:
            return ""
        return (
            f'<span style="margin-left:6px;background:{color}22;color:{color};'
            f'border-radius:10px;padding:1px 7px;font-size:0.68rem;font-weight:700">'
            f'{n}</span>'
        )

    if st.session_state.stocks:
        for s in st.session_state.stocks:
            iv = s.get("initial_value")
            iv_str = f" = {int(iv)}" if iv is not None else ""
            stocks_html += (
                f'<div style="font-size:0.82rem;padding:4px 0;'
                f'border-bottom:1px solid #e2e8f020;color:#e2e8f0">'
                f'<b style="color:#93c5fd">{html_lib.escape(s["name"])}</b>'
                f'<span style="color:#94a3b8;font-size:0.75rem">'
                f'{html_lib.escape(iv_str)} {html_lib.escape(s.get("unit","People"))}</span></div>'
            )
    else:
        stocks_html = '<div style="font-size:0.78rem;color:#475569;font-style:italic">None yet</div>'

    flows_html = ""
    if st.session_state.flows:
        for f in st.session_state.flows:
            src = html_lib.escape(f.get("from_stock") or "☁")
            tgt = html_lib.escape(f.get("to_stock") or "☁")
            flows_html += (
                f'<div style="font-size:0.82rem;padding:4px 0;'
                f'border-bottom:1px solid #e2e8f020;color:#e2e8f0">'
                f'<b style="color:#fbbf24">{html_lib.escape(f["name"])}</b> '
                f'<span style="color:#64748b;font-size:0.73rem">{src} → {tgt}</span></div>'
            )
    else:
        flows_html = '<div style="font-size:0.78rem;color:#475569;font-style:italic">None yet</div>'

    params_html = ""
    if st.session_state.parameters:
        for p in st.session_state.parameters:
            val = p.get("value")
            eq = p.get("equation")
            detail = f" = {val}" if val is not None else (f" = {eq}" if eq else "")
            params_html += (
                f'<div style="font-size:0.82rem;padding:4px 0;'
                f'border-bottom:1px solid #e2e8f020;color:#e2e8f0">'
                f'· <b style="color:#86efac">{html_lib.escape(p["name"])}</b>'
                f'<span style="color:#64748b;font-size:0.73rem">{html_lib.escape(detail)}</span></div>'
            )
    else:
        params_html = '<div style="font-size:0.78rem;color:#475569;font-style:italic">None yet</div>'

    loops_html = ""
    if st.session_state.loops:
        for lp in st.session_state.loops:
            name = html_lib.escape(lp["name"])
            loop_type = html_lib.escape(lp["loop_type"].capitalize())
            seq = lp["variable_sequence"]
            path = html_lib.escape(" → ".join(seq) + (f" → {seq[0]}" if seq else ""))
            color = "#16a34a" if lp["loop_type"] == "reinforcing" else "#dc2626"
            loops_html += (
                f'<div style="margin-bottom:8px;padding:7px 9px;'
                f'border-left:3px solid {color};border-radius:4px;'
                f'background:rgba(255,255,255,0.04)">'
                f'<span style="font-weight:700;color:{color};font-size:0.84rem">{name}</span> '
                f'<span style="font-size:0.74rem;color:#64748b">({loop_type})</span><br>'
                f'<span style="font-size:0.74rem;line-height:1.6;color:#cbd5e1">{path}</span>'
                f'</div>'
            )
    else:
        loops_html = '<div style="font-size:0.78rem;color:#475569;font-style:italic">None yet</div>'

    n_s = len(st.session_state.stocks)
    n_f = len(st.session_state.flows)
    n_p = len(st.session_state.parameters)
    n_l = len(st.session_state.loops)

    st.markdown(
        f'<div class="info-scroll">'
        # Stocks header + count badge
        f'<div style="display:flex;align-items:center;margin-bottom:6px">'
        f'<span style="font-size:0.7rem;font-weight:700;letter-spacing:0.06em;'
        f'color:#93c5fd;text-transform:uppercase">Stocks</span>'
        f'{_count_badge(n_s, "#93c5fd")}</div>'
        f'{stocks_html}'
        # Flows header + count badge
        f'<div style="display:flex;align-items:center;margin:12px 0 6px">'
        f'<span style="font-size:0.7rem;font-weight:700;letter-spacing:0.06em;'
        f'color:#fbbf24;text-transform:uppercase">Flows</span>'
        f'{_count_badge(n_f, "#fbbf24")}</div>'
        f'{flows_html}'
        # Parameters header + count badge
        f'<div style="display:flex;align-items:center;margin:12px 0 6px">'
        f'<span style="font-size:0.7rem;font-weight:700;letter-spacing:0.06em;'
        f'color:#86efac;text-transform:uppercase">Parameters</span>'
        f'{_count_badge(n_p, "#86efac")}</div>'
        f'{params_html}'
        # Feedback loops header + count badge
        f'<div style="display:flex;align-items:center;margin:12px 0 6px">'
        f'<span style="font-size:0.7rem;font-weight:700;letter-spacing:0.06em;'
        f'color:#60a5fa;text-transform:uppercase">Feedback Loops</span>'
        f'{_count_badge(n_l, "#60a5fa")}</div>'
        f'{loops_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Left column: chat ─────────────────────────────────────────────────────────
with chat_col:
    if st.session_state.is_thinking:
        st.markdown(
            '<div class="chat-header"><h3>Chat</h3>'
            '<span class="thinking-pill">'
            '<span class="dot"></span><span class="dot"></span><span class="dot"></span>'
            '&nbsp;Thinking…</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="chat-header"><h3>Chat</h3></div>', unsafe_allow_html=True)

    chat_container = st.container(height=520)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

# ── Chat input ────────────────────────────────────────────────────────────────
if user_input := st.chat_input("Describe a stock, flow, or parameter..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.pending_input = user_input
    st.session_state.is_thinking = True
    st.rerun()

if st.session_state.is_thinking:
    try:
        guardrail_ctx = (
            "\n".join(st.session_state.guardrail_errors)
            if st.session_state.guardrail_errors
            else None
        )
        response = get_tutor_response(
            chat_history=st.session_state.messages,
            stocks=st.session_state.stocks,
            flows=st.session_state.flows,
            parameters=st.session_state.parameters,
            loops=st.session_state.loops,
            guardrail_error=guardrail_ctx,
        )
    except Exception as e:
        st.session_state.is_thinking = False
        st.error(f"LLM error: {e}")
        st.stop()

    st.session_state.is_thinking = False
    st.session_state.last_response_debug = {
        "scratchpad": response.student_state_analysis,
        "extracted_stocks": [s.model_dump() for s in response.extracted_stocks],
        "extracted_flows": [f.model_dump() for f in response.extracted_flows],
        "extracted_parameters": [p.model_dump() for p in response.extracted_parameters],
        "extracted_loops": [lp.model_dump() for lp in response.extracted_loops],
    }

    st.session_state.guardrail_errors = []

    errors = apply_tutor_response(
        response,
        st.session_state.stocks,
        st.session_state.flows,
        st.session_state.parameters,
        st.session_state.loops,
    )
    if errors:
        st.session_state.guardrail_errors = errors

    st.session_state.messages.append(
        {"role": "assistant", "content": response.message_to_student}
    )

    turn_number = len([m for m in st.session_state.messages if m["role"] == "user"])
    try:
        log_turn(
            session_id=st.session_state.session_id,
            turn_number=turn_number,
            student_input=st.session_state.pending_input or "",
            llm_scratchpad=response.student_state_analysis,
            tutor_response=response.message_to_student,
            extracted_stocks=[s.model_dump() for s in response.extracted_stocks],
            extracted_flows=[f.model_dump() for f in response.extracted_flows],
            extracted_parameters=[p.model_dump() for p in response.extracted_parameters],
            extracted_loops=[lp.model_dump() for lp in response.extracted_loops],
            guardrail_errors=errors,
            snapshot_stocks=list(st.session_state.stocks),
            snapshot_flows=list(st.session_state.flows),
            snapshot_parameters=list(st.session_state.parameters),
            snapshot_loops=list(st.session_state.loops),
        )
        st.session_state.log_error = None
    except Exception as e:
        st.session_state.log_error = str(e)

    st.session_state.pending_input = None
    st.rerun()
