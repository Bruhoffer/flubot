"""Pre-assessment extraction and silent scoring for the Flu Dynamics Tutor."""

import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from models import CASE_STUDY, Flow, FeedbackLoop, Parameter, Stock

load_dotenv()

# ── Reference model ───────────────────────────────────────────────────────────

_REFERENCE_STOCKS: list[tuple[str, frozenset]] = [
    ("SUSCEPTIBLE", frozenset({
        "susceptible", "susceptible population", "healthy", "healthy people",
        "healthy population", "susceptible residents", "healthy residents",
        "non-infected", "uninfected", "uninfected population",
    })),
    ("INFECTED", frozenset({
        "infected", "infected population", "sick", "sick people", "sick residents",
        "infected residents", "ill", "ill population",
    })),
]

_REFERENCE_FLOWS: list[tuple[str, frozenset]] = [
    ("Infection Rate", frozenset({
        "infection rate", "rate of infection", "transmission rate", "spreading rate",
        "new infections", "infection", "infecting rate",
    })),
    ("Recovery Rate", frozenset({
        "recovery rate", "rate of recovery", "recovering rate", "recoveries",
        "recovery", "rate of healing", "healing rate",
    })),
]

_REFERENCE_PARAMETERS: list[tuple[str, frozenset]] = [
    ("Average contacts", frozenset({
        "average contacts", "avg contacts", "contacts per month", "contact rate",
        "number of contacts", "contacts", "average number of contacts",
    })),
    ("Transmission coefficient", frozenset({
        "transmission coefficient", "transmission probability", "infection probability",
        "probability of infection", "transmission rate per contact", "beta",
        "infectivity", "contagion rate",
    })),
    ("Recovery duration", frozenset({
        "recovery duration", "recovery time", "duration of infection",
        "infectious period", "time to recover", "days to recover",
    })),
    ("Total Population", frozenset({
        "total population", "population", "total residents", "community size",
        "n", "population size",
    })),
    ("Probability of meeting infected", frozenset({
        "probability of meeting infected", "probability of contact with infected",
        "chance of meeting infected", "fraction infected", "proportion infected",
        "infected fraction", "i/n", "infected/total",
    })),
]

_REFERENCE_LOOPS: list[tuple[str, frozenset]] = [
    ("R1", frozenset({"infected", "probability of meeting infected", "infection rate"})),
    ("B1", frozenset({"susceptible", "infection rate"})),
    ("B2", frozenset({"infected", "recovery rate"})),
]

TOTAL_REFERENCE_STOCKS = len(_REFERENCE_STOCKS)          # 2
TOTAL_REFERENCE_FLOWS = len(_REFERENCE_FLOWS)            # 2
TOTAL_REFERENCE_PARAMETERS = len(_REFERENCE_PARAMETERS)  # 5
TOTAL_REFERENCE_LOOPS = len(_REFERENCE_LOOPS)            # 3


# ── Extraction schema ─────────────────────────────────────────────────────────

class ExtractionResponse(BaseModel):
    extracted_stocks: list[Stock] = []
    extracted_flows: list[Flow] = []
    extracted_parameters: list[Parameter] = []
    extracted_loops: list[FeedbackLoop] = []


_EXTRACTION_PROMPT = (
    "You are a structured extraction system for a System Dynamics case study.\n"
    "The user will write a free-text description of an SIR flu model.\n"
    "Extract every stock, flow, parameter, and feedback loop they explicitly mention.\n"
    "Be lenient: accept informal names, synonyms, and partial descriptions.\n"
    "Do NOT invent anything not stated by the user.\n\n"
    f"Case study context:\n{CASE_STUDY}"
)


def get_pre_assessment_extraction(student_text: str) -> ExtractionResponse:
    """Call GPT-4o-mini to extract model elements from free-text response."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set.")
    client = OpenAI(api_key=api_key)
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _EXTRACTION_PROMPT},
            {"role": "user", "content": student_text},
        ],
        response_format=ExtractionResponse,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("Extraction returned unparseable response.")
    return parsed


# ── Fuzzy matching helpers ─────────────────────────────────────────────────────

def _match(student_name: str, reference: list[tuple[str, frozenset]]) -> str | None:
    """Return canonical name if student_name matches any reference entry."""
    sv = student_name.strip().lower()
    stops = {"the", "a", "an", "of", "in", "and", "or", "per", "rate", "number"}

    for canonical, forms in reference:
        if sv in forms:
            return canonical
        for form in forms:
            if form in sv or sv in form:
                return canonical
        sv_words = set(sv.split()) - stops
        for form in forms:
            fw = set(form.split()) - stops
            if sv_words and fw:
                overlap = sv_words & fw
                if len(overlap) >= 0.6 * min(len(sv_words), len(fw)):
                    return canonical
    return None


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_assessment(
    stocks: list[dict],
    flows: list[dict],
    parameters: list[dict],
    loops: list[dict],
) -> dict:
    """Compare extracted items against the reference model.

    Returns:
        stocks_found, flows_found, parameters_found, loops_found,
        total_stocks, total_flows, total_parameters, total_loops,
        matched_stocks, matched_flows, matched_parameters, matched_loops
    """
    matched_stocks: set[str] = set()
    for s in stocks:
        c = _match(s.get("name", ""), _REFERENCE_STOCKS)
        if c:
            matched_stocks.add(c)

    matched_flows: set[str] = set()
    for f in flows:
        c = _match(f.get("name", ""), _REFERENCE_FLOWS)
        if c:
            matched_flows.add(c)

    matched_params: set[str] = set()
    for p in parameters:
        c = _match(p.get("name", ""), _REFERENCE_PARAMETERS)
        if c:
            matched_params.add(c)

    matched_loops: set[str] = set()
    for lp in loops:
        seq_set = {v.lower() for v in lp.get("variable_sequence", [])}
        for name, key_vars in _REFERENCE_LOOPS:
            if name not in matched_loops and key_vars.issubset(seq_set):
                matched_loops.add(name)

    return {
        "stocks_found": len(matched_stocks),
        "flows_found": len(matched_flows),
        "parameters_found": len(matched_params),
        "loops_found": len(matched_loops),
        "total_stocks": TOTAL_REFERENCE_STOCKS,
        "total_flows": TOTAL_REFERENCE_FLOWS,
        "total_parameters": TOTAL_REFERENCE_PARAMETERS,
        "total_loops": TOTAL_REFERENCE_LOOPS,
        "matched_stocks": sorted(matched_stocks),
        "matched_flows": sorted(matched_flows),
        "matched_parameters": sorted(matched_params),
        "matched_loops": sorted(matched_loops),
    }
