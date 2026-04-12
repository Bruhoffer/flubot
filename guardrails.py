"""Application-level guardrails for Stock & Flow model state validation."""

from models import Flow, FeedbackLoop, Parameter, Stock, TutorResponse

# Canonical loop names — first match wins
_CANONICAL_LOOPS: list[tuple[str, str, set[str]]] = [
    ("R1", "reinforcing", {
        "infected", "probability of meeting infected", "infection rate",
    }),
    ("B1", "balancing", {
        "susceptible", "infected", "infection rate",
    }),
    ("B2", "balancing", {
        "infected", "recovery rate",
    }),
]


def _canonical_loop_name(loop: FeedbackLoop, existing_loops: list[dict]) -> str:
    """Return the canonical label (R1, B1, B2) for a loop, or next available."""
    used_names = {lp.get("name", "").upper() for lp in existing_loops}
    seq_set = {v.lower() for v in loop.variable_sequence}

    for name, _, key_vars in _CANONICAL_LOOPS:
        if name in used_names:
            continue
        if key_vars.issubset(seq_set):
            return name

    prefix = "R" if loop.loop_type == "reinforcing" else "B"
    n = 1
    while f"{prefix}{n}" in used_names:
        n += 1
    return f"{prefix}{n}"


def _name_exists(name: str, existing: list[dict]) -> bool:
    return name.strip().lower() in {e.get("name", "").lower() for e in existing}


def apply_tutor_response(
    response: TutorResponse,
    stocks: list[dict],
    flows: list[dict],
    parameters: list[dict],
    loops: list[dict],
) -> list[str]:
    """Apply a validated TutorResponse to the model state. Mutates lists in-place.

    Returns a list of error messages (empty if all extractions succeeded).
    """
    errors: list[str] = []

    # Stocks
    for stock in response.extracted_stocks:
        if _name_exists(stock.name, stocks):
            errors.append(
                f"Error: Stock '{stock.name}' already exists. Acknowledge and move on."
            )
        else:
            stocks.append(stock.model_dump())

    # Flows — from_stock/to_stock must reference approved stocks (or None for clouds)
    stock_names = {s["name"].lower() for s in stocks}
    for flow in response.extracted_flows:
        if _name_exists(flow.name, flows):
            errors.append(
                f"Error: Flow '{flow.name}' already exists. Acknowledge and move on."
            )
            continue
        missing = []
        if flow.from_stock and flow.from_stock.lower() not in stock_names:
            missing.append(flow.from_stock)
        if flow.to_stock and flow.to_stock.lower() not in stock_names:
            missing.append(flow.to_stock)
        if missing:
            errors.append(
                f"Error: Flow '{flow.name}' references undefined stock(s): "
                f"{', '.join(missing)}. The stocks must be approved first."
            )
        else:
            flows.append(flow.model_dump())

    # Parameters / auxiliary variables
    for param in response.extracted_parameters:
        if _name_exists(param.name, parameters):
            errors.append(
                f"Error: Parameter '{param.name}' already exists. Acknowledge and move on."
            )
        else:
            parameters.append(param.model_dump())

    # Feedback loops
    all_names = (
        {s["name"].lower() for s in stocks}
        | {f["name"].lower() for f in flows}
        | {p["name"].lower() for p in parameters}
    )
    for loop in response.extracted_loops:
        loop = loop.model_copy(update={"loop_type": loop.loop_type.lower()})

        # Strip closing duplicate
        seq = loop.variable_sequence
        if len(seq) > 1 and seq[-1].lower() == seq[0].lower():
            loop = loop.model_copy(update={"variable_sequence": seq[:-1]})

        if any(lp.get("name", "").lower() == loop.name.lower() for lp in loops):
            errors.append(f"Error: Loop '{loop.name}' already exists.")
            continue

        missing_vars = [v for v in loop.variable_sequence if v.lower() not in all_names]
        if missing_vars:
            errors.append(
                f"Error: Loop references unknown element(s): {', '.join(missing_vars)}. "
                "They must be approved first."
            )
            continue

        canonical_name = _canonical_loop_name(loop, loops)
        loop = loop.model_copy(update={"name": canonical_name})
        loops.append(loop.model_dump())

    return errors
