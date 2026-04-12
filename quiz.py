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
