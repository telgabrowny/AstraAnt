"""AstraAnt CLI -- command-line interface for the simulator and feasibility tracker."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml

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


@catalog.command("tools")
def catalog_tools():
    """List tool heads in the catalog."""
    from pathlib import Path
    import yaml
    tools_dir = Path(__file__).parent.parent / "catalog" / "tools"
    if not tools_dir.exists():
        click.echo("No tools catalog found.")
        return
    click.echo(f"{'ID':<20s} {'Type':<18s} {'Mass(g)':<10s} {'Cost($)':<10s} {'Electrical'}")
    click.echo("-" * 75)
    for f in sorted(tools_dir.glob("*.yaml")):
        with open(f) as fh:
            t = yaml.safe_load(fh)
        tid = t.get("id", "?")
        ttype = t.get("type", "?")
        mass = t.get("physical", {}).get("total_mass_g", "?")
        cost = t.get("cost_usd", "?")
        elec = t.get("electrical", {}).get("connector", "passive")
        if elec == "none" or elec is None:
            elec = "passive"
        click.echo(f"{tid:<20s} {ttype:<18s} {str(mass):<10s} ${str(cost):<9s} {elec}")


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
    """Show detailed info for an ant caste (worker, taskmaster, surface)."""
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
@click.option("--surface-ants", "-s", default=3, help="Number of surface ants")
@click.option("--track", type=click.Choice(["a", "b", "c"]), default="a", help="Extraction track")
@click.option("--asteroid", default="bennu", help="Target asteroid ID")
@click.option("--destination", type=click.Choice(["lunar_orbit", "mars_orbit", "earth_return"]),
              default="lunar_orbit", help="Cargo destination")
@click.option("--vehicle", default="starship_conservative", help="Launch vehicle")
def analyze(workers: int, taskmasters: int, surface_ants: int, track: str,
            asteroid: str, destination: str, vehicle: str):
    """Run feasibility analysis for a mission configuration."""
    mission = MissionConfig(
        swarm=SwarmConfig(workers=workers, taskmasters=taskmasters, surface_ants=surface_ants, track=track),
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
@click.option("--surface-ants", "-s", default=3, help="Number of surface ants")
@click.option("--asteroid", default="bennu", help="Target asteroid ID")
@click.option("--destination", type=click.Choice(["lunar_orbit", "mars_orbit", "earth_return"]),
              default="lunar_orbit")
@click.option("--vehicle", default="starship_conservative")
def compare(workers: int, taskmasters: int, surface_ants: int,
            asteroid: str, destination: str, vehicle: str):
    """Compare all three extraction tracks head-to-head."""
    cat = Catalog()
    click.echo("Running three-track comparison...\n")

    reports = {}
    for track in ["a", "b", "c"]:
        mission = MissionConfig(
            swarm=SwarmConfig(workers=workers, taskmasters=taskmasters, surface_ants=surface_ants, track=track),
            asteroid_id=asteroid,
            destination=destination,
            launch_vehicle=vehicle,
        )
        reports[track] = analyze_mission(mission, cat)

    # Comparison table
    click.echo("=" * 70)
    click.echo("THREE-TRACK COMPARISON")
    click.echo("=" * 70)
    click.echo(f"Swarm: {workers}W + {taskmasters}T + {surface_ants}S -> {asteroid} -> {destination}\n")

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


# -- Sensitivity command -------------------------------------------------------

@main.command()
@click.option("--workers", "-w", default=100, help="Baseline worker count")
@click.option("--track", type=click.Choice(["a", "b", "c"]), default="b")
@click.option("--asteroid", default="bennu")
@click.option("--destination", default="lunar_orbit")
def sensitivity(workers: int, track: str, asteroid: str, destination: str):
    """Run sensitivity analysis -- which parameters matter most."""
    from .sensitivity import run_sensitivity, format_sensitivity
    from .feasibility import MissionConfig, SwarmConfig
    baseline = MissionConfig(
        swarm=SwarmConfig(workers=workers, taskmasters=max(1, workers // 20),
                          surface_ants=3, track=track),
        asteroid_id=asteroid,
        destination=destination,
    )
    results = run_sensitivity(baseline)
    click.echo(format_sensitivity(results))


@build.command("scad")
@click.argument("tool_id", required=False, default=None)
@click.option("--all", "gen_all", is_flag=True, help="Generate all tool models")
@click.option("--output-dir", "-o", default=None, help="Output directory")
def build_scad(tool_id: str | None, gen_all: bool, output_dir: str | None):
    """Generate OpenSCAD 3D-printable models for tool heads."""
    from .scad_generator import generate_tool_scad, generate_all_tools, TOOL_GENERATORS

    if gen_all or tool_id is None:
        out = Path(output_dir) if output_dir else None
        files = generate_all_tools(out)
        click.echo(f"Generated {len(files)} OpenSCAD tool models:")
        for f in files:
            click.echo(f"  {f}")
    else:
        if tool_id not in TOOL_GENERATORS:
            click.echo(f"Unknown tool '{tool_id}'. Available: {', '.join(TOOL_GENERATORS.keys())}")
            return
        code = generate_tool_scad(tool_id)
        if output_dir:
            filepath = Path(output_dir) / f"{tool_id}.scad"
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(code)
            click.echo(f"Written to {filepath}")
        else:
            click.echo(code)


@build.command("wiring")
@click.argument("caste")
@click.option("--track", type=click.Choice(["a", "b", "c"]), default="a")
@click.option("--output", "-o", default=None, help="Output file path")
def build_wiring(caste: str, track: str, output: str | None):
    """Generate wiring diagram for an ant caste."""
    from .wiring import generate_wiring_diagram
    text = generate_wiring_diagram(caste, track)
    if output:
        Path(output).write_text(text)
        click.echo(f"Wiring diagram written to {output}")
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


# -- Simulate command (headless) ------------------------------------------------

@main.command()
@click.option("--workers", "-w", default=50, help="Number of worker ants")
@click.option("--taskmasters", "-t", default=3, help="Number of taskmasters")
@click.option("--surface-ants", "-s", default=2, help="Number of surface ants")
@click.option("--track", type=click.Choice(["a", "b", "c"]), default="a")
@click.option("--days", default=30, help="Simulated mission days to run")
@click.option("--speed", default=10000.0, help="Simulation speed multiplier")
def simulate(workers: int, taskmasters: int, surface_ants: int,
             track: str, days: int, speed: float):
    """Run headless simulation and print results."""
    from .gui.simulation.sim_engine import SimEngine

    total_ants = workers + taskmasters + surface_ants
    click.echo(f"Running {days}-day simulation with {total_ants} ants (Track {track.upper()})...")
    click.echo(f"  Workers dynamically assigned roles: mining, sorting, plastering, tending")

    engine = SimEngine(
        workers=workers, taskmasters=taskmasters, surface_ants=surface_ants,
        track=track,
    )
    engine.setup()
    engine.clock.speed = speed

    # Simulate in 0.1-second real-time steps
    target_sim_time = days * 86400.0
    step = 0.1
    while engine.clock.sim_time < target_sim_time:
        engine.tick(step)

    status = engine.status()

    click.echo(f"\n{'=' * 60}")
    click.echo(f"SIMULATION RESULTS -- {days} days, Track {track.upper()}")
    click.echo(f"{'=' * 60}")
    click.echo(f"  Elapsed sim time:    {status['clock']}")
    click.echo(f"  Total ants:          {status['total_ants']}")

    for caste, counts in status["ants_by_caste"].items():
        click.echo(f"    {caste:14s} active: {counts['active']}  failed: {counts['failed']}")

    t = status["tunnel"]
    click.echo(f"\n  Tunnel:")
    click.echo(f"    Length:     {t['total_length_m']:.1f} m")
    click.echo(f"    Volume:     {t['total_volume_m3']:.2f} m3")
    click.echo(f"    Sealed:     {t['sealed_length_m']:.1f} m")

    s = status["stats"]
    click.echo(f"\n  Production:")
    click.echo(f"    Material extracted: {s['material_kg']:.1f} kg")
    click.echo(f"    Water recovered:   {s['water_kg']:.1f} kg")
    click.echo(f"    Wall sealed:       {s['sealed_m2']:.1f} m2")
    click.echo(f"    Dump cycles:       {s['dump_cycles']}")
    click.echo(f"    Drum cycles:       {s['drum_cycles']}")
    click.echo(f"    Vat checks:        {s['vat_checks']}")
    click.echo(f"    Anomalies:         {s['anomalies']}")
    click.echo(f"    Ant failures:      {s['failures']}")
    click.echo(f"{'=' * 60}")


# -- GUI command ----------------------------------------------------------------

@main.command()
@click.option("--asteroid", default="bennu", help="Target asteroid ID")
@click.option("--workers", "-w", default=20, help="Number of worker ants")
@click.option("--taskmasters", "-t", default=1, help="Number of taskmasters")
@click.option("--surface-ants", "-s", default=2, help="Number of surface ants")
@click.option("--track", type=click.Choice(["a", "b", "c"]), default="a")
def gui(asteroid: str, workers: int, taskmasters: int, surface_ants: int,
        track: str):
    """Launch the 3D interactive simulation."""
    try:
        from .gui import launch
    except ImportError as e:
        click.echo(f"GUI dependencies not installed. Run: pip install astraant[gui]")
        click.echo(f"Error: {e}")
        return
    launch(asteroid=asteroid, workers=workers, taskmasters=taskmasters,
           couriers=surface_ants, track=track)


if __name__ == "__main__":
    main()
