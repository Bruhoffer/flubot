"""Graphviz Stock & Flow diagram renderer for the Flu Dynamics Tutor."""

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

    # ── Stocks ─────────────────────────────────────────────────────────────────
    stock_names = {s["name"] for s in stocks}
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
        if src and src in stock_names:
            dot.edge(
                src, valve_id,
                penwidth="3",
                color="#92400e",
                arrowhead="none",
            )
        else:
            # Source cloud
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

    # ── Loop labels ────────────────────────────────────────────────────────────
    if loops:
        for lp in loops:
            loop_type = lp.get("loop_type", "balancing")
            color = "#16a34a" if loop_type == "reinforcing" else "#dc2626"
            symbol = "R" if loop_type == "reinforcing" else "B"
            dot.node(
                f'loop_{lp["name"]}',
                f'{lp["name"]} ({symbol})',
                shape="plaintext",
                fontcolor=color,
                fontsize="10",
                fontname="Helvetica Bold",
            )

    return dot
