"""Graphviz Stock & Flow diagram renderer for the Flu Dynamics Tutor."""

import re
from typing import Sequence

import graphviz


def render_sfd(
    stocks: Sequence[dict],
    flows: Sequence[dict],
    parameters: Sequence[dict],
    loops: Sequence[dict] | None = None,
) -> graphviz.Digraph:
    """Build a Stock & Flow Diagram from the approved model elements.

    Visual conventions:
      Stocks      → thick-bordered filled rectangle (double box style)
      Flows       → bold coloured arrow; valve shown as a diamond node
      Parameters  → ellipse (constants in blue, auxiliaries in orange)
      Loop labels → plaintext node near centre

    Args:
        stocks:     List of approved stock dicts.
        flows:      List of approved flow dicts.
        parameters: List of approved parameter/auxiliary dicts.
        loops:      List of identified feedback loop dicts (for labels).

    Returns:
        A graphviz.Digraph ready for rendering.
    """
    dot = graphviz.Digraph(
        "SFD",
        format="svg",
        graph_attr={
            "rankdir": "LR",
            "bgcolor": "transparent",
            "fontname": "Helvetica",
            "pad": "0.4",
            "nodesep": "0.6",
            "ranksep": "1.0",
            "size": "12,5!",   # max 12 wide × 5 tall inches; ! = hard constraint
            "ratio": "fill",
        },
    )

    if not stocks and not flows and not parameters:
        dot.node(
            "empty",
            "No elements yet \u2014 start chatting!",
            shape="plaintext",
            fontcolor="#888888",
            fontsize="13",
        )
        return dot

    # ── Pre-compute lookup tables ──────────────────────────────────────────────
    stock_names = {s["name"] for s in stocks}
    param_names = {p["name"] for p in parameters}

    # flow name → valve node id (built during flow rendering below)
    flow_valve_ids: dict[str, str] = {
        f["name"]: f"valve_{i}_{f['name'].replace(' ', '_')}"
        for i, f in enumerate(flows)
    }

    # flows that have at least one parameter feeding into them (equation discussion started)
    flows_with_params: set[str] = {
        target
        for p in parameters
        for target in (p.get("feeds_into") or [])
        if target in flow_valve_ids
    }

    # ── Stocks ─────────────────────────────────────────────────────────────────
    for s in stocks:
        iv = s.get("initial_value")
        label = f'{s["name"]}\n({int(iv) if iv is not None and iv == int(iv) else iv} {s.get("unit", "People")})' if iv is not None else s["name"]
        dot.node(
            s["name"],
            label,
            shape="box",
            style="filled",
            fillcolor="#dbeafe",
            color="#1d4ed8",
            penwidth="3",
            fontname="Helvetica",
            fontsize="11",
            fontcolor="#1e3a5f",
        )

    # ── Flows ──────────────────────────────────────────────────────────────────
    for i, f in enumerate(flows):
        valve_id = f"valve_{i}_{f['name'].replace(' ', '_')}"
        # Valve node — diamond shape represents the flow regulator
        dot.node(
            valve_id,
            f['name'],
            shape="diamond",
            style="filled",
            fillcolor="#fef9c3",
            color="#92400e",
            fontname="Helvetica",
            fontsize="9",
            fontcolor="#451a03",
            width="1.1",
            height="0.5",
        )
        src = f.get("from_stock")
        tgt = f.get("to_stock")
        # Arrow from source stock (or cloud) → valve → target stock (or cloud)
        # Polarity: outflow from stock = "−", inflow to stock = "+"
        if src and src in stock_names:
            dot.edge(
                src, valve_id,
                penwidth="3",
                color="#92400e",
                arrowhead="none",
                label="  −",
                fontcolor="#dc2626",
                fontsize="12",
                fontname="Helvetica Bold",
            )
            # Causal dashed arrow: only once parameters feed into this flow
            if f["name"] in flows_with_params:
                dot.edge(
                    src, valve_id,
                    style="dashed",
                    color="#94a3b8",
                    arrowsize="0.7",
                    penwidth="1.0",
                    label="  +",
                    fontcolor="#16a34a",
                    fontsize="11",
                    fontname="Helvetica Bold",
                    constraint="false",
                )
        else:
            cloud_id = f"cloud_src_{i}"
            dot.node(cloud_id, "☁", shape="plaintext", fontsize="16", fontcolor="#94a3b8")
            dot.edge(cloud_id, valve_id, penwidth="3", color="#92400e", arrowhead="none")

        if tgt and tgt in stock_names:
            dot.edge(
                valve_id, tgt,
                penwidth="3",
                color="#92400e",
                arrowhead="normal",
                arrowsize="1.2",
                label="  +",
                fontcolor="#16a34a",
                fontsize="12",
                fontname="Helvetica Bold",
            )
        else:
            cloud_id = f"cloud_tgt_{i}"
            dot.node(cloud_id, "☁", shape="plaintext", fontsize="16", fontcolor="#94a3b8")
            dot.edge(valve_id, cloud_id, penwidth="3", color="#92400e", arrowhead="normal")

    # ── Parameters / auxiliaries ───────────────────────────────────────────────
    for p in parameters:
        has_eq = bool(p.get("equation"))
        val = p.get("value")
        if has_eq:
            label = f'{p["name"]}\n= {p["equation"]}'
            fill = "#fef3c7"
            border = "#d97706"
        elif val is not None:
            label = f'{p["name"]}\n= {val} {p.get("unit", "")}'
            fill = "#f0fdf4"
            border = "#15803d"
        else:
            label = p["name"]
            fill = "#f8fafc"
            border = "#64748b"

        dot.node(
            p["name"],
            label,
            shape="ellipse",
            style="filled",
            fillcolor=fill,
            color=border,
            fontname="Helvetica",
            fontsize="9",
            fontcolor="#1e293b",
        )

        # Outbound edges: param/auxiliary → flow valves or other auxiliaries
        # Auxiliaries (have an equation) get a "+" polarity label; constants do not
        is_auxiliary = bool(p.get("equation"))
        for target in (p.get("feeds_into") or []):
            dest = flow_valve_ids.get(target, target)
            edge_attrs: dict = dict(
                style="dashed",
                color="#64748b",
                arrowsize="0.7",
                penwidth="1.2",
            )
            if is_auxiliary:
                edge_attrs.update(
                    label="  +",
                    fontcolor="#16a34a",
                    fontsize="11",
                    fontname="Helvetica Bold",
                )
            dot.edge(p["name"], dest, **edge_attrs)

        # Inbound edges: parse equation to find which stocks/params feed INTO this auxiliary
        # All equation inputs get a "+" causal label
        if p.get("equation"):
            tokens = re.split(r"[\s+\-*/()]+", p["equation"])
            for tok in tokens:
                tok = tok.strip()
                if tok and (tok in stock_names or tok in param_names) and tok != p["name"]:
                    dot.edge(
                        tok, p["name"],
                        style="dashed",
                        color="#64748b",
                        arrowsize="0.7",
                        penwidth="1.2",
                        label="  +",
                        fontcolor="#16a34a",
                        fontsize="11",
                        fontname="Helvetica Bold",
                    )

    return dot
