"""Bioreactor kinetics simulation using Monod growth model + metal extraction.

Uses SciPy ODE solver for bacterial/fungal growth curves and metal dissolution
kinetics. Each vat is modeled independently with its own organism and conditions.

This module can run standalone for batch analysis or be called by the sim engine
for real-time bioreactor state during the 3D simulation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

try:
    from scipy.integrate import solve_ivp
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


@dataclass
class MonodParams:
    """Monod growth kinetics parameters for a microbial culture."""
    mu_max: float       # Maximum specific growth rate (1/hour)
    ks: float           # Half-saturation constant (g/L)
    yield_xs: float     # Biomass yield on substrate (g biomass / g substrate)
    maintenance: float  # Maintenance coefficient (g substrate / g biomass / hour)


@dataclass
class VatState:
    """State of a single bioreactor vat at a point in time."""
    biomass_g_per_l: float = 0.1     # Initial inoculum concentration
    substrate_g_per_l: float = 10.0  # Available substrate (metal ore in slurry)
    metal_dissolved_g_per_l: float = 0.0
    ph: float = 2.0
    temp_c: float = 30.0
    volume_liters: float = 200.0
    time_hours: float = 0.0


@dataclass
class VatConfig:
    """Configuration for a bioreactor vat."""
    name: str
    volume_liters: float
    organism: str
    monod: MonodParams
    optimal_ph: float
    optimal_temp_c: float
    ph_range: tuple[float, float]
    temp_range: tuple[float, float]
    metal_extraction_rate: float     # g metal / g biomass / hour
    target_metals: list[str]
    extraction_efficiency: float     # 0-1


# Pre-configured vats from the catalog species data
VAT_SULFIDE = VatConfig(
    name="Sulfide Metals (Cu, Ni, Co)",
    volume_liters=200,
    organism="Acidithiobacillus ferrooxidans + thiooxidans",
    monod=MonodParams(mu_max=0.065, ks=0.5, yield_xs=0.15, maintenance=0.01),
    optimal_ph=2.0,
    optimal_temp_c=30,
    ph_range=(1.5, 3.0),
    temp_range=(25, 35),
    metal_extraction_rate=0.005,  # g metal per g biomass per hour
    target_metals=["copper", "nickel", "cobalt", "zinc"],
    extraction_efficiency=0.85,
)

VAT_REE = VatConfig(
    name="Rare Earth Elements",
    volume_liters=100,
    organism="Aspergillus niger",
    monod=MonodParams(mu_max=0.087, ks=1.0, yield_xs=0.30, maintenance=0.005),
    optimal_ph=4.0,
    optimal_temp_c=28,
    ph_range=(3.0, 5.0),
    temp_range=(25, 30),
    metal_extraction_rate=0.002,
    target_metals=["lanthanum", "cerium", "neodymium", "yttrium"],
    extraction_efficiency=0.60,
)

VAT_PGM = VatConfig(
    name="Platinum Group Metals",
    volume_liters=50,
    organism="Chromobacterium violaceum",
    monod=MonodParams(mu_max=0.17, ks=0.3, yield_xs=0.25, maintenance=0.008),
    optimal_ph=7.5,
    optimal_temp_c=28,
    ph_range=(7.0, 9.0),
    temp_range=(25, 30),
    metal_extraction_rate=0.001,  # Slowest — PGM bioleaching is immature
    target_metals=["platinum", "palladium", "iridium"],
    extraction_efficiency=0.40,
)


def _ph_temp_factor(state: VatState, config: VatConfig) -> float:
    """Growth rate modifier based on pH and temperature deviation from optimal.

    Returns 1.0 at optimal conditions, drops toward 0 at range boundaries,
    and returns 0 (culture death) outside the viable range.
    """
    # pH factor (Gaussian-like around optimal)
    ph_min, ph_max = config.ph_range
    if state.ph < ph_min or state.ph > ph_max:
        return 0.0  # Culture crash outside viable range
    ph_dev = abs(state.ph - config.optimal_ph) / (ph_max - ph_min)
    ph_factor = math.exp(-4 * ph_dev ** 2)

    # Temperature factor
    t_min, t_max = config.temp_range
    if state.temp_c < t_min or state.temp_c > t_max:
        return 0.0
    t_dev = abs(state.temp_c - config.optimal_temp_c) / (t_max - t_min)
    temp_factor = math.exp(-4 * t_dev ** 2)

    return ph_factor * temp_factor


def _ode_system(t: float, y: list[float], config: VatConfig,
                state_template: VatState) -> list[float]:
    """ODE system for Monod growth + metal extraction.

    y = [biomass_g_per_l, substrate_g_per_l, metal_dissolved_g_per_l]
    """
    X, S, M = y
    X = max(0, X)
    S = max(0, S)

    monod = config.monod
    env = _ph_temp_factor(state_template, config)

    # Monod growth rate
    if S > 0:
        mu = monod.mu_max * (S / (monod.ks + S)) * env
    else:
        mu = 0.0

    # Biomass growth
    dX = mu * X

    # Substrate consumption (growth + maintenance)
    dS = -(mu * X / monod.yield_xs) - (monod.maintenance * X)
    dS = min(0, dS)  # Can only decrease

    # Metal extraction (proportional to active biomass)
    dM = config.metal_extraction_rate * X * env

    return [dX, dS, dM]


def simulate_vat(config: VatConfig, state: VatState,
                 duration_hours: float = 24.0,
                 dt_hours: float = 1.0) -> list[VatState]:
    """Simulate a bioreactor vat over time.

    Returns a list of VatState snapshots at each timestep.
    """
    if HAS_SCIPY:
        return _simulate_scipy(config, state, duration_hours, dt_hours)
    else:
        return _simulate_euler(config, state, duration_hours, dt_hours)


def _simulate_scipy(config, state, duration_hours, dt_hours):
    """ODE integration using SciPy."""
    t_span = (0, duration_hours)
    t_eval = [i * dt_hours for i in range(int(duration_hours / dt_hours) + 1)]
    y0 = [state.biomass_g_per_l, state.substrate_g_per_l, state.metal_dissolved_g_per_l]

    sol = solve_ivp(
        _ode_system, t_span, y0,
        args=(config, state),
        t_eval=t_eval,
        method="RK45",
        max_step=dt_hours,
    )

    results = []
    for i in range(len(sol.t)):
        results.append(VatState(
            biomass_g_per_l=max(0, sol.y[0][i]),
            substrate_g_per_l=max(0, sol.y[1][i]),
            metal_dissolved_g_per_l=max(0, sol.y[2][i]),
            ph=state.ph,
            temp_c=state.temp_c,
            volume_liters=state.volume_liters,
            time_hours=state.time_hours + sol.t[i],
        ))
    return results


def _simulate_euler(config, state, duration_hours, dt_hours):
    """Simple Euler integration fallback (no SciPy dependency)."""
    results = []
    X = state.biomass_g_per_l
    S = state.substrate_g_per_l
    M = state.metal_dissolved_g_per_l
    t = 0.0

    while t <= duration_hours:
        results.append(VatState(
            biomass_g_per_l=X, substrate_g_per_l=S, metal_dissolved_g_per_l=M,
            ph=state.ph, temp_c=state.temp_c, volume_liters=state.volume_liters,
            time_hours=state.time_hours + t,
        ))
        dX, dS, dM = _ode_system(t, [X, S, M], config, state)
        X = max(0, X + dX * dt_hours)
        S = max(0, S + dS * dt_hours)
        M = max(0, M + dM * dt_hours)
        t += dt_hours

    return results


def format_vat_report(config: VatConfig, results: list[VatState]) -> str:
    """Format a vat simulation report."""
    lines = []
    lines.append(f"{'=' * 60}")
    lines.append(f"BIOREACTOR SIMULATION: {config.name}")
    lines.append(f"Organism: {config.organism}")
    lines.append(f"Volume: {config.volume_liters}L | pH: {config.optimal_ph} | Temp: {config.optimal_temp_c}C")
    lines.append(f"{'=' * 60}")

    lines.append(f"\n{'Hour':>6s} {'Biomass':>10s} {'Substrate':>10s} {'Metal':>10s}")
    lines.append(f"{'':>6s} {'(g/L)':>10s} {'(g/L)':>10s} {'(g/L)':>10s}")
    lines.append("-" * 40)

    # Show every 24 hours
    for s in results:
        relative_h = s.time_hours - results[0].time_hours
        if relative_h % 24 < 1.0 or s == results[-1]:
            lines.append(f"{relative_h:6.0f} {s.biomass_g_per_l:10.3f} "
                         f"{s.substrate_g_per_l:10.3f} {s.metal_dissolved_g_per_l:10.3f}")

    final = results[-1]
    total_metal_g = final.metal_dissolved_g_per_l * config.volume_liters
    lines.append(f"\n--- RESULTS ---")
    lines.append(f"  Duration: {final.time_hours - results[0].time_hours:.0f} hours")
    lines.append(f"  Final biomass: {final.biomass_g_per_l:.3f} g/L")
    lines.append(f"  Substrate remaining: {final.substrate_g_per_l:.3f} g/L")
    lines.append(f"  Metal dissolved: {final.metal_dissolved_g_per_l:.3f} g/L")
    lines.append(f"  Total metal extracted: {total_metal_g:.1f} g ({total_metal_g/1000:.3f} kg)")
    lines.append(f"  Targets: {', '.join(config.target_metals)}")
    lines.append(f"{'=' * 60}")
    return "\n".join(lines)
