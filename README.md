# flubot — AI Socratic Tutor for System Dynamics

An AI-powered Socratic tutor that guides students to construct a **Stock & Flow Diagram (SFD)** for a flu-outbreak SIR model through conversation — then tests their understanding with a quiz and Behaviour Over Time reflection.

Built for the RC4 Junior Seminar at NUS.

---

## What It Does

Students move through five phases:

| Phase | Description |
|-------|-------------|
| **Pre-assessment** | Student describes their initial mental model in free text; automatically scored via LLM extraction |
| **Socratic chat** | Tutor asks guiding questions; responses are parsed to extract stocks, flows, parameters, and feedback loops — building the SFD live |
| **SFD diagram** | Graphviz diagram updates in real time as the student correctly identifies model elements |
| **Simulation** | Once the model is complete, a Plotly chart simulates the epidemic curve (S-shaped "Limits to Growth" pattern) |
| **MCQ quiz** | 4 questions on the "Limits to Growth" archetype |
| **Behaviour Over Time** | Chat-based open-ended questions on how each variable evolves over 6 months |
| **Feedback survey** | Anonymous session rating for research |

All sessions are logged to PostgreSQL — session ID, student ID, per-turn extracted elements, guardrail errors, transcripts, quiz results, and survey responses.

---

## Architecture

```
app.py           Streamlit entry point — phase routing, session state, chat UI
llm.py           OpenAI calls — tutor responses + Behaviour Over Time evaluation
guardrails.py    Validates LLM-proposed SFD elements against known-correct answers
assess.py        Pre/post assessment extraction and scoring (LLM-based)
quiz.py          MCQ and BOT question banks
render.py        Graphviz SFD renderer
models.py        Pydantic models — CASE_STUDY, stock/flow/parameter/loop schemas
logger.py        PostgreSQL logging (init_session, log_turn, save_quiz_results, save_survey)
simulation.py    Numerical SIR model simulation
migrate.sql      Database schema
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit |
| LLM | OpenAI (structured outputs / GPT-4o) |
| Database | PostgreSQL (psycopg2-binary) |
| Diagram | Graphviz |
| Charts | Plotly |
| Deployment | Docker · Heroku (Procfile included) |

---

## Setup

**1. Clone and install**

```bash
git clone https://github.com/Bruhoffer/flubot.git
cd flubot
pip install -r requirements.txt
```

**2. Environment variables** — create a `.env` file:

```env
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

**3. Initialise the database**

```bash
psql $DATABASE_URL -f migrate.sql
```

**4. Run**

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## Docker Deployment

```bash
docker build -t flubot .
docker run -p 8501:8501 \
  -e OPENAI_API_KEY=sk-... \
  -e DATABASE_URL=postgresql://... \
  flubot
```

---

## How the Tutor Works

The LLM acts as a Socratic guide — it asks questions rather than giving answers. It listens for the student to identify:

- **Stocks** — accumulations (Susceptible residents, Infected residents)
- **Flows** — rates of change (Infection Rate, Recovery Rate)
- **Parameters** — drivers (Contact Rate, Infection Probability, Recovery Duration)
- **Loops** — feedback structure (R1 reinforcing growth, B1 susceptible depletion, B2 recovery)

Each response passes through `guardrails.py`, which validates proposed elements before accepting them into the SFD. The tutor adapts to what the student has already identified, and never repeats feedback for confirmed elements.

Session data is persisted to PostgreSQL for downstream research analysis.
