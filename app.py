"""Flu Dynamics S&F Tutor — Streamlit entry point."""

import html as html_lib
import threading

import plotly.graph_objects as go
import streamlit as st

from assess import get_pre_assessment_extraction, score_assessment
from guardrails import apply_tutor_response
from llm import get_tutor_response
from logger import (
    get_latest_session,
    init_session,
    load_session_state,
    log_turn,
    save_pre_assessment,
    save_pre_assessment_raw,
    save_quiz_results,
    save_session_outcome,
    save_session_transcript,
)
from models import CASE_STUDY
from quiz import QUESTIONS, TOTAL_QUESTIONS
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
        display: flex;
        align-items: center;
        gap: 18px;
        background: #1e293b;
        color: #e2e8f0;
        border-radius: 8px;
        padding: 7px 16px;
        font-size: 0.8rem;
        margin-bottom: 10px;
        flex-wrap: wrap;
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
        font-size: 0.81rem;
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
    "_pending_student_id": None,
    "resume_candidate": None,
    "phase": "pre_assessment",
    "quiz_question_idx": 0,
    "quiz_answers": {},
    "quiz_saved": False,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Student ID gate ───────────────────────────────────────────────────────────
if not st.session_state.student_id or not st.session_state.session_id:
    st.title("Flu Dynamics S&F Tutor")

    if st.session_state.resume_candidate is None:
        st.markdown("Enter your student ID to begin.")
        with st.form("student_id_form"):
            sid = st.text_input("Student ID (e.g. A0123456X)")
            submitted = st.form_submit_button("Start Session")
        if submitted and sid.strip():
            try:
                candidate = get_latest_session(sid.strip())
                st.session_state._pending_student_id = sid.strip()
                if candidate:
                    st.session_state.resume_candidate = candidate
                else:
                    session_id = init_session(sid.strip())
                    st.session_state.student_id = sid.strip()
                    st.session_state.session_id = session_id
                    st.session_state.resume_candidate = False
                st.rerun()
            except Exception as e:
                st.error(f"Could not connect to database: {e}")

    elif isinstance(st.session_state.resume_candidate, dict):
        candidate = st.session_state.resume_candidate
        sid = st.session_state._pending_student_id
        last_seen = candidate.get("last_active")
        last_seen_str = str(last_seen)[:16] if last_seen else "unknown"
        st.info(f"A previous session was found for **{sid}** (last active: {last_seen_str}).")
        col_r, col_n = st.columns(2)
        with col_r:
            if st.button("Resume last session", type="primary", use_container_width=True):
                try:
                    state = load_session_state(candidate["id"])
                    st.session_state.student_id = sid
                    st.session_state.session_id = candidate["id"]
                    st.session_state.messages = state["messages"]
                    st.session_state.stocks = state["stocks"]
                    st.session_state.flows = state["flows"]
                    st.session_state.parameters = state["parameters"]
                    st.session_state.loops = state["loops"]
                    st.session_state.resume_candidate = False
                    st.session_state.phase = "tutoring"
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not load session: {e}")
        with col_n:
            if st.button("Start new session", use_container_width=True):
                try:
                    session_id = init_session(sid)
                    st.session_state.student_id = sid
                    st.session_state.session_id = session_id
                    st.session_state.resume_candidate = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not start new session: {e}")

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
if st.session_state.phase == "quiz":
    st.title("What did we learn? — The 'Limits to Growth' Archetype")

    idx = st.session_state.quiz_question_idx

    if idx >= TOTAL_QUESTIONS:
        correct = sum(
            1
            for q_idx, ans in st.session_state.quiz_answers.items()
            if ans == QUESTIONS[q_idx]["answer"]
        )

        if not st.session_state.quiz_saved:
            try:
                answer_log = [
                    {
                        "question": QUESTIONS[q_idx]["question"],
                        "selected": QUESTIONS[q_idx]["options"][ans],
                        "correct_answer": QUESTIONS[q_idx]["options"][QUESTIONS[q_idx]["answer"]],
                        "is_correct": ans == QUESTIONS[q_idx]["answer"],
                    }
                    for q_idx, ans in st.session_state.quiz_answers.items()
                ]
                save_quiz_results(
                    st.session_state.session_id,
                    {"score": correct, "total": TOTAL_QUESTIONS, "answers": answer_log},
                )
                st.session_state.quiz_saved = True
            except Exception:
                pass

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

        if st.button("← Return to my diagram", type="primary"):
            st.session_state.phase = "tutoring"
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
            st.session_state.quiz_answers[idx] = q["options"].index(selected)
            st.rerun()
    else:
        student_ans = st.session_state.quiz_answers[idx]
        correct_ans = q["answer"]
        if student_ans == correct_ans:
            st.success("Correct! ✓")
        else:
            st.error(f"Not quite. The correct answer: **{q['options'][correct_ans]}**")
        st.info(f"**Why:** {q['explanation']}")

        label = "Next question →" if idx < TOTAL_QUESTIONS - 1 else "See results →"
        if st.button(label, type="primary"):
            st.session_state.quiz_question_idx += 1
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
info_left, info_right = st.columns([5, 1])
with info_left:
    short_session = str(st.session_state.session_id)[:8] + "..."
    safe_sid = html_lib.escape(st.session_state.student_id)
    safe_log_error = html_lib.escape(str(st.session_state.log_error)) if st.session_state.log_error else ""
    st.markdown(
        f'<div class="top-bar">'
        f'<span><span class="label">Student</span>'
        f'<span class="value">{safe_sid}</span></span>'
        f'<span><span class="label">Session</span>'
        f'<span class="tag">{short_session}</span></span>'
        + (f'<span style="color:#f87171;font-size:0.75rem">⚠ Logging error: {safe_log_error}</span>'
           if safe_log_error else '')
        + '</div>',
        unsafe_allow_html=True,
    )
with info_right:
    btn_finish, btn_reset = st.columns(2)
    with btn_finish:
        if st.button("Finish →", use_container_width=True,
                     help="End session and go to the archetype quiz"):
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
            st.session_state.phase = "quiz"
            st.rerun()
    with btn_reset:
        if st.button("Reset", type="primary", use_container_width=True):
            for key in ["messages", "stocks", "flows", "parameters", "loops", "guardrail_errors"]:
                st.session_state[key] = []
            st.session_state.session_id = None
            st.session_state.student_id = None
            st.session_state.phase = "pre_assessment"
            st.session_state.quiz_question_idx = 0
            st.session_state.quiz_answers = {}
            st.session_state.quiz_saved = False
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
                "Notice the bell-curve shape — rapid growth (R1) then decline as "
                "susceptibles are exhausted (B1). This is 'Limits to Growth'."
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
    if st.session_state.stocks:
        for s in st.session_state.stocks:
            iv = s.get("initial_value")
            iv_str = f" = {int(iv)}" if iv is not None else ""
            stocks_html += (
                f'<div style="font-size:0.8rem;padding:3px 0;'
                f'border-bottom:1px solid #e2e8f020;color:#e2e8f0">'
                f'<b style="color:#93c5fd">{html_lib.escape(s["name"])}</b>'
                f'{html_lib.escape(iv_str)} {html_lib.escape(s.get("unit","People"))}</div>'
            )
    else:
        stocks_html = '<div style="font-size:0.78rem;color:#64748b">No stocks identified yet.</div>'

    flows_html = ""
    if st.session_state.flows:
        for f in st.session_state.flows:
            src = html_lib.escape(f.get("from_stock") or "☁")
            tgt = html_lib.escape(f.get("to_stock") or "☁")
            flows_html += (
                f'<div style="font-size:0.78rem;padding:3px 0;'
                f'border-bottom:1px solid #e2e8f020;color:#e2e8f0">'
                f'<b style="color:#fbbf24">{html_lib.escape(f["name"])}</b> '
                f'<span style="color:#64748b;font-size:0.72rem">{src} → {tgt}</span></div>'
            )
    else:
        flows_html = '<div style="font-size:0.78rem;color:#64748b">No flows identified yet.</div>'

    params_html = ""
    if st.session_state.parameters:
        for p in st.session_state.parameters:
            val = p.get("value")
            eq = p.get("equation")
            detail = f" = {val}" if val is not None else (f" = {eq}" if eq else "")
            params_html += (
                f'<div style="font-size:0.78rem;padding:3px 0;'
                f'border-bottom:1px solid #e2e8f020;color:#e2e8f0">'
                f'· {html_lib.escape(p["name"])}'
                f'<span style="color:#64748b">{html_lib.escape(detail)}</span></div>'
            )
    else:
        params_html = '<div style="font-size:0.78rem;color:#64748b">No parameters identified yet.</div>'

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
                f'<span style="font-weight:700;color:{color};font-size:0.82rem">{name}</span> '
                f'<span style="font-size:0.74rem;color:#64748b">({loop_type})</span><br>'
                f'<span style="font-size:0.74rem;line-height:1.6;color:#cbd5e1">{path}</span>'
                f'</div>'
            )
    else:
        loops_html = '<div style="font-size:0.78rem;color:#64748b">No loops identified yet.</div>'

    st.markdown(
        f'<div class="info-scroll">'
        f'<div style="font-size:0.7rem;font-weight:700;letter-spacing:0.06em;'
        f'color:#93c5fd;text-transform:uppercase;margin-bottom:6px">Stocks</div>'
        f'{stocks_html}'
        f'<div style="margin:10px 0 6px;font-size:0.7rem;font-weight:700;'
        f'letter-spacing:0.06em;color:#fbbf24;text-transform:uppercase">Flows</div>'
        f'{flows_html}'
        f'<div style="margin:10px 0 6px;font-size:0.7rem;font-weight:700;'
        f'letter-spacing:0.06em;color:#86efac;text-transform:uppercase">Parameters</div>'
        f'{params_html}'
        f'<div style="margin:10px 0 6px;font-size:0.7rem;font-weight:700;'
        f'letter-spacing:0.06em;color:#60a5fa;text-transform:uppercase">Feedback Loops</div>'
        f'{loops_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.divider()
    with st.expander("Debug: last LLM extraction", expanded=False):
        if st.session_state.last_response_debug:
            d = st.session_state.last_response_debug
            st.markdown("**Scratchpad:**")
            st.caption(d["scratchpad"])
            st.markdown(f"**stocks:** `{d['extracted_stocks']}`")
            st.markdown(f"**flows:** `{d['extracted_flows']}`")
            st.markdown(f"**parameters:** `{d['extracted_parameters']}`")
            st.markdown(f"**loops:** `{d['extracted_loops']}`")
        else:
            st.caption("No response yet.")

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
