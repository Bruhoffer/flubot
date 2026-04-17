"""Supabase logging via direct PostgreSQL connection (psycopg2)."""

import json
import os
from uuid import uuid4

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

def _get_conn():
    """Open a fresh connection for each operation."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set in .env")
    return psycopg2.connect(url, connect_timeout=5)


def init_session(student_id: str) -> str:
    """Insert a new session row and return the generated session_id (UUID)."""
    session_id = str(uuid4())
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO flu_sessions (id, student_id) VALUES (%s, %s)",
                (session_id, student_id),
            )
        conn.commit()
    finally:
        conn.close()
    return session_id


def get_latest_session(student_id: str) -> dict | None:
    """Return the most recent session row for a student, or None."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, last_active
                FROM flu_sessions
                WHERE student_id = %s
                ORDER BY last_active DESC NULLS LAST
                LIMIT 1
                """,
                (student_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def load_session_state(session_id: str) -> dict:
    """Reconstruct graph state and chat history from a previous session.

    Returns a dict with keys: stocks, flows, parameters, loops, messages.
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT snapshot_stocks, snapshot_flows, snapshot_parameters, snapshot_loops
                FROM flu_turns
                WHERE session_id = %s
                ORDER BY turn_number DESC
                LIMIT 1
                """,
                (session_id,),
            )
            snapshot_row = cur.fetchone()

            cur.execute(
                """
                SELECT student_input, tutor_response
                FROM flu_turns
                WHERE session_id = %s
                ORDER BY turn_number ASC
                """,
                (session_id,),
            )
            turn_rows = cur.fetchall()
    finally:
        conn.close()

    messages: list[dict] = []
    for row in turn_rows:
        messages.append({"role": "user", "content": row["student_input"]})
        messages.append({"role": "assistant", "content": row["tutor_response"]})

    if snapshot_row:
        def _parse(v):
            return json.loads(v) if isinstance(v, str) else (v or [])
        stocks = _parse(snapshot_row["snapshot_stocks"])
        flows = _parse(snapshot_row["snapshot_flows"])
        parameters = _parse(snapshot_row["snapshot_parameters"])
        loops = _parse(snapshot_row["snapshot_loops"])
    else:
        stocks, flows, parameters, loops = [], [], [], []

    return {
        "stocks": stocks,
        "flows": flows,
        "parameters": parameters,
        "loops": loops,
        "messages": messages,
    }


def save_pre_assessment(session_id: str, score: dict, raw_text: str = "") -> None:
    """Persist pre-assessment raw response and score."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flu_sessions SET pre_assessment = %s, pre_assessment_raw = %s WHERE id = %s",
                (json.dumps(score), raw_text, session_id),
            )
        conn.commit()
    finally:
        conn.close()


def save_pre_assessment_raw(session_id: str, raw_text: str) -> None:
    """Persist only the raw pre-assessment text immediately."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flu_sessions SET pre_assessment_raw = %s WHERE id = %s",
                (raw_text, session_id),
            )
        conn.commit()
    finally:
        conn.close()


def save_session_outcome(session_id: str, outcome: dict) -> None:
    """Persist final tutoring outcome to flu_sessions.session_outcome (jsonb)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flu_sessions SET session_outcome = %s WHERE id = %s",
                (json.dumps(outcome), session_id),
            )
        conn.commit()
    finally:
        conn.close()


def save_session_transcript(session_id: str, transcript: str, cld_dot: str) -> None:
    """Persist full chat transcript and diagram DOT source when a session ends."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flu_sessions SET transcript = %s, cld_dot = %s WHERE id = %s",
                (transcript, cld_dot, session_id),
            )
        conn.commit()
    finally:
        conn.close()


def save_quiz_results(session_id: str, results: dict) -> None:
    """Persist post-assessment quiz results to flu_sessions.quiz_results (jsonb)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flu_sessions SET quiz_results = %s WHERE id = %s",
                (json.dumps(results), session_id),
            )
        conn.commit()
    finally:
        conn.close()


def save_bot_results(session_id: str, results: dict) -> None:
    """Persist BOT question results progressively (called after each correct answer).

    results is a dict keyed by question index:
        {0: {question, attempts, correct: True}, ...}
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flu_sessions SET bot_results = %s WHERE id = %s",
                (json.dumps(results), session_id),
            )
        conn.commit()
    finally:
        conn.close()


def save_survey(session_id: str, survey: dict) -> None:
    """Persist post-session survey responses to flu_sessions.survey_results (jsonb).

    Overwrites the entire column each call — safe because callers always pass
    the full accumulated dict from session state.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flu_sessions SET survey_results = %s WHERE id = %s",
                (json.dumps(survey), session_id),
            )
        conn.commit()
    finally:
        conn.close()


# Alias used for progressive per-step saves
save_survey_partial = save_survey


def log_turn(
    session_id: str,
    turn_number: int,
    student_input: str,
    llm_scratchpad: str,
    tutor_response: str,
    extracted_stocks: list,
    extracted_flows: list,
    extracted_parameters: list,
    extracted_loops: list,
    guardrail_errors: list,
    snapshot_stocks: list,
    snapshot_flows: list,
    snapshot_parameters: list,
    snapshot_loops: list,
) -> None:
    """Insert one turn row and update the session's last_active timestamp."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO flu_turns (
                    session_id, turn_number,
                    student_input, llm_scratchpad, tutor_response,
                    extracted_stocks, extracted_flows, extracted_parameters, extracted_loops,
                    guardrail_errors,
                    snapshot_stocks, snapshot_flows, snapshot_parameters, snapshot_loops
                ) VALUES (
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s,
                    %s, %s, %s, %s
                )
                """,
                (
                    session_id,
                    turn_number,
                    student_input,
                    llm_scratchpad,
                    tutor_response,
                    json.dumps(extracted_stocks),
                    json.dumps(extracted_flows),
                    json.dumps(extracted_parameters),
                    json.dumps(extracted_loops),
                    json.dumps(guardrail_errors),
                    json.dumps(snapshot_stocks),
                    json.dumps(snapshot_flows),
                    json.dumps(snapshot_parameters),
                    json.dumps(snapshot_loops),
                ),
            )
            cur.execute(
                "UPDATE flu_sessions SET last_active = now() WHERE id = %s",
                (session_id,),
            )
        conn.commit()
    finally:
        conn.close()
