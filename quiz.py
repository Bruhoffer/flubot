"""'Limits to Growth' archetype quiz for the Flu Dynamics Tutor."""

QUESTIONS: list[dict] = [
    {
        "question": (
            "In a Stock and Flow model, what is the key difference between a **stock** "
            "and a **flow**?"
        ),
        "options": [
            "A stock changes instantly; a flow accumulates over time.",
            "A stock is an accumulation (measured at a point in time); "
            "a flow is a rate of change (measured over a time interval).",
            "A stock and a flow are the same thing — just different names.",
            "A flow is always larger than a stock.",
        ],
        "answer": 1,
        "explanation": (
            "Stocks are the 'bathtubs' of a system — they accumulate and deplete over time "
            "(e.g. SUSCEPTIBLE = 599 people at t=0). Flows are the 'taps and drains' — "
            "rates that fill or empty a stock (e.g. Infection Rate = 20 people/month). "
            "This distinction is fundamental to System Dynamics."
        ),
    },
    {
        "question": (
            "In the RC4 flu model, the **Infection Rate** depends on four quantities. "
            "Which equation correctly captures it?"
        ),
        "options": [
            "Infection Rate = INFECTED × Average contacts × Transmission coefficient",
            "Infection Rate = SUSCEPTIBLE / Recovery duration",
            "Infection Rate = SUSCEPTIBLE × Average contacts × "
            "(INFECTED / Total Population) × Transmission coefficient",
            "Infection Rate = Total Population × Transmission coefficient",
        ],
        "answer": 2,
        "explanation": (
            "The full equation is: SUSCEPTIBLE × Average contacts × "
            "Probability of meeting infected × Transmission coefficient, where "
            "Probability of meeting infected = INFECTED / Total Population. "
            "Notice SUSCEPTIBLE appears, not INFECTED — only healthy people can become newly infected. "
            "The probability term is the auxiliary variable that links the INFECTED stock back "
            "into the infection rate, creating the R1 reinforcing loop."
        ),
    },
    {
        "question": (
            "Why does the number of INFECTED residents eventually **decrease** even "
            "without any external intervention (e.g. no vaccine, no lockdown)?"
        ),
        "options": [
            "The virus mutates and becomes less dangerous over time.",
            "As SUSCEPTIBLE residents are depleted, fewer people are available to infect, "
            "so the Infection Rate slows and Recovery Rate eventually dominates.",
            "The government always intervenes before the epidemic burns out.",
            "Infected residents leave the community before recovering.",
        ],
        "answer": 1,
        "explanation": (
            "This is the B1 balancing loop at work: as SUSCEPTIBLE decreases, the "
            "Probability of meeting infected drops, which reduces the Infection Rate. "
            "Meanwhile, the B2 balancing loop (Recovery Rate) continuously drains INFECTED. "
            "Eventually Recovery Rate > Infection Rate and the epidemic declines. "
            "This self-limiting dynamic is the hallmark of the 'Limits to Growth' archetype."
        ),
    },
    {
        "question": (
            "Which **system archetype** best describes the behaviour of the SIR flu model — "
            "rapid initial epidemic growth that peaks and then declines?"
        ),
        "options": [
            "Fixes that Fail — the intervention creates unintended side-effects.",
            "Escalation — two parties keep outpacing each other.",
            "Limits to Growth — a reinforcing growth loop is eventually constrained "
            "by a balancing loop.",
            "Shifting the Burden — a symptomatic fix weakens the long-term solution.",
        ],
        "answer": 2,
        "explanation": (
            "'Limits to Growth' is defined by: R loop (growth engine) + B loop (constraining "
            "mechanism). Here, R1 drives early epidemic growth (more infected → higher "
            "transmission probability → even more infected). But B1 is the constraint: "
            "as susceptibles are exhausted, the R1 engine loses fuel. The epidemic curve's "
            "bell shape — rapid rise then decline — is the classic Limits to Growth signature."
        ),
    },
    {
        "question": (
            "A public health officer wants to reduce the **peak number of infected residents**. "
            "Based on the model, which lever would be **most effective**?"
        ),
        "options": [
            "Increase the Total Population by allowing more residents into RC4.",
            "Reduce Average contacts (e.g. through social distancing or masks), "
            "which lowers the Infection Rate directly.",
            "Increase Recovery duration so infected residents stay sick longer.",
            "Remove the SUSCEPTIBLE stock from the model.",
        ],
        "answer": 1,
        "explanation": (
            "Average contacts feeds directly into the Infection Rate equation. Halving "
            "contacts (e.g. from 10 to 5 per month) halves the Infection Rate at any given "
            "moment, significantly flattening the epidemic curve. This is exactly why "
            "social distancing, masks, and quarantine work — they reduce the effective "
            "contact rate. Increasing Recovery duration (option C) would make things worse "
            "by keeping people infectious longer."
        ),
    },
]

TOTAL_QUESTIONS = len(QUESTIONS)

# ── Part 2: BOT (Behaviour Over Time) — chat-based ──────────────────────────
# Mirrors STEP 5 in the system prompt. Each question has a reference_answer
# used by the evaluator LLM to judge the student's response.

BOT_QUESTIONS: list[dict] = [
    {
        "question": (
            "Given the structure you've built — the reinforcing loop (R1) and the two "
            "balancing loops (B1, B2) — what kind of **behaviour over time graph** would "
            "you expect for the SUSCEPTIBLE and INFECTED populations?"
        ),
        "reference_answer": (
            "INFECTED follows an S-shaped (sigmoid) curve: it starts near 1, grows "
            "exponentially at first driven by R1, then levels off toward an endemic "
            "equilibrium around 320 people — it does NOT return to zero. "
            "SUSCEPTIBLE follows an inverted S-shape: it starts at 599, drops as people "
            "get infected, and stabilises around 280. The system reaches a new steady "
            "state (endemic equilibrium), not the original starting values."
        ),
        "minimum_criteria": (
            "The student must describe: (1) INFECTED rising then levelling off — an "
            "S-shaped or sigmoid curve, NOT a bell curve that returns to zero; "
            "(2) SUSCEPTIBLE decreasing and stabilising. Mentioning only one population "
            "or describing a bell curve / return-to-zero is insufficient. The key insight "
            "is that the system reaches an endemic equilibrium, not elimination."
        ),
    },
    {
        "question": (
            "Why do you think this behaviour will occur? "
            "Think about which loop dominates at the beginning versus later."
        ),
        "reference_answer": (
            "At the start, R1 dominates: only 1 infected person exists but 599 susceptible, "
            "so each new infection adds another infectious person — exponential growth. "
            "Over time, B1 kicks in: as SUSCEPTIBLE depletes, the probability of meeting "
            "an infected person shrinks, slowing the Infection Rate and weakening R1. "
            "Simultaneously, B2 (Recovery Rate) continuously drains INFECTED. "
            "Eventually Infection Rate equals Recovery Rate — dynamic equilibrium at ~320 "
            "infected. The system does not return to zero because recovery sends people "
            "back to SUSCEPTIBLE (not immune), maintaining ongoing transmission."
        ),
        "minimum_criteria": (
            "The student must explain: (1) R1 dominates early, causing initial rapid growth; "
            "(2) B1 and/or B2 constrain growth over time as susceptibles deplete or "
            "recovery increases; (3) the system stabilises rather than returning to zero. "
            "Mentioning only one loop (e.g. only B1 slowing things down) without explaining "
            "R1's initial dominance is insufficient. The loop dominance SHIFT is the key insight."
        ),
    },
    {
        "question": (
            "Can you relate your behaviour predictions back to the **structure** of the model? "
            "Explain which loops are responsible and what changes over time."
        ),
        "reference_answer": (
            "R1 (INFECTED → Probability of meeting infected → Infection Rate → INFECTED) "
            "drives early exponential growth — a reinforcing loop that amplifies itself. "
            "B1 (SUSCEPTIBLE → Infection Rate → SUSCEPTIBLE decreases) is the growth "
            "constraint: as SUSCEPTIBLE falls, the Infection Rate loses fuel, weakening R1. "
            "B2 (INFECTED → Recovery Rate → INFECTED decreases) is the recovery engine "
            "that continuously drains the infected stock. "
            "The transition to equilibrium happens when B1 + B2 together neutralise R1, "
            "i.e. when Recovery Rate ≈ Infection Rate. This is the 'Limits to Growth' "
            "archetype: reinforcing growth eventually constrained by balancing loops."
        ),
        "minimum_criteria": (
            "The student MUST address all three loops — R1, B1, AND B2 — and explain "
            "the role each plays. Mentioning only one or two loops is NOT sufficient. "
            "Specifically required: (1) R1 causes early growth; (2) B1 constrains growth "
            "via susceptible depletion; (3) B2 drains INFECTED via recovery. "
            "A response that only mentions one balancing loop slowing things down, "
            "without naming R1's role or the other balancing loop, must be marked incorrect "
            "and the student prompted to address the missing loop(s)."
        ),
    },
]

TOTAL_BOT = len(BOT_QUESTIONS)
