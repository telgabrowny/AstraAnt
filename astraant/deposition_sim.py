"""Zero-gravity patterned electrodeposition & electroforming simulator.

Models patterned metal deposition from electrolyte solution, analogous to
masked stereolithography (MSLA/DLP 3D printing) but using electric current
instead of UV light.  Also supports electroforming in shaped pools (I-beam,
channel cross-sections) for structural part fabrication.

Physics modeled:
  - Electric potential: Laplace equation (sparse direct solve, Jacobi fallback)
  - Ion transport: Fick's diffusion (0g) + convective mixing model (1g)
  - Deposition rate: Faraday's law with concentration-dependent current
  - Electrode kinetics: optional Butler-Volmer (secondary current distribution)
  - Pattern: configurable electrode mask (active/inactive regions)
  - Geometry: arbitrary 2D cross-sections via boolean mask (I-beam, channel)
  - Forced convection: optional bulk flow velocity for pumped electrolyte
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve as sp_solve
    HAS_SCIPY_SPARSE = True
except ImportError:
    HAS_SCIPY_SPARSE = False


# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
FARADAY = 96485.3329            # C/mol
R_GAS = 8.31446                 # J/(mol*K)
NU_WATER = 1.0e-6               # m^2/s, kinematic viscosity of water at 25C
BETA_SOLUTAL = 1.6e-4           # m^3/mol, solutal expansion coeff (CuSO4)


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------
@dataclass
class ElectrolyteConfig:
    """Metal ion electrolyte properties for electrodeposition."""
    metal: str
    diffusivity_m2_s: float          # D, ion diffusion coefficient
    charge_number: int               # n, electrons transferred per ion
    molar_mass_kg_mol: float         # M, molar mass of deposited metal
    density_solid_kg_m3: float       # rho, density of solid metal deposit
    bulk_concentration_mol_m3: float # C0, initial/bulk ion concentration
    conductivity_s_m: float          # kappa, electrolyte ionic conductivity


# Pre-configured electrolytes matching bioreactor leachate metals
COPPER_SULFATE = ElectrolyteConfig(
    metal="copper",
    diffusivity_m2_s=7.2e-10,
    charge_number=2,
    molar_mass_kg_mol=0.06355,
    density_solid_kg_m3=8960.0,
    bulk_concentration_mol_m3=100.0,
    conductivity_s_m=5.0,
)

NICKEL_SULFATE = ElectrolyteConfig(
    metal="nickel",
    diffusivity_m2_s=6.6e-10,
    charge_number=2,
    molar_mass_kg_mol=0.05869,
    density_solid_kg_m3=8908.0,
    bulk_concentration_mol_m3=100.0,
    conductivity_s_m=4.5,
)

IRON_SULFATE = ElectrolyteConfig(
    metal="iron",
    diffusivity_m2_s=7.2e-10,
    charge_number=2,
    molar_mass_kg_mol=0.05585,
    density_solid_kg_m3=7874.0,
    bulk_concentration_mol_m3=100.0,
    conductivity_s_m=5.0,
)


@dataclass
class ElectrodeKinetics:
    """Butler-Volmer electrode kinetics for secondary current distribution.

    Higher j0 = faster kinetics = closer to primary distribution.
    Lower j0 = more activation resistance = more uniform current.
    """
    j0_a_m2: float           # exchange current density (A/m^2)
    alpha_a: float = 0.5     # anodic transfer coefficient
    alpha_c: float = 0.5     # cathodic transfer coefficient


COPPER_KINETICS = ElectrodeKinetics(j0_a_m2=3.0)
NICKEL_KINETICS = ElectrodeKinetics(j0_a_m2=0.5)
IRON_KINETICS = ElectrodeKinetics(j0_a_m2=1.0)


@dataclass
class DepositionConfig:
    """Simulation domain geometry and operating parameters."""
    width_mm: float = 20.0          # electrode array width
    gap_mm: float = 5.0             # electrode-to-cathode distance
    nx: int = 100                   # grid points in x (lateral)
    nz: int = 50                    # grid points in z (gap direction)

    voltage_v: float = 0.5          # applied cell voltage
    temperature_k: float = 298.15   # 25C
    duration_s: float = 3600.0      # total simulation time
    dt_s: float = 0.1               # timestep (must satisfy CFL for diffusion)
    snapshot_interval_s: float = 300.0  # save state every N seconds

    # Electrode pattern: list of (start_frac, end_frac) active regions.
    pattern: list[tuple[float, float]] = field(default_factory=lambda: [
        (0.10, 0.30), (0.40, 0.60), (0.70, 0.90),
    ])

    gravity_m_s2: float = 0.0       # 0 = microgravity, 9.81 = Earth

    @property
    def dx(self) -> float:
        return (self.width_mm / 1000.0) / max(self.nx - 1, 1)

    @property
    def dz(self) -> float:
        return (self.gap_mm / 1000.0) / max(self.nz - 1, 1)

    @property
    def width_m(self) -> float:
        return self.width_mm / 1000.0

    @property
    def gap_m(self) -> float:
        return self.gap_mm / 1000.0

    def electrode_mask(self) -> np.ndarray:
        """Boolean array [nx]: True where electrode is active."""
        mask = np.zeros(self.nx, dtype=bool)
        for start_frac, end_frac in self.pattern:
            i0 = int(start_frac * self.nx)
            i1 = int(end_frac * self.nx)
            mask[i0:i1] = True
        return mask


@dataclass
class SimSnapshot:
    """Simulation state at a moment in time."""
    time_s: float
    concentration: np.ndarray         # [nx, nz] mol/m^3
    potential: np.ndarray             # [nx, nz] V
    deposit_um: np.ndarray            # [nx] micrometers
    current_density_a_m2: np.ndarray  # [nx] at cathode surface
    gravity_m_s2: float = 0.0
    geometry_mask: np.ndarray | None = None

    @property
    def deposit_mean_um(self) -> float:
        active = self.deposit_um[self.deposit_um > 0.01]
        return float(np.mean(active)) if len(active) > 0 else 0.0

    @property
    def deposit_std_um(self) -> float:
        active = self.deposit_um[self.deposit_um > 0.01]
        return float(np.std(active)) if len(active) > 0 else 0.0

    @property
    def uniformity_pct(self) -> float:
        """100 = perfectly uniform, 0 = wildly varying."""
        mean = self.deposit_mean_um
        if mean < 0.01:
            return 100.0
        return max(0.0, 100.0 * (1.0 - self.deposit_std_um / mean))


@dataclass
class LayerSpec:
    """One layer in a multi-metal deposition sequence."""
    electrolyte: ElectrolyteConfig
    pattern: list[tuple[float, float]]
    duration_s: float = 600.0


@dataclass
class LayerResult:
    """Result of depositing one layer."""
    metal: str
    deposit_um: np.ndarray
    pattern: list[tuple[float, float]]
    final_snapshot: SimSnapshot


# Metal colors for visualization
METAL_COLORS: dict[str, str] = {
    "copper": "#B87333",
    "nickel": "#A0A0A8",
    "iron": "#6B6B6B",
    "zinc": "#BACCDB",
    "cobalt": "#5E7FB1",
}


# ---------------------------------------------------------------------------
# Geometry generators
# ---------------------------------------------------------------------------
def make_rectangular_mask(nx: int, nz: int) -> np.ndarray:
    """Full rectangular domain (all cells active)."""
    return np.ones((nx, nz), dtype=bool)


def make_ibeam_mask(
    nx: int,
    nz: int,
    flange_width_frac: float = 1.0,
    web_width_frac: float = 0.3,
    flange_height_frac: float = 0.25,
) -> np.ndarray:
    """I-beam cross-section pool: wide flanges top/bottom, narrow web.

    The bottom flange is the cathode (where metal deposits).
    The top flange has the anode (wire/rod).
    The web connects them with a narrower cross-section.
    """
    geo = np.zeros((nx, nz), dtype=bool)
    flange_z = max(1, int(flange_height_frac * nz))
    cx = nx // 2
    fl_half = max(1, int(flange_width_frac / 2 * nx))
    web_half = max(1, int(web_width_frac / 2 * nx))
    # Bottom flange
    geo[cx - fl_half:cx + fl_half, :flange_z] = True
    # Web
    geo[cx - web_half:cx + web_half, flange_z:nz - flange_z] = True
    # Top flange
    geo[cx - fl_half:cx + fl_half, nz - flange_z:] = True
    return geo


def make_channel_mask(
    nx: int, nz: int, channel_width_frac: float = 0.5,
) -> np.ndarray:
    """Simple rectangular channel (subset of full width)."""
    geo = np.zeros((nx, nz), dtype=bool)
    half = max(1, int(channel_width_frac / 2 * nx))
    cx = nx // 2
    geo[cx - half:cx + half, :] = True
    return geo


# ---------------------------------------------------------------------------
# Physics solvers
# ---------------------------------------------------------------------------
def _solve_potential_jacobi(config: DepositionConfig) -> np.ndarray:
    """Solve Laplace equation via Jacobi relaxation (legacy fallback)."""
    nx, nz = config.nx, config.nz
    dx, dz = config.dx, config.dz
    mask = config.electrode_mask()

    phi = np.zeros((nx, nz))
    z_frac = np.linspace(0.0, 1.0, nz)
    phi[:, :] = config.voltage_v * z_frac[np.newaxis, :]

    rx = (dz / dx) ** 2
    rz = 1.0
    denom = 2.0 * (rx + rz)

    for _ in range(15000):
        phi_prev = phi.copy()
        phi[1:-1, 1:-1] = (
            rx * (phi[:-2, 1:-1] + phi[2:, 1:-1])
            + rz * (phi[1:-1, :-2] + phi[1:-1, 2:])
        ) / denom
        phi[:, 0] = 0.0
        phi[mask, -1] = config.voltage_v
        phi[~mask, -1] = phi[~mask, -2]
        phi[0, :] = phi[1, :]
        phi[-1, :] = phi[-2, :]
        if np.max(np.abs(phi - phi_prev)) < 1e-8:
            break

    return phi


def _solve_potential(
    config: DepositionConfig,
    geometry_mask: np.ndarray | None = None,
    cathode_potential: np.ndarray | None = None,
) -> np.ndarray:
    """Solve Laplace equation for electric potential.

    Uses scipy sparse direct solver if available, Jacobi fallback otherwise.
    Supports arbitrary 2D geometry via geometry_mask and non-zero cathode
    potential for Butler-Volmer iteration.
    """
    if not HAS_SCIPY_SPARSE:
        return _solve_potential_jacobi(config)

    nx, nz = config.nx, config.nz
    dx, dz = config.dx, config.dz
    emask = config.electrode_mask()

    geo = geometry_mask if geometry_mask is not None else np.ones((nx, nz), dtype=bool)
    c_phi = cathode_potential if cathode_potential is not None else np.zeros(nx)

    # Build index map: active cell (i,j) -> linear index k
    idx = np.full((nx, nz), -1, dtype=int)
    cells = []
    k = 0
    for i in range(nx):
        for j in range(nz):
            if geo[i, j]:
                idx[i, j] = k
                cells.append((i, j))
                k += 1
    n_vars = k
    if n_vars == 0:
        return np.zeros((nx, nz))

    rows, cols, vals = [], [], []
    rhs = np.zeros(n_vars)
    rx = 1.0 / dx ** 2
    rz = 1.0 / dz ** 2

    for k, (i, j) in enumerate(cells):
        is_cathode = (j == 0)
        is_anode = (j == nz - 1) and (i < len(emask)) and emask[i]

        if is_cathode:
            rows.append(k); cols.append(k); vals.append(1.0)
            rhs[k] = c_phi[i]
            continue
        if is_anode:
            rows.append(k); cols.append(k); vals.append(1.0)
            rhs[k] = config.voltage_v
            continue

        # Interior or Neumann boundary
        diag = 0.0
        for di, dj, r in [(-1, 0, rx), (1, 0, rx), (0, -1, rz), (0, 1, rz)]:
            ni, nj = i + di, j + dj
            if 0 <= ni < nx and 0 <= nj < nz and geo[ni, nj]:
                nk = idx[ni, nj]
                rows.append(k); cols.append(nk); vals.append(r)
                diag -= r
            # else: Neumann -- missing neighbor contributes nothing
        rows.append(k); cols.append(k); vals.append(diag)

    A = coo_matrix((vals, (rows, cols)), shape=(n_vars, n_vars)).tocsr()
    phi_flat = sp_solve(A, rhs)

    phi = np.zeros((nx, nz))
    for k, (i, j) in enumerate(cells):
        phi[i, j] = phi_flat[k]
    return phi


def _compute_current_density(
    phi: np.ndarray,
    concentration: np.ndarray,
    config: DepositionConfig,
    electrolyte: ElectrolyteConfig,
    geometry_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Current density at cathode surface [A/m^2]."""
    c_ratio = np.clip(
        concentration[:, 0] / electrolyte.bulk_concentration_mol_m3, 0.0, 2.0
    )
    e_z = (phi[:, 1] - phi[:, 0]) / config.dz
    j = electrolyte.conductivity_s_m * c_ratio * e_z
    if geometry_mask is not None:
        j *= geometry_mask[:, 0]
    return j


def _mixing_rate(
    config: DepositionConfig, electrolyte: ElectrolyteConfig,
) -> float:
    """Convective mixing rate for 1g [1/s]."""
    g = config.gravity_m_s2
    if g <= 0:
        return 0.0
    D = electrolyte.diffusivity_m2_s
    C0 = electrolyte.bulk_concentration_mol_m3
    gap = config.gap_m
    Ra = g * BETA_SOLUTAL * C0 * gap ** 3 / (NU_WATER * D)
    Sh = max(1.0, 0.15 * Ra ** 0.28)
    return D * Sh ** 2 / gap ** 2


def compute_wagner_number(
    electrolyte: ElectrolyteConfig,
    kinetics: ElectrodeKinetics,
    config: DepositionConfig,
) -> float:
    """Wagner number: ratio of kinetic to ohmic resistance.

    Wa >> 1: kinetics dominate, current is uniform.
    Wa << 1: ohmic resistance dominates, geometry controls current.
    """
    L = config.gap_m
    kappa = electrolyte.conductivity_s_m
    T = config.temperature_k
    dj_deta = kinetics.j0_a_m2 * (kinetics.alpha_a + kinetics.alpha_c) * FARADAY / (R_GAS * T)
    return kappa / (dj_deta * L)


def _apply_kinetics_correction(
    j_primary: np.ndarray,
    electrolyte: ElectrolyteConfig,
    kinetics: ElectrodeKinetics,
    config: DepositionConfig,
    geometry_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Apply Wagner number correction to primary current distribution.

    Blends between primary distribution (Wa=0, geometry-controlled) and
    uniform distribution (Wa->inf, kinetics-controlled) based on the
    Wagner number.  From Newman's electrochemical systems theory.

    j_secondary = j_avg + (j_primary - j_avg) / (1 + Wa)
    """
    if geometry_mask is not None:
        cathode = geometry_mask[:, 0]
        active_j = j_primary[cathode]
    else:
        active_j = j_primary[j_primary > 0.01]

    if len(active_j) == 0:
        return j_primary.copy()

    j_avg = float(np.mean(active_j))
    wa = compute_wagner_number(electrolyte, kinetics, config)

    j_secondary = j_avg + (j_primary - j_avg) / (1.0 + wa)
    return np.maximum(j_secondary, 0.0)


def _step_concentration(
    C: np.ndarray,
    j_cathode: np.ndarray,
    config: DepositionConfig,
    electrolyte: ElectrolyteConfig,
    k_mix: float,
    cell_pattern: np.ndarray | None,
    geometry_mask: np.ndarray | None = None,
    flow_velocity_m_s: float = 0.0,
) -> np.ndarray:
    """Advance concentration field by one timestep."""
    dx, dz = config.dx, config.dz
    dt = config.dt_s
    D = electrolyte.diffusivity_m2_s
    n = electrolyte.charge_number
    C_bulk = electrolyte.bulk_concentration_mol_m3
    nz = config.nz

    C_new = C.copy()

    if geometry_mask is not None:
        geo = geometry_mask
        # Geometry-aware diffusion: only include contributions between active cells
        center = C[1:-1, 1:-1]
        left_ok = geo[:-2, 1:-1] & geo[1:-1, 1:-1]
        right_ok = geo[2:, 1:-1] & geo[1:-1, 1:-1]
        bottom_ok = geo[1:-1, :-2] & geo[1:-1, 1:-1]
        top_ok = geo[1:-1, 2:] & geo[1:-1, 1:-1]

        d2C_dx2 = (
            np.where(left_ok, C[:-2, 1:-1] - center, 0.0)
            + np.where(right_ok, C[2:, 1:-1] - center, 0.0)
        ) / dx ** 2
        d2C_dz2 = (
            np.where(bottom_ok, C[1:-1, :-2] - center, 0.0)
            + np.where(top_ok, C[1:-1, 2:] - center, 0.0)
        ) / dz ** 2
        interior = geo[1:-1, 1:-1]
        C_new[1:-1, 1:-1] += dt * D * (d2C_dx2 + d2C_dz2) * interior
    else:
        d2C_dx2 = (C[:-2, 1:-1] - 2.0 * C[1:-1, 1:-1] + C[2:, 1:-1]) / dx ** 2
        d2C_dz2 = (C[1:-1, :-2] - 2.0 * C[1:-1, 1:-1] + C[1:-1, 2:]) / dz ** 2
        C_new[1:-1, 1:-1] += dt * D * (d2C_dx2 + d2C_dz2)

    # Forced convection (upwind advection, flow in +z direction)
    if flow_velocity_m_s > 0:
        dC_dz = (C[1:-1, 1:-1] - C[1:-1, :-2]) / dz
        adv = flow_velocity_m_s * dC_dz
        if geometry_mask is not None:
            adv *= geometry_mask[1:-1, 1:-1]
        C_new[1:-1, 1:-1] -= dt * adv

    # Convective mixing (1g only)
    if k_mix > 0:
        z_frac_sq = np.linspace(0.0, 1.0, nz) ** 2
        if cell_pattern is not None:
            k_local = k_mix * (
                (1.0 + cell_pattern[1:-1, np.newaxis])
                * z_frac_sq[np.newaxis, 1:-1]
            )
        else:
            k_local = k_mix * z_frac_sq[np.newaxis, 1:-1]
        C_new[1:-1, 1:-1] += dt * k_local * (C_bulk - C_new[1:-1, 1:-1])

    # Cathode BC (z=0): Neumann flux from deposition
    flux_mol = j_cathode / (n * FARADAY)
    C_new[:, 0] = (
        C[:, 0]
        + dt * D * 2.0 * (C[:, 1] - C[:, 0]) / dz ** 2
        - dt * 2.0 * flux_mol / dz
    )

    # Top BC: bulk concentration
    C_new[:, -1] = C_bulk

    # Side walls: Neumann
    C_new[0, :] = C_new[1, :]
    C_new[-1, :] = C_new[-2, :]

    # Zero out outside geometry
    if geometry_mask is not None:
        C_new[~geometry_mask] = 0.0

    np.clip(C_new, 0.0, None, out=C_new)
    return C_new


# ---------------------------------------------------------------------------
# Simulation drivers
# ---------------------------------------------------------------------------
def run_simulation(
    config: DepositionConfig,
    electrolyte: ElectrolyteConfig,
    verbose: bool = False,
    geometry_mask: np.ndarray | None = None,
    kinetics: ElectrodeKinetics | None = None,
    flow_velocity_m_s: float = 0.0,
    pulse_on_s: float = 0.0,
    pulse_off_s: float = 0.0,
) -> list[SimSnapshot]:
    """Run patterned electrodeposition and return state snapshots."""
    nx = config.nx
    n = electrolyte.charge_number
    M = electrolyte.molar_mass_kg_mol
    rho = electrolyte.density_solid_kg_m3

    C = np.full((config.nx, config.nz), electrolyte.bulk_concentration_mol_m3)
    if geometry_mask is not None:
        C[~geometry_mask] = 0.0
    deposit_m = np.zeros(nx)

    phi = _solve_potential(config, geometry_mask)
    k_mix = _mixing_rate(config, electrolyte)

    cell_pattern = None
    if config.gravity_m_s2 > 0:
        x_coords = np.linspace(0.0, config.width_m, nx)
        wavelength = config.gap_m
        cell_pattern = 0.3 * np.sin(2.0 * np.pi * x_coords / wavelength + 0.7)

    snapshots: list[SimSnapshot] = []
    n_steps = int(config.duration_s / config.dt_s)
    next_snap = 0.0

    for step in range(n_steps + 1):
        t = step * config.dt_s
        j = _compute_current_density(phi, C, config, electrolyte, geometry_mask)
        if kinetics is not None:
            j = _apply_kinetics_correction(j, electrolyte, kinetics, config,
                                           geometry_mask)

        # Pulse plating: zero current during off-phase
        if pulse_on_s > 0:
            cycle = pulse_on_s + pulse_off_s
            phase = t % cycle
            if phase >= pulse_on_s:
                j = np.zeros_like(j)  # off-phase: no current, diffusion continues

        if t >= next_snap - 1e-9:
            snapshots.append(SimSnapshot(
                time_s=t,
                concentration=C.copy(),
                potential=phi.copy(),
                deposit_um=deposit_m * 1e6,
                current_density_a_m2=j.copy(),
                gravity_m_s2=config.gravity_m_s2,
                geometry_mask=geometry_mask,
            ))
            next_snap += config.snapshot_interval_s

        if step == n_steps:
            break

        if verbose and step > 0 and step % 10000 == 0:
            pct = step / n_steps * 100
            print(f"  {pct:.0f}%", end="...", flush=True)

        C = _step_concentration(C, j, config, electrolyte, k_mix, cell_pattern,
                                geometry_mask, flow_velocity_m_s)
        dh = M * np.maximum(j, 0.0) / (n * FARADAY * rho) * config.dt_s
        deposit_m += dh

    if verbose:
        print()
    return snapshots


def compare_gravity(
    electrolyte: ElectrolyteConfig | None = None,
    base_config: DepositionConfig | None = None,
    verbose: bool = False,
) -> tuple[list[SimSnapshot], list[SimSnapshot]]:
    """Run at 0g and 9.81 m/s^2, return (results_0g, results_1g)."""
    if electrolyte is None:
        electrolyte = COPPER_SULFATE
    if base_config is None:
        base_config = DepositionConfig()

    def _make(gravity: float) -> DepositionConfig:
        return DepositionConfig(
            width_mm=base_config.width_mm, gap_mm=base_config.gap_mm,
            nx=base_config.nx, nz=base_config.nz,
            voltage_v=base_config.voltage_v,
            temperature_k=base_config.temperature_k,
            duration_s=base_config.duration_s, dt_s=base_config.dt_s,
            snapshot_interval_s=base_config.snapshot_interval_s,
            pattern=list(base_config.pattern),
            gravity_m_s2=gravity,
        )

    if verbose:
        print("  0g run...", flush=True)
    results_0g = run_simulation(_make(0.0), electrolyte, verbose=verbose)

    if verbose:
        print("  1g run...", flush=True)
    results_1g = run_simulation(_make(9.81), electrolyte, verbose=verbose)

    return results_0g, results_1g


def run_multilayer(
    layers: list[LayerSpec],
    base_config: DepositionConfig | None = None,
    verbose: bool = False,
) -> list[LayerResult]:
    """Run sequential multi-metal deposition."""
    if base_config is None:
        base_config = DepositionConfig(
            gap_mm=0.2, nz=10, dt_s=0.1, snapshot_interval_s=60.0,
        )

    results: list[LayerResult] = []
    for i, layer in enumerate(layers):
        if verbose:
            print(f"  Layer {i + 1}/{len(layers)}: {layer.electrolyte.metal}...",
                  flush=True)
        cfg = DepositionConfig(
            width_mm=base_config.width_mm, gap_mm=base_config.gap_mm,
            nx=base_config.nx, nz=base_config.nz,
            voltage_v=base_config.voltage_v,
            temperature_k=base_config.temperature_k,
            duration_s=layer.duration_s, dt_s=base_config.dt_s,
            snapshot_interval_s=layer.duration_s,
            pattern=list(layer.pattern),
            gravity_m_s2=base_config.gravity_m_s2,
        )
        snaps = run_simulation(cfg, layer.electrolyte, verbose=False)
        results.append(LayerResult(
            metal=layer.electrolyte.metal,
            deposit_um=snaps[-1].deposit_um.copy(),
            pattern=list(layer.pattern),
            final_snapshot=snaps[-1],
        ))

    return results


def make_conformal_ibeam_mask(
    nx: int,
    nz: int,
    flange_width_frac: float = 1.0,
    web_width_frac: float = 0.3,
    gap_cells: int = 8,
) -> np.ndarray:
    """I-beam pool with constant-gap anode following cathode profile.

    Instead of filling the entire I-beam volume, the electrolyte forms a
    thin uniform-thickness layer that follows the I-beam cross-section.
    The anode mirrors the cathode at constant distance.
    This eliminates the path-length non-uniformity of the full pool.
    """
    geo = np.zeros((nx, nz), dtype=bool)
    cx = nx // 2
    fl_half = max(1, int(flange_width_frac / 2 * nx))
    web_half = max(1, int(web_width_frac / 2 * nx))
    g = min(gap_cells, nz)

    # Bottom flange region (full width, thin gap)
    geo[cx - fl_half:cx + fl_half, :g] = True
    # Web region (narrow, thin gap, stacked above flange)
    geo[cx - web_half:cx + web_half, g:2 * g] = True
    # Top flange region (full width, thin gap, stacked above web)
    geo[cx - fl_half:cx + fl_half, 2 * g:3 * g] = True
    return geo


def run_pool_simulation(
    pool_type: str = "ibeam",
    electrolyte: ElectrolyteConfig | None = None,
    kinetics: ElectrodeKinetics | None = None,
    config: DepositionConfig | None = None,
    flow_velocity_m_s: float = 0.0,
    pool_params: dict | None = None,
    pulse_on_s: float = 0.0,
    pulse_off_s: float = 0.0,
    verbose: bool = False,
) -> tuple[list[SimSnapshot], np.ndarray]:
    """Run electroforming simulation in a shaped pool.

    Returns (snapshots, geometry_mask).
    """
    if electrolyte is None:
        electrolyte = IRON_SULFATE
    if config is None:
        config = DepositionConfig(
            width_mm=50.0, gap_mm=30.0, nx=100, nz=60,
            voltage_v=0.5, duration_s=600.0, dt_s=0.1,
            snapshot_interval_s=600.0,
            pattern=[(0.0, 1.0)],  # full-coverage anode for pools
        )
    params = pool_params or {}

    if pool_type == "ibeam":
        geo = make_ibeam_mask(config.nx, config.nz, **params)
    elif pool_type == "ibeam_conformal":
        geo = make_conformal_ibeam_mask(config.nx, config.nz, **params)
    elif pool_type == "channel":
        geo = make_channel_mask(config.nx, config.nz, **params)
    else:
        geo = make_rectangular_mask(config.nx, config.nz)

    snaps = run_simulation(config, electrolyte, verbose=verbose,
                           geometry_mask=geo, kinetics=kinetics,
                           flow_velocity_m_s=flow_velocity_m_s,
                           pulse_on_s=pulse_on_s, pulse_off_s=pulse_off_s)
    return snaps, geo


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------
def render_comparison(
    results_0g: list[SimSnapshot],
    results_1g: list[SimSnapshot],
    config: DepositionConfig,
    electrolyte: ElectrolyteConfig,
    output_dir: str | Path = "output",
) -> Path | None:
    """Save 4-panel comparison figure as PNG."""
    if not HAS_MATPLOTLIB:
        return None

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    f0 = results_0g[-1]
    f1 = results_1g[-1]
    C0 = electrolyte.bulk_concentration_mol_m3

    fig = plt.figure(figsize=(14, 10))
    gs = GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.30)
    x_mm = np.linspace(0, config.width_mm, config.nx)

    ax1 = fig.add_subplot(gs[0, 0])
    im1 = ax1.imshow(f0.concentration.T, origin="lower", aspect="auto",
                     extent=[0, config.width_mm, 0, config.gap_mm],
                     cmap="viridis", vmin=0, vmax=C0)
    ax1.set_title("0g -- Ion concentration")
    ax1.set_xlabel("Position (mm)")
    ax1.set_ylabel("Gap height (mm)")
    plt.colorbar(im1, ax=ax1, label="mol/m^3")

    ax2 = fig.add_subplot(gs[0, 1])
    im2 = ax2.imshow(f1.concentration.T, origin="lower", aspect="auto",
                     extent=[0, config.width_mm, 0, config.gap_mm],
                     cmap="viridis", vmin=0, vmax=C0)
    ax2.set_title("1g -- Ion concentration")
    ax2.set_xlabel("Position (mm)")
    ax2.set_ylabel("Gap height (mm)")
    plt.colorbar(im2, ax=ax2, label="mol/m^3")

    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot(x_mm, f0.deposit_um, "b-", linewidth=2, label="0g")
    ax3.plot(x_mm, f1.deposit_um, "r--", linewidth=2, label="1g")
    for s, e in config.pattern:
        ax3.axvspan(s * config.width_mm, e * config.width_mm, alpha=0.1, color="gold")
    ax3.set_title("Deposit profile")
    ax3.set_xlabel("Position (mm)")
    ax3.set_ylabel("Thickness (um)")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(x_mm, f0.current_density_a_m2, "b-", linewidth=2, label="0g")
    ax4.plot(x_mm, f1.current_density_a_m2, "r--", linewidth=2, label="1g")
    for s, e in config.pattern:
        ax4.axvspan(s * config.width_mm, e * config.width_mm, alpha=0.1, color="gold")
    ax4.set_title("Current density at cathode")
    ax4.set_xlabel("Position (mm)")
    ax4.set_ylabel("J (A/m^2)")
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    fig.suptitle(
        f"Patterned Electrodeposition: {electrolyte.metal.title()} | "
        f"{config.voltage_v}V | {config.gap_mm}mm gap | "
        f"{config.duration_s / 60:.0f} min",
        fontsize=14, fontweight="bold",
    )
    fpath = out / f"deposition_{electrolyte.metal}_comparison.png"
    fig.savefig(fpath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fpath


def render_resolution_comparison(
    electrolyte: ElectrolyteConfig | None = None,
    output_dir: str | Path = "output",
) -> Path | None:
    """Compare pattern fidelity at 5mm vs 0.2mm gap."""
    if not HAS_MATPLOTLIB:
        return None
    if electrolyte is None:
        electrolyte = COPPER_SULFATE

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pattern = [(0.10, 0.30), (0.40, 0.60), (0.70, 0.90)]

    cfg_w = DepositionConfig(gap_mm=5.0, nx=100, nz=50, pattern=pattern)
    phi_w = _solve_potential(cfg_w)
    C_w = np.full((100, 50), electrolyte.bulk_concentration_mol_m3)
    j_w = _compute_current_density(phi_w, C_w, cfg_w, electrolyte)

    cfg_t = DepositionConfig(gap_mm=0.2, nx=100, nz=10, pattern=pattern)
    phi_t = _solve_potential(cfg_t)
    C_t = np.full((100, 10), electrolyte.bulk_concentration_mol_m3)
    j_t = _compute_current_density(phi_t, C_t, cfg_t, electrolyte)

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    x_mm = np.linspace(0, 20, 100)

    axes[0, 0].imshow(phi_w.T, origin="lower", aspect="auto",
                      extent=[0, 20, 0, 5], cmap="plasma")
    axes[0, 0].set_title("5mm gap -- Potential field")
    axes[0, 0].set_ylabel("Gap (mm)")

    axes[0, 1].imshow(phi_t.T, origin="lower", aspect="auto",
                      extent=[0, 20, 0, 0.2], cmap="plasma")
    axes[0, 1].set_title("0.2mm gap -- Potential field")
    axes[0, 1].set_ylabel("Gap (mm)")

    j_w_n = j_w / max(np.max(j_w), 1e-12)
    j_t_n = j_t / max(np.max(j_t), 1e-12)

    axes[1, 0].plot(x_mm, j_w_n, "b-", linewidth=2)
    axes[1, 0].set_title("5mm gap -- Current density (normalized)")
    axes[1, 0].set_ylim(-0.05, 1.15)

    axes[1, 1].plot(x_mm, j_t_n, "r-", linewidth=2)
    axes[1, 1].set_title("0.2mm gap -- Current density (normalized)")
    axes[1, 1].set_ylim(-0.05, 1.15)

    for ax in axes[1, :]:
        for s, e in pattern:
            ax.axvspan(s * 20, e * 20, alpha=0.15, color="gold")
        ax.set_xlabel("Position (mm)")
        ax.grid(True, alpha=0.3)

    fig.suptitle("Pattern Resolution: Gap-to-Feature Ratio Comparison",
                 fontsize=14, fontweight="bold")
    fig.tight_layout()
    fpath = out / "deposition_resolution_comparison.png"
    fig.savefig(fpath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fpath


def render_multilayer(
    layer_results: list[LayerResult],
    config: DepositionConfig,
    output_dir: str | Path = "output",
) -> Path | None:
    """Render multi-metal cross-section and layer pattern map."""
    if not HAS_MATPLOTLIB:
        return None

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    x_mm = np.linspace(0, config.width_mm, config.nx)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8),
                                    gridspec_kw={"height_ratios": [3, 1]})
    bottom = np.zeros_like(x_mm)
    for lr in layer_results:
        color = METAL_COLORS.get(lr.metal, "#999999")
        ax1.fill_between(x_mm, bottom, bottom + lr.deposit_um,
                         color=color, alpha=0.85, label=lr.metal.title(),
                         edgecolor="black", linewidth=0.3)
        bottom += lr.deposit_um

    ax1.set_xlabel("Position (mm)")
    ax1.set_ylabel("Cumulative thickness (um)")
    ax1.set_title("Multi-Metal Deposit Cross-Section (each layer = one press cycle)")
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, config.width_mm)

    n_layers = len(layer_results)
    for i, lr in enumerate(layer_results):
        color = METAL_COLORS.get(lr.metal, "#999999")
        for s, e in lr.pattern:
            ax2.barh(i, (e - s) * config.width_mm, left=s * config.width_mm,
                     height=0.7, color=color, alpha=0.85,
                     edgecolor="black", linewidth=0.5)
    ax2.set_xlabel("Position (mm)")
    ax2.set_title("Layer Patterns (top-down electrode mask per layer)")
    ax2.set_yticks(range(n_layers))
    ax2.set_yticklabels([f"L{i + 1} {lr.metal}" for i, lr in enumerate(layer_results)])
    ax2.set_xlim(0, config.width_mm)
    ax2.grid(True, alpha=0.3, axis="x")

    fig.suptitle(f"Sequential Patterned Deposition | {config.gap_mm}mm gap | "
                 f"{n_layers} layers", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fpath = out / "deposition_multilayer.png"
    fig.savefig(fpath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fpath


def render_pool_analysis(
    snapshots: list[SimSnapshot],
    config: DepositionConfig,
    electrolyte: ElectrolyteConfig,
    geometry_mask: np.ndarray,
    kinetics: ElectrodeKinetics | None = None,
    output_dir: str | Path = "output",
) -> Path | None:
    """Render 4-panel pool electroforming analysis."""
    if not HAS_MATPLOTLIB:
        return None

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    final = snapshots[-1]
    x_mm = np.linspace(0, config.width_mm, config.nx)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Panel 1: Pool geometry
    ax = axes[0, 0]
    display = geometry_mask.astype(float).T
    ax.imshow(display, origin="lower", aspect="auto",
              extent=[0, config.width_mm, 0, config.gap_mm],
              cmap="Greys", vmin=0, vmax=1.5)
    ax.set_title("Pool Geometry (white = electrolyte)")
    ax.set_xlabel("Position (mm)")
    ax.set_ylabel("Height (mm)")

    # Panel 2: Potential field (masked)
    ax = axes[0, 1]
    phi_masked = np.where(geometry_mask, final.potential, np.nan)
    ax.imshow(phi_masked.T, origin="lower", aspect="auto",
              extent=[0, config.width_mm, 0, config.gap_mm],
              cmap="plasma")
    ax.set_title("Potential field (V)")
    ax.set_xlabel("Position (mm)")
    ax.set_ylabel("Height (mm)")

    # Panel 3: Current density along cathode
    ax = axes[1, 0]
    j = final.current_density_a_m2
    cathode_active = geometry_mask[:, 0]
    j_plot = np.where(cathode_active, j, 0.0)
    ax.plot(x_mm, j_plot, "b-", linewidth=2)
    if np.max(j_plot) > 0:
        j_avg = np.mean(j_plot[cathode_active])
        ax.axhline(y=j_avg, color="orange", linestyle="--", linewidth=1,
                    label=f"Average: {j_avg:.1f} A/m^2")
        ax.legend()
    ax.set_title("Current density at cathode")
    ax.set_xlabel("Position (mm)")
    ax.set_ylabel("J (A/m^2)")
    ax.grid(True, alpha=0.3)

    # Panel 4: Deposit profile
    ax = axes[1, 1]
    dep = np.where(cathode_active, final.deposit_um, 0.0)
    ax.fill_between(x_mm, 0, dep, color="#6B6B6B", alpha=0.7, label="Deposit")
    ax.set_title("Deposit profile at cathode")
    ax.set_xlabel("Position (mm)")
    ax.set_ylabel("Thickness (um)")
    ax.grid(True, alpha=0.3)

    wa_str = ""
    if kinetics is not None:
        wa = compute_wagner_number(electrolyte, kinetics, config)
        wa_str = f" | Wa={wa:.2f}"

    fig.suptitle(
        f"Pool Electroforming: {electrolyte.metal.title()} | "
        f"{config.voltage_v}V | {config.gap_mm}mm depth{wa_str}",
        fontsize=14, fontweight="bold",
    )
    fig.tight_layout()
    fpath = out / "deposition_pool_analysis.png"
    fig.savefig(fpath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fpath


# ---------------------------------------------------------------------------
# ASCII reports
# ---------------------------------------------------------------------------
def format_report(
    results_0g: list[SimSnapshot],
    results_1g: list[SimSnapshot],
    electrolyte: ElectrolyteConfig,
    config: DepositionConfig,
) -> str:
    """Generate ASCII comparison report."""
    f0 = results_0g[-1]
    f1 = results_1g[-1]

    lines = [
        "=" * 64,
        "PATTERNED ELECTRODEPOSITION: 0g vs 1g COMPARISON",
        "=" * 64,
        f"  Metal:    {electrolyte.metal}",
        f"  Voltage:  {config.voltage_v} V",
        f"  Gap:      {config.gap_mm} mm",
        f"  Duration: {config.duration_s:.0f}s ({config.duration_s / 60:.0f} min)",
        f"  Grid:     {config.nx} x {config.nz}",
        f"  Pattern:  {len(config.pattern)} active stripe(s)",
        "",
        f"  {'Metric':<34s} {'0g':>10s} {'1g':>10s}",
        "  " + "-" * 56,
        f"  {'Mean deposit (um)':<34s} {f0.deposit_mean_um:>10.2f} {f1.deposit_mean_um:>10.2f}",
        f"  {'Std deviation (um)':<34s} {f0.deposit_std_um:>10.2f} {f1.deposit_std_um:>10.2f}",
        f"  {'Uniformity (%)':<34s} {f0.uniformity_pct:>10.1f} {f1.uniformity_pct:>10.1f}",
        f"  {'Peak deposit (um)':<34s} {np.max(f0.deposit_um):>10.2f} {np.max(f1.deposit_um):>10.2f}",
        f"  {'Mean current (A/m^2)':<34s} {np.mean(f0.current_density_a_m2):>10.1f} {np.mean(f1.current_density_a_m2):>10.1f}",
        f"  {'Min cathode conc (mol/m^3)':<34s} {np.min(f0.concentration[:, 0]):>10.1f} {np.min(f1.concentration[:, 0]):>10.1f}",
        "",
    ]

    if f0.uniformity_pct > f1.uniformity_pct:
        adv = f0.uniformity_pct - f1.uniformity_pct
        lines.append(f"  --> 0g uniformity advantage: +{adv:.1f} percentage points")

    if f1.deposit_mean_um > f0.deposit_mean_um > 0:
        ratio = f1.deposit_mean_um / f0.deposit_mean_um
        lines.append(f"  --> 1g deposits {ratio:.1f}x faster (convective enhancement)")

    lines += [
        "",
        "  KEY INSIGHT: 0g trades deposition speed for uniformity.",
        "  Without convection, every point under the electrode pattern",
        "  receives identical diffusive transport -- the deposit is as",
        "  uniform as the electrode pattern itself.",
        "=" * 64,
    ]
    return "\n".join(lines)


def format_pool_report(
    snapshots: list[SimSnapshot],
    config: DepositionConfig,
    electrolyte: ElectrolyteConfig,
    geometry_mask: np.ndarray,
    kinetics: ElectrodeKinetics | None = None,
) -> str:
    """ASCII report for pool electroforming analysis."""
    final = snapshots[-1]
    j = final.current_density_a_m2
    cathode = geometry_mask[:, 0]
    j_active = j[cathode]

    lines = [
        "=" * 64,
        "POOL ELECTROFORMING ANALYSIS",
        "=" * 64,
        f"  Metal:     {electrolyte.metal}",
        f"  Voltage:   {config.voltage_v} V",
        f"  Pool:      {config.width_mm} x {config.gap_mm} mm",
        f"  Grid:      {config.nx} x {config.nz}",
        f"  Duration:  {config.duration_s:.0f}s ({config.duration_s / 60:.0f} min)",
        f"  Cathode:   {int(np.sum(cathode))} of {config.nx} points active",
        "",
    ]

    if kinetics is not None:
        wa = compute_wagner_number(electrolyte, kinetics, config)
        lines.append(f"  Wagner number:     {wa:.3f}")
        if wa > 1:
            lines.append("    -> Kinetics dominate: current is relatively uniform")
        elif wa > 0.1:
            lines.append("    -> Mixed regime: geometry and kinetics both matter")
        else:
            lines.append("    -> Ohmic regime: geometry controls current distribution")
        lines.append("")

    if len(j_active) > 0:
        j_mean = float(np.mean(j_active))
        j_min = float(np.min(j_active))
        j_max = float(np.max(j_active))
        j_ratio = j_max / j_min if j_min > 1e-12 else float("inf")

        lines += [
            f"  {'Current density (A/m^2)':<34s}",
            f"    Mean:                          {j_mean:>10.1f}",
            f"    Min:                           {j_min:>10.1f}",
            f"    Max:                           {j_max:>10.1f}",
            f"    Max/Min ratio:                 {j_ratio:>10.1f}",
            "",
            f"  {'Deposit':<34s}",
            f"    Mean (um):                     {final.deposit_mean_um:>10.3f}",
            f"    Uniformity (%):                {final.uniformity_pct:>10.1f}",
            "",
        ]

        if j_ratio > 2.0:
            lines.append("  WARNING: Current concentration ratio > 2x")
            lines.append("  Corners/edges will deposit faster than flat regions.")
            lines.append("  Consider: pulse plating, auxiliary anodes, or")
            lines.append("  accepting non-uniform thickness and machining after.")
        elif j_ratio > 1.5:
            lines.append("  NOTICE: Moderate current non-uniformity (1.5-2x).")
            lines.append("  Acceptable for most structural applications.")
        else:
            lines.append("  GOOD: Current distribution is relatively uniform.")

    lines.append("=" * 64)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ("all", "gravity"):
        print("=== 0g vs 1g Comparison (5mm gap, copper, 1 hour) ===")
        cfg = DepositionConfig()
        r0, r1 = compare_gravity(COPPER_SULFATE, cfg, verbose=True)
        print()
        print(format_report(r0, r1, COPPER_SULFATE, cfg))
        p = render_comparison(r0, r1, cfg, COPPER_SULFATE, output_dir="output")
        if p:
            print(f"  Saved: {p}")

    if mode in ("all", "resolution"):
        print()
        print("=== Pattern Resolution: 5mm vs 0.2mm Gap ===")
        p = render_resolution_comparison(output_dir="output")
        if p:
            print(f"  Saved: {p}")

    if mode in ("all", "multilayer"):
        print()
        print("=== Multi-Metal Sequential Deposition (0.2mm gap) ===")
        thin_cfg = DepositionConfig(
            gap_mm=0.2, nx=100, nz=10, dt_s=0.1,
            voltage_v=0.3, duration_s=600.0,
            snapshot_interval_s=600.0,
        )
        layers = [
            LayerSpec(IRON_SULFATE,   [(0.0, 1.0)],               duration_s=600),
            LayerSpec(COPPER_SULFATE, [(0.15, 0.35), (0.65, 0.85)], duration_s=600),
            LayerSpec(NICKEL_SULFATE, [(0.05, 0.45), (0.55, 0.95)], duration_s=600),
        ]
        results = run_multilayer(layers, thin_cfg, verbose=True)
        total_um = sum(lr.deposit_um.max() for lr in results)
        print(f"  Total peak thickness: {total_um:.2f} um")
        for lr in results:
            print(f"    {lr.metal:>8s}: mean={np.mean(lr.deposit_um[lr.deposit_um > 0.01]):.3f} um, "
                  f"uniformity={lr.final_snapshot.uniformity_pct:.1f}%")
        p = render_multilayer(results, thin_cfg, output_dir="output")
        if p:
            print(f"  Saved: {p}")

    if mode in ("all", "pool"):
        cfg_pool = DepositionConfig(
            width_mm=50.0, gap_mm=30.0, nx=100, nz=60,
            voltage_v=0.5, duration_s=600.0, dt_s=0.1,
            snapshot_interval_s=600.0, pattern=[(0.0, 1.0)],
        )

        # --- Baseline: primary distribution (worst case) ---
        print()
        print("=== 1. BASELINE: I-Beam Pool, Primary Distribution ===")
        snaps_base, geo_base = run_pool_simulation(
            "ibeam", IRON_SULFATE, config=cfg_pool, verbose=True)
        print()
        print(format_pool_report(snaps_base, cfg_pool, IRON_SULFATE, geo_base))

        # --- Fix 1: Butler-Volmer kinetics ---
        print()
        print("=== 2. FIX: Add Butler-Volmer Kinetics (Wa=4.3) ===")
        snaps_bv, _ = run_pool_simulation(
            "ibeam", IRON_SULFATE, kinetics=IRON_KINETICS,
            config=cfg_pool, verbose=True)
        print()
        print(format_pool_report(snaps_bv, cfg_pool, IRON_SULFATE, geo_base,
                                  kinetics=IRON_KINETICS))

        # --- Fix 2: Pulse plating (2s on, 1s off) ---
        print()
        print("=== 3. FIX: Pulse Plating (2s on / 1s off) ===")
        snaps_pulse, _ = run_pool_simulation(
            "ibeam", IRON_SULFATE, config=cfg_pool,
            pulse_on_s=2.0, pulse_off_s=1.0, verbose=True)
        print()
        print(format_pool_report(snaps_pulse, cfg_pool, IRON_SULFATE, geo_base))

        # --- Fix 3: Conformal anode (constant-gap pool) ---
        print()
        print("=== 4. FIX: Conformal Anode (constant gap) ===")
        cfg_conf = DepositionConfig(
            width_mm=50.0, gap_mm=24.0, nx=100, nz=24,
            voltage_v=0.5, duration_s=600.0, dt_s=0.1,
            snapshot_interval_s=600.0, pattern=[(0.0, 1.0)],
        )
        snaps_conf, geo_conf = run_pool_simulation(
            "ibeam_conformal", IRON_SULFATE, config=cfg_conf, verbose=True)
        print()
        print(format_pool_report(snaps_conf, cfg_conf, IRON_SULFATE, geo_conf))

        # Save the baseline visualization
        p = render_pool_analysis(snaps_base, cfg_pool, IRON_SULFATE, geo_base,
                                 output_dir="output")
        if p:
            print(f"\n  Baseline figure: {p}")

        # Save the best fix visualization
        p = render_pool_analysis(snaps_bv, cfg_pool, IRON_SULFATE, geo_base,
                                  kinetics=IRON_KINETICS,
                                  output_dir="output")
        if p:
            print(f"  BV kinetics figure: {p}")
