"""UHF radio link budget calculator for AstraAnt missions.

Computes EIRP, free-space path loss, received power, noise floor,
available Eb/N0, link margin, and maximum data rate for a given distance.
Sweeps distance from 0.01 AU to 2.0 AU to show how throughput degrades.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# Physical constants
C_LIGHT = 299_792_458.0         # m/s
K_BOLTZMANN = 1.380649e-23      # J/K
AU_METERS = 149_597_870_700.0   # 1 AU in metres

# Default link parameters
DEFAULT_FREQ_HZ = 437e6         # 437 MHz UHF amateur satellite band
DEFAULT_TX_POWER_W = 2.0        # 2 W (33 dBm) typical CubeSat UHF
DEFAULT_TX_ANTENNA_GAIN_DBI = 6.0   # patch antenna
DEFAULT_TX_LINE_LOSS_DB = 1.0
DEFAULT_RX_ANTENNA_GAIN_DBI = 14.0  # 10-element Yagi on ground
DEFAULT_RX_LINE_LOSS_DB = 1.0
DEFAULT_SYSTEM_NOISE_TEMP_K = 500.0  # sky + receiver
DEFAULT_REQUIRED_EB_N0_DB = 10.0     # BPSK w/ convolutional coding
DEFAULT_IMPLEMENTATION_LOSS_DB = 2.0


def watts_to_dbm(watts: float) -> float:
    """Convert watts to dBm."""
    return 10.0 * math.log10(watts * 1000.0)


def watts_to_dbw(watts: float) -> float:
    """Convert watts to dBW."""
    return 10.0 * math.log10(watts)


def dbm_to_dbw(dbm: float) -> float:
    """Convert dBm to dBW."""
    return dbm - 30.0


@dataclass
class LinkBudgetParams:
    """All parameters for a single link budget calculation."""
    freq_hz: float = DEFAULT_FREQ_HZ
    tx_power_w: float = DEFAULT_TX_POWER_W
    tx_antenna_gain_dbi: float = DEFAULT_TX_ANTENNA_GAIN_DBI
    tx_line_loss_db: float = DEFAULT_TX_LINE_LOSS_DB
    distance_au: float = 1.0
    rx_antenna_gain_dbi: float = DEFAULT_RX_ANTENNA_GAIN_DBI
    rx_line_loss_db: float = DEFAULT_RX_LINE_LOSS_DB
    system_noise_temp_k: float = DEFAULT_SYSTEM_NOISE_TEMP_K
    required_eb_n0_db: float = DEFAULT_REQUIRED_EB_N0_DB
    implementation_loss_db: float = DEFAULT_IMPLEMENTATION_LOSS_DB


@dataclass
class LinkBudgetResult:
    """Complete link budget output."""
    params: LinkBudgetParams
    # Transmit side
    tx_power_dbm: float = 0.0
    tx_power_dbw: float = 0.0
    eirp_dbm: float = 0.0
    eirp_dbw: float = 0.0
    # Path
    wavelength_m: float = 0.0
    distance_m: float = 0.0
    fspl_db: float = 0.0
    # Receive side
    rx_power_dbw: float = 0.0
    rx_power_dbm: float = 0.0
    # Noise
    noise_density_dbw_hz: float = 0.0
    # Performance
    data_rate_bps: float = 0.0
    available_eb_n0_db: float = 0.0
    link_margin_db: float = 0.0
    max_data_rate_bps: float = 0.0
    link_closes: bool = False


def compute_fspl(distance_m: float, wavelength_m: float) -> float:
    """Free-space path loss in dB.

    FSPL = 20*log10(4*pi*d / lambda)
    """
    if distance_m <= 0 or wavelength_m <= 0:
        return 0.0
    return 20.0 * math.log10(4.0 * math.pi * distance_m / wavelength_m)


def compute_link_budget(
    params: LinkBudgetParams,
    data_rate_bps: float = 1200.0,
) -> LinkBudgetResult:
    """Compute a full link budget for the given parameters and data rate.

    Returns a LinkBudgetResult with every line item filled in.
    """
    r = LinkBudgetResult(params=params)

    # Transmit power
    r.tx_power_dbm = watts_to_dbm(params.tx_power_w)
    r.tx_power_dbw = watts_to_dbw(params.tx_power_w)

    # EIRP = TX power + antenna gain - line loss
    r.eirp_dbm = r.tx_power_dbm + params.tx_antenna_gain_dbi - params.tx_line_loss_db
    r.eirp_dbw = r.eirp_dbm - 30.0

    # Path
    r.wavelength_m = C_LIGHT / params.freq_hz
    r.distance_m = params.distance_au * AU_METERS
    r.fspl_db = compute_fspl(r.distance_m, r.wavelength_m)

    # Received power (dBW)
    r.rx_power_dbw = (r.eirp_dbw
                      - r.fspl_db
                      + params.rx_antenna_gain_dbi
                      - params.rx_line_loss_db
                      - params.implementation_loss_db)
    r.rx_power_dbm = r.rx_power_dbw + 30.0

    # Noise power density  N0 = k * T  (dBW/Hz)
    r.noise_density_dbw_hz = watts_to_dbw(K_BOLTZMANN * params.system_noise_temp_k)

    # Available Eb/N0 at the given data rate
    r.data_rate_bps = data_rate_bps
    r.available_eb_n0_db = (r.rx_power_dbw
                            - r.noise_density_dbw_hz
                            - 10.0 * math.log10(data_rate_bps))

    # Link margin
    r.link_margin_db = r.available_eb_n0_db - params.required_eb_n0_db
    r.link_closes = r.link_margin_db >= 0.0

    # Max data rate where margin = 3 dB (minimum operational margin)
    # Eb/N0_avail = Prx - N0 - 10*log10(R)  >=  Eb/N0_req + 3
    # => 10*log10(R) <= Prx - N0 - Eb/N0_req - 3
    max_log_r = (r.rx_power_dbw
                 - r.noise_density_dbw_hz
                 - params.required_eb_n0_db
                 - 3.0)
    if max_log_r > 0:
        r.max_data_rate_bps = 10.0 ** (max_log_r / 10.0)
    else:
        r.max_data_rate_bps = 0.0

    return r


def sweep_distances(
    params: LinkBudgetParams | None = None,
    distances_au: list[float] | None = None,
) -> list[LinkBudgetResult]:
    """Compute link budget across a range of distances.

    Returns a list of LinkBudgetResult, one per distance.
    """
    if params is None:
        params = LinkBudgetParams()
    if distances_au is None:
        distances_au = [0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 1.5, 2.0]

    results = []
    for d in distances_au:
        p = LinkBudgetParams(
            freq_hz=params.freq_hz,
            tx_power_w=params.tx_power_w,
            tx_antenna_gain_dbi=params.tx_antenna_gain_dbi,
            tx_line_loss_db=params.tx_line_loss_db,
            distance_au=d,
            rx_antenna_gain_dbi=params.rx_antenna_gain_dbi,
            rx_line_loss_db=params.rx_line_loss_db,
            system_noise_temp_k=params.system_noise_temp_k,
            required_eb_n0_db=params.required_eb_n0_db,
            implementation_loss_db=params.implementation_loss_db,
        )
        results.append(compute_link_budget(p))
    return results


def _fmt_rate(bps: float) -> str:
    """Format a bit rate for display."""
    if bps <= 0:
        return "-- link does not close --"
    if bps >= 1_000_000:
        return f"{bps / 1e6:.1f} Mbps"
    if bps >= 1_000:
        return f"{bps / 1e3:.1f} kbps"
    return f"{bps:.0f} bps"


def format_link_budget(result: LinkBudgetResult) -> str:
    """Format a single link budget as a human-readable table."""
    p = result.params
    lines = []
    lines.append("=" * 60)
    lines.append("UHF LINK BUDGET")
    lines.append("=" * 60)

    lines.append("")
    lines.append("--- TRANSMIT ---")
    lines.append(f"  Frequency:          {p.freq_hz / 1e6:.1f} MHz")
    lines.append(f"  TX power:           {p.tx_power_w:.1f} W ({result.tx_power_dbm:.1f} dBm)")
    lines.append(f"  TX antenna gain:    {p.tx_antenna_gain_dbi:+.1f} dBi (patch)")
    lines.append(f"  TX line loss:       -{p.tx_line_loss_db:.1f} dB")
    lines.append(f"  EIRP:               {result.eirp_dbm:.1f} dBm ({result.eirp_dbw:.1f} dBW)")

    lines.append("")
    lines.append("--- PATH ---")
    lines.append(f"  Distance:           {p.distance_au:.3f} AU ({result.distance_m:.3e} m)")
    lines.append(f"  Wavelength:         {result.wavelength_m:.4f} m")
    lines.append(f"  Free-space loss:    -{result.fspl_db:.1f} dB")

    lines.append("")
    lines.append("--- RECEIVE ---")
    lines.append(f"  RX antenna gain:    {p.rx_antenna_gain_dbi:+.1f} dBi (10-el Yagi)")
    lines.append(f"  RX line loss:       -{p.rx_line_loss_db:.1f} dB")
    lines.append(f"  Implementation loss:  -{p.implementation_loss_db:.1f} dB")
    lines.append(f"  Received power:     {result.rx_power_dbw:.1f} dBW ({result.rx_power_dbm:.1f} dBm)")

    lines.append("")
    lines.append("--- NOISE ---")
    lines.append(f"  System noise temp:  {p.system_noise_temp_k:.0f} K")
    lines.append(f"  Noise density N0:   {result.noise_density_dbw_hz:.1f} dBW/Hz")

    lines.append("")
    lines.append("--- PERFORMANCE ---")
    lines.append(f"  Data rate:          {_fmt_rate(result.data_rate_bps)}")
    lines.append(f"  Available Eb/N0:    {result.available_eb_n0_db:.1f} dB")
    lines.append(f"  Required Eb/N0:     {p.required_eb_n0_db:.1f} dB")
    lines.append(f"  Link margin:        {result.link_margin_db:+.1f} dB")
    lines.append(f"  Link closes:        {'YES' if result.link_closes else 'NO'}")

    lines.append("")
    lines.append(f"  Max data rate (3 dB margin): {_fmt_rate(result.max_data_rate_bps)}")

    lines.append("=" * 60)
    return "\n".join(lines)


def format_distance_sweep(results: list[LinkBudgetResult]) -> str:
    """Format a distance sweep as a table."""
    lines = []
    lines.append("")
    lines.append("DISTANCE vs DATA RATE (3 dB margin)")
    lines.append("-" * 60)
    lines.append(f"  {'Distance (AU)':<16s} {'FSPL (dB)':<12s} {'Rx (dBW)':<12s} {'Max Rate':<20s}")
    lines.append(f"  {'-'*14:<16s} {'-'*9:<12s} {'-'*8:<12s} {'-'*18:<20s}")
    for r in results:
        lines.append(
            f"  {r.params.distance_au:<16.3f} {r.fspl_db:<12.1f} "
            f"{r.rx_power_dbw:<12.1f} {_fmt_rate(r.max_data_rate_bps):<20s}"
        )
    lines.append("")
    return "\n".join(lines)
