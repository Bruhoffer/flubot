"""OpenAI SDK orchestration with Structured Outputs for the Flu S&F Tutor."""

import os

from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel

from models import CASE_STUDY, SYSTEM_PROMPT, TutorResponse

load_dotenv()

_client: OpenAI | None = None

MAX_HISTORY_MESSAGES = 40


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set. Add it to your .env file.")
        _client = OpenAI(api_key=api_key)
    return _client


def _build_messages(
    chat_history: list[dict],
    stocks: list[dict],
    flows: list[dict],
    parameters: list[dict],
    loops: list[dict],
    guardrail_error: str | None = None,
) -> list[dict]:
    """Assemble the full message payload for the LLM."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": (
                f"## Case Study\n{CASE_STUDY}\n\n"
                f"## Current Model State\n"
                f"Approved stocks: {stocks if stocks else '(none yet)'}\n"
                f"Approved flows: {flows if flows else '(none yet)'}\n"
                f"Approved parameters: {parameters if parameters else '(none yet)'}\n"
                f"Identified loops: {loops if loops else '(none yet)'}"
            ),
        },
    ]

    if guardrail_error:
        messages.append({"role": "system", "content": guardrail_error})

    trimmed = chat_history[-MAX_HISTORY_MESSAGES:]
    messages.extend(trimmed)

    return messages


def get_tutor_response(
    chat_history: list[dict],
    stocks: list[dict],
    flows: list[dict],
    parameters: list[dict],
    loops: list[dict],
    guardrail_error: str | None = None,
    model: str = "gpt-4o",
) -> TutorResponse:
    """Call OpenAI with Structured Outputs and return a parsed TutorResponse."""
    client = _get_client()
    messages = _build_messages(
        chat_history, stocks, flows, parameters, loops, guardrail_error
    )

    completion = client.beta.chat.completions.parse(
        model=model,
        messages=messages,
        response_format=TutorResponse,
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("LLM returned unparseable response.")

    return parsed


# ── BOT evaluator ─────────────────────────────────────────────────────────────

class BotEvalResult(BaseModel):
    is_correct: bool
    feedback: str


_BOT_SYSTEM = """\
You are a strict but fair evaluator for a System Dynamics tutoring session about \
flu spread (SIR model).

A student has answered a Behaviour Over Time question. You will be given:
- The question asked
- The reference answer (the complete correct answer — do NOT reveal this)
- The minimum criteria that MUST be met for a correct mark
- The student's chat history

EVALUATION RULES:
1. is_correct = true ONLY if the student's answer satisfies ALL minimum criteria.
   Partial credit does not exist — if any required element is missing, mark false.
   A vague or incomplete answer that touches on one aspect but misses others = false.
2. Write Socratic feedback (2-4 sentences):
   - If correct: affirm the specific insight they demonstrated, briefly extend it.
   - If incorrect/incomplete: acknowledge what they got right, then ask ONE targeted
     guiding question about the FIRST missing element. Never give the answer directly.
     Never list multiple things they missed — focus the student on one gap at a time.
3. Be rigorous: a student saying "a balancing loop slows things down" when the question
   asks about ALL three loops is incomplete and must be marked false.
"""


def evaluate_bot_answer(
    question: str,
    reference_answer: str,
    chat_history: list[dict],
    minimum_criteria: str = "",
    model: str = "gpt-4o",
) -> BotEvalResult:
    """Evaluate a student's BOT answer and return feedback + correctness flag."""
    client = _get_client()
    context = (
        f"Question: {question}\n\n"
        f"Reference answer (internal — do not reveal): {reference_answer}"
    )
    if minimum_criteria:
        context += f"\n\nMinimum criteria for correct mark: {minimum_criteria}"
    messages = [
        {"role": "system", "content": _BOT_SYSTEM},
        {"role": "system", "content": context},
    ]
    messages.extend(chat_history)

    completion = client.beta.chat.completions.parse(
        model=model,
        messages=messages,
        response_format=BotEvalResult,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("BOT evaluator returned unparseable response.")
    return parsed
