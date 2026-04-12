"""Euler integration of the SIR flu model (simplified — no permanent Recovered state).

Recovery returns individuals to Susceptible, matching the case study equations exactly:
  Infection Rate = S × c × (I/N) × β
  Recovery Rate  = I / τ
  dS/dt = -Infection Rate + Recovery Rate
  dI/dt = +Infection Rate - Recovery Rate
"""

from __future__ import annotations


# ── Default parameters (from the activity sheet) ────────────────────────────
_S0 = 599        # initial susceptible
_I0 = 1          # initial infected
_N  = 600        # total population (constant)
_c  = 10         # avg contacts per month
_β  = 0.65       # transmission coefficient per contact
_τ  = 1 / 3      # recovery duration in months (~9 days ≈ 0.33 months)


def simulate(
    months: float = 6.0,
    dt: float = 0.05,
    s0: float = _S0,
    i0: float = _I0,
    total_population: float = _N,
    avg_contacts: float = _c,
    transmission_coeff: float = _β,
    recovery_duration: float = _τ,
) -> dict[str, list[float]]:
    """Run Euler integration and return time series.

    Returns:
        {
          "t":           list of time points (months),
          "susceptible": list of S values,
          "infected":    list of I values,
        }
    """
    t_series: list[float] = []
    s_series: list[float] = []
    i_series: list[float] = []

    S = float(s0)
    I = float(i0)
    t = 0.0
    steps = round(months / dt)

    for _ in range(steps + 1):
        t_series.append(round(t, 4))
        s_series.append(round(S, 4))
        i_series.append(round(I, 4))

        prob_meeting = I / total_population
        infection_rate = S * avg_contacts * prob_meeting * transmission_coeff
        recovery_rate = I / recovery_duration

        S_new = S + dt * (-infection_rate + recovery_rate)
        I_new = I + dt * (infection_rate - recovery_rate)

        # Clamp to valid range
        S = max(0.0, min(S_new, total_population))
        I = max(0.0, min(I_new, total_population))
        t += dt

    return {"t": t_series, "susceptible": s_series, "infected": i_series}


def peak_infected(sim: dict[str, list[float]]) -> tuple[float, float]:
    """Return (peak_infected_count, time_of_peak_in_months)."""
    infected = sim["infected"]
    idx = infected.index(max(infected))
    return round(infected[idx], 1), round(sim["t"][idx], 2)
