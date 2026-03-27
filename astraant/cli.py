"""AstraAnt CLI -- command-line interface for the simulator and feasibility tracker."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from .catalog import Catalog
from .configs import (
    compute_ant_cost,
    compute_ant_mass,
    compute_ant_power,
    load_all_ant_configs,
)
from .feasibility import (
    FeasibilityReport,
    MissionConfig,
    SwarmConfig,
    analyze_mission,
    format_report,
)


@click.group()
@click.version_option(package_name="astraant")
def main():
    """AstraAnt -- Ant Swarm Asteroid Mining Simulator & Feasibility Tracker."""
    pass


# -- Catalog commands ------------------------------------------------------

@main.group()
def catalog():
    """Inspect and manage the component catalog."""
    pass


@catalog.command("summary")
def catalog_summary():
    """Show catalog entry counts."""
    cat = Catalog()
    counts = cat.summary()
    click.echo("Catalog Summary:")
    for kind, count in counts.items():
        click.echo(f"  {kind:12s} {count}")
    click.echo(f"  {'TOTAL':12s} {sum(counts.values())}")


@catalog.command("parts")
@click.option("--category", "-c", default=None, help="Filter by category")
def catalog_parts(category: str | None):
    """List all parts in the catalog."""
    cat = Catalog()
    parts = cat.parts_by_category(category) if category else cat.parts
    if not parts:
        click.echo(f"No parts found{' in category ' + category if category else ''}.")
        return
    click.echo(f"{'ID':<30s} {'Category':<15s} {'Mass(g)':<10s} {'Price($)':<10s} {'Stale?'}")
    click.echo("-" * 80)
    for p in parts:
        mass = p.get("specs", {}).get("mass_g", "?")
        price = p.best_price()
        price_str = f"${price:.2f}" if price else "?"
        stale_days = p.days_since_price_check()
        stale = f"{stale_days}d" if stale_days else "?"
        click.echo(f"{p.id:<30s} {p.get('category', '?'):<15s} {str(mass):<10s} {price_str:<10s} {stale}")


@catalog.command("asteroids")
@click.option("--max-dv", type=float, default=None, help="Max delta-v from LEO (km/s)")
def catalog_asteroids(max_dv: float | None):
    """List asteroids in the catalog."""
    cat = Catalog()
    asteroids = cat.asteroids_by_accessibility(max_dv) if max_dv else cat.asteroids
    if not asteroids:
        click.echo("No asteroids found.")
        return
    click.echo(f"{'ID':<20s} {'Name':<20s} {'Type':<10s} {'dv(km/s)':<10s} {'Confidence':<12s} {'Water?'}")
    click.echo("-" * 85)
    for a in asteroids:
        name = a.get("name", "?")
        spec = a.get("physical", {}).get("spectral_class", "?")
        dv = a.get("mining_relevance", {}).get("accessibility", {}).get("delta_v_from_leo_km_per_s", "?")
        conf = a.get("composition", {}).get("confidence", "?")
        water = a.get("mining_relevance", {}).get("water_availability", False)
        click.echo(f"{a.id:<20s} {name:<20s} {spec:<10s} {str(dv):<10s} {conf:<12s} {'Yes' if water else 'No'}")


@catalog.command("species")
def catalog_species():
    """List biological species in the catalog."""
    cat = Catalog()
    if not cat.species:
        click.echo("No species in catalog.")
        return
    click.echo(f"{'ID':<40s} {'Type':<10s} {'Targets'}")
    click.echo("-" * 80)
    for s in cat.species:
        stype = s.get("type", "?")
        targets = s.get("extraction", {}).get("target_metals", [])
        click.echo(f"{s.id:<40s} {stype:<10s} {', '.join(targets)}")


@catalog.command("stale")
@click.option("--days", default=90, help="Stale threshold in days")
def catalog_stale(days: int):
    """Find parts with outdated pricing."""
    cat = Catalog()
    stale = cat.stale_parts(days)
    if not stale:
        click.echo(f"All parts have been price-checked within {days} days.")
        return
    click.echo(f"Parts not price-checked in {days}+ days:")
    for p in stale:
        d = p.days_since_price_check()
        click.echo(f"  {p.id}: {d} days since last check")


# -- Ant commands ----------------------------------------------------------

@main.group()
def ant():
    """Inspect ant caste configurations."""
    pass


@ant.command("info")
@click.argument("caste")
def ant_info(caste: str):
    """Show detailed info for an ant caste (worker, taskmaster, courier)."""
    configs = load_all_ant_configs()
    if caste not in configs:
        click.echo(f"Unknown caste '{caste}'. Available: {', '.join(configs.keys())}")
        return
    cfg = configs[caste]
    mass = compute_ant_mass(cfg)
    power = compute_ant_power(cfg)
    cost = compute_ant_cost(cfg)

    click.echo(f"\n{'=' * 50}")
    click.echo(f"ANT CASTE: {caste.upper()}")
    click.echo(f"{'=' * 50}")
    click.echo(f"  Mass budget: {cfg.get('chassis', {}).get('mass_budget_g', '?')} g")
    click.echo(f"  Computed mass: {mass:.0f} g")
    over = mass > cfg.get("chassis", {}).get("mass_budget_g", 9999)
    if over:
        click.echo(f"  *** OVER MASS BUDGET ***")
    click.echo(f"  Estimated cost: ${cost:.0f}")
    click.echo(f"\n  Power:")
    click.echo(f"    Idle:   {power['idle_mw']:.0f} mW")
    click.echo(f"    Active: {power['active_mw']:.0f} mW")
    click.echo(f"    Peak:   {power['peak_mw']:.0f} mW")
    click.echo(f"\n  Components:")
    click.echo(f"    Compute: {cfg.get('compute', {}).get('part_id', '?')}")
    click.echo(f"    Locomotion: {cfg.get('locomotion', {}).get('actuators', '?')}x "
               f"{cfg.get('locomotion', {}).get('part_id', '?')}")
    click.echo(f"    Sensors: {len(cfg.get('sensors', []))}")


@ant.command("list")
def ant_list():
    """List all ant castes with summary stats."""
    configs = load_all_ant_configs()
    if not configs:
        click.echo("No ant configurations found.")
        return
    click.echo(f"{'Caste':<15s} {'Mass(g)':<10s} {'Cost($)':<10s} {'Idle(mW)':<10s} {'Active(mW)':<12s}")
    click.echo("-" * 60)
    for caste, cfg in configs.items():
        mass = compute_ant_mass(cfg)
        power = compute_ant_power(cfg)
        cost = compute_ant_cost(cfg)
        click.echo(f"{caste:<15s} {mass:<10.0f} {cost:<10.0f} {power['idle_mw']:<10.0f} {power['active_mw']:<12.0f}")


# -- Analyze commands ------------------------------------------------------

@main.command()
@click.option("--workers", "-w", default=100, help="Number of worker ants")
@click.option("--taskmasters", "-t", default=5, help="Number of taskmaster ants")
@click.option("--couriers", "-c", default=3, help="Number of courier ants")
@click.option("--track", type=click.Choice(["a", "b", "c"]), default="a", help="Extraction track")
@click.option("--asteroid", default="bennu", help="Target asteroid ID")
@click.option("--destination", type=click.Choice(["lunar_orbit", "mars_orbit", "earth_return"]),
              default="lunar_orbit", help="Cargo destination")
@click.option("--vehicle", default="starship_conservative", help="Launch vehicle")
def analyze(workers: int, taskmasters: int, couriers: int, track: str,
            asteroid: str, destination: str, vehicle: str):
    """Run feasibility analysis for a mission configuration."""
    mission = MissionConfig(
        swarm=SwarmConfig(workers=workers, taskmasters=taskmasters, couriers=couriers, track=track),
        asteroid_id=asteroid,
        destination=destination,
        launch_vehicle=vehicle,
    )
    cat = Catalog()
    report = analyze_mission(mission, cat)
    click.echo(format_report(report))


@main.command()
@click.option("--workers", "-w", default=100, help="Number of worker ants")
@click.option("--taskmasters", "-t", default=5, help="Number of taskmasters")
@click.option("--couriers", "-c", default=3, help="Number of couriers")
@click.option("--asteroid", default="bennu", help="Target asteroid ID")
@click.option("--destination", type=click.Choice(["lunar_orbit", "mars_orbit", "earth_return"]),
              default="lunar_orbit")
@click.option("--vehicle", default="starship_conservative")
def compare(workers: int, taskmasters: int, couriers: int,
            asteroid: str, destination: str, vehicle: str):
    """Compare all three extraction tracks head-to-head."""
    cat = Catalog()
    click.echo("Running three-track comparison...\n")

    reports = {}
    for track in ["a", "b", "c"]:
        mission = MissionConfig(
            swarm=SwarmConfig(workers=workers, taskmasters=taskmasters, couriers=couriers, track=track),
            asteroid_id=asteroid,
            destination=destination,
            launch_vehicle=vehicle,
        )
        reports[track] = analyze_mission(mission, cat)

    # Comparison table
    click.echo("=" * 70)
    click.echo("THREE-TRACK COMPARISON")
    click.echo("=" * 70)
    click.echo(f"Swarm: {workers}W + {taskmasters}T + {couriers}C -> {asteroid} -> {destination}\n")

    click.echo(f"{'Metric':<30s} {'Track A':<18s} {'Track B':<18s} {'Track C':<18s}")
    click.echo("-" * 85)

    def fmt_usd(v: float) -> str:
        if v >= 1_000_000:
            return f"${v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"${v/1_000:.0f}K"
        return f"${v:.0f}"

    def fmt_kg(v: float) -> str:
        return f"{v:.1f} kg"

    ra, rb, rc = reports["a"], reports["b"], reports["c"]

    click.echo(f"{'Total mass (wet+margin)':<30s} {fmt_kg(ra.mass_budget.total_with_margin_kg):<18s} "
               f"{fmt_kg(rb.mass_budget.total_with_margin_kg):<18s} "
               f"{fmt_kg(rc.mass_budget.total_with_margin_kg):<18s}")
    click.echo(f"{'Launch cost':<30s} {fmt_usd(ra.cost_estimate.launch_cost_usd):<18s} "
               f"{fmt_usd(rb.cost_estimate.launch_cost_usd):<18s} "
               f"{fmt_usd(rc.cost_estimate.launch_cost_usd):<18s}")
    click.echo(f"{'Total 1st cycle cost':<30s} {fmt_usd(ra.cost_estimate.total_first_cycle_usd):<18s} "
               f"{fmt_usd(rb.cost_estimate.total_first_cycle_usd):<18s} "
               f"{fmt_usd(rc.cost_estimate.total_first_cycle_usd):<18s}")
    click.echo(f"{'Revenue/cycle':<30s} {fmt_usd(ra.revenue_per_cycle_usd):<18s} "
               f"{fmt_usd(rb.revenue_per_cycle_usd):<18s} "
               f"{fmt_usd(rc.revenue_per_cycle_usd):<18s}")

    def fmt_be(cycles: int) -> str:
        return f"{cycles} cycles" if cycles > 0 else "NEVER"

    click.echo(f"{'Break-even':<30s} {fmt_be(ra.break_even_cycles):<18s} "
               f"{fmt_be(rb.break_even_cycles):<18s} "
               f"{fmt_be(rc.break_even_cycles):<18s}")

    click.echo("\n" + "=" * 70)


# -- Build commands (BOM export) ------------------------------------------─

@main.group()
def build():
    """Export build packages (BOM, wiring, firmware) for physical ant construction."""
    pass


@build.command("bom")
@click.argument("caste")
@click.option("--track", type=click.Choice(["a", "b", "c"]), default="a")
@click.option("--output", "-o", default=None, help="Output file path")
def build_bom(caste: str, track: str, output: str | None):
    """Generate Bill of Materials for an ant caste."""
    configs = load_all_ant_configs()
    if caste not in configs:
        click.echo(f"Unknown caste '{caste}'. Available: {', '.join(configs.keys())}")
        return

    cat = Catalog()
    cfg = configs[caste]

    lines = []
    lines.append(f"# Bill of Materials -- {caste.upper()} Ant (Track {track.upper()})")
    lines.append(f"# Generated by AstraAnt v{__import__('astraant').__version__}")
    lines.append("")
    lines.append(f"{'#':<4s} {'Component':<30s} {'Part ID':<25s} {'Qty':<5s} {'Unit $':<10s} {'Total $':<10s}")
    lines.append("-" * 90)

    total_cost = 0.0
    total_mass = 0.0
    item_num = 0

    def add_item(component: str, part_id: str, qty: int, unit_cost: float, unit_mass: float):
        nonlocal item_num, total_cost, total_mass
        item_num += 1
        total = qty * unit_cost
        total_cost += total
        total_mass += qty * unit_mass
        lines.append(f"{item_num:<4d} {component:<30s} {part_id:<25s} {qty:<5d} "
                     f"${unit_cost:<9.2f} ${total:<9.2f}")

    # Compute
    comp = cfg.get("compute", {})
    add_item("Microcontroller", comp.get("part_id", "?"), 1,
             comp.get("cost_usd", 5), comp.get("mass_g", 5))

    # Locomotion
    loco = cfg.get("locomotion", {})
    add_item("Leg actuator", loco.get("part_id", "?"),
             loco.get("actuators", 6),
             loco.get("per_unit_cost_usd", 3),
             loco.get("per_unit_mass_g", 9))

    # Communication
    comms = cfg.get("communication", {})
    if isinstance(comms, list):
        for c in comms:
            add_item(f"Comm: {c.get('purpose', '?')}", c.get("part_id", c.get("type", "?")),
                     1, c.get("cost_usd", 5), c.get("mass_g", 5))
    elif isinstance(comms, dict):
        add_item("Communication", comms.get("part_id", "?"), 1,
                 comms.get("cost_usd", 5), comms.get("mass_g", 5))

    # Sensors
    for sensor in cfg.get("sensors", []):
        add_item(f"Sensor: {sensor.get('purpose', '?')[:20]}", sensor.get("part_id", "?"),
                 1, sensor.get("cost_usd", 5), sensor.get("mass_g", 2))

    # Tool (track-specific)
    tool = cfg.get("tool", {})
    if isinstance(tool, dict) and track in ("a", "b", "c"):
        track_tool = tool.get(f"track_{track}", tool)
        if track_tool and track_tool.get("type") != "none":
            add_item(f"Tool: {track_tool.get('type', '?')}", track_tool.get("part_id", "?"),
                     1, track_tool.get("cost_usd", 5), track_tool.get("mass_g", 10))

    # Solar (if present)
    solar = cfg.get("solar", {})
    if solar:
        add_item("Solar cell", solar.get("part_id", "?"), 1,
                 solar.get("cost_usd", 0), solar.get("mass_g", 0))

    # Battery
    battery = cfg.get("battery", cfg.get("power", {}).get("backup_battery", {}))
    if battery and battery.get("capacity_mah"):
        add_item("Battery (LiPo)", "lipo_cell", 1,
                 battery.get("cost_usd", 5), battery.get("mass_g", 15))

    lines.append("-" * 90)
    lines.append(f"{'':4s} {'TOTAL':<30s} {'':25s} {'':5s} {'':10s} ${total_cost:<9.2f}")
    lines.append(f"\nTotal estimated mass: {total_mass:.0f} g")
    lines.append(f"Mass budget: {cfg.get('chassis', {}).get('mass_budget_g', '?')} g")

    text = "\n".join(lines)

    if output:
        Path(output).write_text(text)
        click.echo(f"BOM written to {output}")
    else:
        click.echo(text)


# -- Readiness commands -----------------------------------------------------

@main.command()
@click.option("--track", type=click.Choice(["a", "b", "c"]), default="a",
              help="Extraction track to assess")
def readiness(track: str):
    """Run readiness assessment -- what's proven, what needs testing."""
    from .readiness import assess_mission, format_readiness_report
    cat = Catalog()
    report = assess_mission(cat, track=track)
    click.echo(format_readiness_report(report))


if __name__ == "__main__":
    main()
