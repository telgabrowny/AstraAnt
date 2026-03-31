"""Seed Mothership Bill of Materials.

Complete BOM, cost, mass, and sizing for the minimum viable
seed mothership: the "microwave oven that grows into a space station."
"""

import math


def generate_bom_report() -> str:
    lines = []
    bom = []

    def item(subsys, name, mass_kg, cost_usd, qty, notes):
        bom.append((subsys, name, mass_kg * qty, cost_usd * qty, qty, notes))

    # === STRUCTURE ===
    item('STRUCT', 'Aluminum frame (6061-T6)', 2.5, 400, 1, 'CubeSat-class chassis')
    item('STRUCT', 'Deployment springs + hinges', 0.3, 200, 1, 'Membrane + panel release')
    item('STRUCT', 'Rock clamp + aperture frame', 0.4, 300, 1, 'Grips rock, seals membrane')

    # === POWER ===
    item('POWER', 'Deployable solar panel (2 m2)', 1.5, 40000, 2,
         '4 m2 total = 1.1 kW at 1 AU')
    item('POWER', 'Li-ion battery (28V, 100Wh)', 0.8, 1500, 2,
         'Eclipse + peak loads, redundant')
    item('POWER', 'MPPT + power distribution', 0.4, 2500, 1,
         'Panel -> cell -> motors')

    # === PROPULSION ===
    item('PROP', 'Ion thruster (BIT-3 class)', 1.5, 120000, 1,
         'Iodine-fed, 1.4 mN, Isp 2200s')
    item('PROP', 'Iodine propellant', 1.0, 80, 5,
         '5 kg solid iodine, easy storage')
    item('PROP', 'Cold gas thruster (attitude)', 0.15, 500, 4,
         'N2, fine positioning for rock capture')
    item('PROP', 'N2 propellant tank', 0.5, 300, 1,
         '0.5 kg N2 for attitude control')

    # === COMPUTE + COMMS ===
    item('COMP', 'ESP32-S3 (TMR, 3 units)', 0.015, 5, 3,
         'Triple voting, radiation tolerance')
    item('COMP', 'Watchdog + power cycling board', 0.05, 200, 1,
         'Auto-resets hung processors')
    item('COMP', 'UHF radio + patch antenna', 0.3, 3000, 1,
         '9600 bps Earth link')
    item('COMP', 'X-band backup transmitter', 0.15, 5000, 1,
         'Higher bandwidth option')
    item('COMP', 'Sun sensor + magnetometer', 0.1, 2000, 1,
         'Coarse attitude determination')
    item('COMP', 'Star tracker (nano class)', 0.15, 12000, 1,
         'Arcsec-level navigation')
    item('COMP', 'AS7341 spectral sensor', 0.02, 10, 2,
         'Rock characterization, 11 channels')

    # === ROBOTIC ARMS (x2, redundant) + WAAM PRINTING ===
    item('ARMS', 'Arm assembly (3-DOF + gripper)', 1.5, 2000, 2,
         'Stepper motors, Al linkage, 30cm reach')
    item('ARMS', 'WAAM print head (arc + wire feed)', 0.3, 400, 2,
         'MIG-style: motor + 2 rollers + nozzle + arc tip')
    item('ARMS', 'Seed wire spool (0.5mm Cu, 200m)', 0.3, 50, 1,
         'Initial cathode wire for electroforming')
    item('ARMS', 'Tool heads (gripper/driver/probe)', 0.15, 200, 2,
         'Swappable magnetic mount')
    item('ARMS', 'Vacuum lubricant (Braycote 601)', 0.05, 100, 2,
         'Bearings + joints')
    item('ARMS', 'Arm cable harness', 0.1, 100, 2,
         'Motor + encoder + power')

    # === CHEMISTRY PACKAGE ===
    item('CHEM', 'Kapton+Kevlar membrane (3m rated)', 8.0, 1500, 1,
         '55 m2, spring-loaded spool')
    item('CHEM', 'Mylar concentrator (2 m2)', 0.4, 200, 1,
         'Aluminized Mylar on Al frame')
    item('CHEM', 'Spare Mylar concentrator (2 m2)', 0.4, 200, 1,
         'Expansion / replacement')
    item('CHEM', 'Copper seed tape (25m roll)', 0.1, 50, 1,
         'Cathode seed for electrodeposition')
    item('CHEM', 'NdFeB permanent magnet', 0.1, 20, 1,
         'For future Stirling engine build')

    # === FLUID SYSTEM (oversized for growth) ===
    item('FLUID', 'Peristaltic pump (2000 L/hr)', 2.5, 2500, 1,
         'Acid-rated, oversized for 5m operations')
    item('FLUID', 'Spare pump head + hoses', 1.0, 800, 1,
         'Hot-swap replacement, acid-resistant')
    item('FLUID', 'PTFE tubing + fittings (10m)', 0.8, 400, 1,
         'Acid-resistant fluid path')
    item('FLUID', 'Collapsible bladder (200L)', 0.4, 200, 1,
         'Acid-resistant drain storage')
    item('FLUID', 'Flow + pressure sensors', 0.1, 300, 1,
         'Fluid system health monitoring')

    # === ELECTRO-WINNING CELL ===
    item('EWIN', 'Lead alloy anode (Pb-Sn-Ca)', 1.5, 200, 1,
         'Standard electro-winning anode')
    item('EWIN', 'SS cathode blanks (10 pack)', 1.0, 150, 1,
         'Reusable, iron peels off')
    item('EWIN', 'DC-DC converter (2V, 500A)', 0.3, 500, 1,
         'Panel voltage -> cell voltage')
    item('EWIN', 'Electrode mounting frame', 0.3, 100, 1,
         'Positions electrodes in solution')

    # === BIOLOGY ===
    item('BIO', 'Freeze-dried bacteria (4 species)', 0.2, 500, 1,
         'A.ferrox, A.thiox, L.ferrox, C.violaceum')
    item('BIO', 'Nutrient salts + trace minerals', 0.3, 150, 1,
         '(NH4)2SO4, K2HPO4, MgSO4, FeSO4')
    item('BIO', 'Backup culture vials (sealed)', 0.1, 200, 1,
         '10 vials, deep-frozen backup')
    item('BIO', 'pH + temperature sensors', 0.05, 100, 1,
         'Bioleaching health monitoring')

    # === PRINTER BOT SEED PARTS (Earth-origin components) ===
    item('BOTS', 'SG90 servo tray (50 units)', 0.45, 15, 1,
         'Enough for 6 bots + spares. $0.30 each.')
    item('BOTS', 'ESP32/RP2040 tray (10 units)', 0.03, 50, 1,
         'Bot brains. $5 each.')
    item('BOTS', 'NdFeB magnet discs (80 units)', 0.16, 16, 1,
         '8 per bot foot pad, 10 bots worth')
    item('BOTS', 'Wire feed roller bearings (20)', 0.04, 10, 1,
         'For WAAM print heads, 2 per bot')

    # === MISCELLANEOUS ===
    item('MISC', 'Silicone gaskets + sealant', 0.4, 200, 1,
         'Aperture seal, joint seals')
    item('MISC', 'MLI thermal blanket', 0.3, 500, 1,
         'Multi-layer insulation')
    item('MISC', 'Wiring harness (main bus)', 0.5, 300, 1,
         'Power + data backbone')
    item('MISC', 'Fasteners + brackets (SS)', 0.2, 100, 1,
         'Stainless steel')

    # --- Generate report ---
    lines.append("=" * 90)
    lines.append("  SEED MOTHERSHIP: COMPLETE BILL OF MATERIALS")
    lines.append("  \"Microwave oven that grows into a space station\"")
    lines.append("=" * 90)
    lines.append("")

    subsys_names = {
        'STRUCT': 'STRUCTURE',
        'POWER': 'POWER SYSTEM',
        'PROP': 'PROPULSION',
        'COMP': 'COMPUTE + COMMS',
        'ARMS': 'ROBOTIC ARMS (x2, redundant)',
        'CHEM': 'CHEMISTRY PACKAGE',
        'FLUID': 'FLUID SYSTEM (oversized for growth)',
        'EWIN': 'ELECTRO-WINNING CELL',
        'BIO': 'BIOLOGY',
        'BOTS': 'PRINTER BOT PARTS (Earth-origin seeds)',
        'MISC': 'MISCELLANEOUS',
    }

    subsystems = {}
    for subsys, name, mass, cost, qty, notes in bom:
        if subsys not in subsystems:
            subsystems[subsys] = []
        subsystems[subsys].append((name, mass, cost, qty, notes))

    grand_mass = 0
    grand_cost = 0

    for key in ['STRUCT', 'POWER', 'PROP', 'COMP', 'ARMS',
                'CHEM', 'FLUID', 'EWIN', 'BIO', 'BOTS', 'MISC']:
        items = subsystems[key]
        sub_mass = sum(m for _, m, _, _, _ in items)
        sub_cost = sum(c for _, _, c, _, _ in items)
        grand_mass += sub_mass
        grand_cost += sub_cost

        lines.append(
            f"--- {subsys_names[key]} ({sub_mass:.1f} kg, ${sub_cost:,.0f}) ---")
        for name, mass, cost, qty, notes in items:
            lines.append(
                f"  {name:<42} {mass:>5.1f} kg  ${cost:>8,.0f}  {notes}")
        lines.append("")

    lines.append("=" * 90)
    lines.append(f"  TOTAL HARDWARE: {grand_mass:.1f} kg  ${grand_cost:,.0f}")
    lines.append("=" * 90)
    lines.append("")

    # Physical dimensions
    lines.append("PHYSICAL SIZE:")
    lines.append(f"  Stowed:    ~50 x 35 x 30 cm (carry-on suitcase)")
    lines.append(f"  Volume:    ~50 liters (~24U CubeSat)")
    lines.append(f"  Mass:      {grand_mass:.1f} kg")
    lines.append(f"  Deployed:  ~5m tip-to-tip (solar wings)")
    lines.append(f"             2x 30cm arms on opposite sides")
    lines.append(f"             Membrane wraps up to 3m rock")
    lines.append(f"             Concentrator: 2 m2 (1.4 x 1.4m)")
    lines.append("")

    # Propulsion
    m_dry = grand_mass - 5.0 - 0.5  # subtract propellant
    m_wet = grand_mass
    isp = 2200
    ve = isp * 9.81
    dv = ve * math.log(m_wet / m_dry)

    lines.append("PROPULSION BUDGET:")
    lines.append(f"  Dry mass:     {m_dry:.1f} kg")
    lines.append(f"  Ion fuel:     5.0 kg iodine (solid, easy storage)")
    lines.append(f"  Attitude:     0.5 kg N2 (cold gas)")
    lines.append(f"  Ion Isp:      {isp} s")
    lines.append(f"  Delta-V:      {dv:.0f} m/s ({dv/1000:.1f} km/s)")
    lines.append(f"  Strategy:     Rideshare to GTO, ion spiral to NEA")
    lines.append("")

    # Power budget
    pv_watts = 4.0 * 1361 * 0.20  # 4 m2 at 20% eff
    lines.append("POWER BUDGET:")
    lines.append(f"  Solar panels: 4 m2 = {pv_watts:.0f}W at 1 AU")
    lines.append(f"  E-winning:    {pv_watts:.0f}W / 2V = {pv_watts/2:.0f}A")
    lines.append(f"  Deposition:   {pv_watts/2 * 0.02496:.0f} kg/day")
    lines.append(f"  Wire stock:   {pv_watts/2 * 0.02496:.0f} kg/day (electroformed inside bag)")
    lines.append(f"  WAAM print:   ~0.5 kg/hr at 1.1 kW (arc melts wire, builds shapes)")
    lines.append(f"  After arms WAAM-print Stirling: power scales with concentrators")
    lines.append("")

    # Launch costs
    rideshare = grand_mass * 10000
    dedicated = 2500000
    total_budget = grand_cost + rideshare
    total_premium = grand_cost + dedicated

    lines.append("MISSION COST:")
    lines.append(f"  Hardware:            ${grand_cost:>12,.0f}")
    lines.append(f"  Launch (rideshare):  ${rideshare:>12,.0f}  "
                 f"({grand_mass:.0f} kg x $10K/kg)")
    lines.append(f"  Launch (dedicated):  ${dedicated:>12,.0f}  (Electron-class)")
    lines.append(f"  ---")
    lines.append(f"  TOTAL (budget):      ${total_budget:>12,.0f}")
    lines.append(f"  TOTAL (premium):     ${total_premium:>12,.0f}")
    lines.append("")

    # Cost breakdown pie
    hw_pct = grand_cost / total_budget * 100
    launch_pct = rideshare / total_budget * 100
    lines.append("COST BREAKDOWN (budget path):")
    lines.append(f"  Hardware:  {hw_pct:.0f}% (dominated by solar panels + ion engine)")
    lines.append(f"  Launch:    {launch_pct:.0f}%")
    lines.append(f"  Ion engine + panels = ${120000 + 80000:,} "
                 f"({(120000 + 80000) / grand_cost * 100:.0f}% of hardware)")
    lines.append(f"  Everything else = ${grand_cost - 120000 - 80000:,} "
                 f"({(grand_cost - 120000 - 80000) / grand_cost * 100:.0f}% of hardware)")
    lines.append("")

    # Comparison
    lines.append("COMPARISON:")
    lines.append(f"  This mission:    {grand_mass:.0f} kg   ${total_budget/1e6:.1f}M (rideshare)")
    lines.append(f"  OSIRIS-REx:     2,110 kg   $800M  (returned 121g of sample)")
    lines.append(f"  Hayabusa2:      609 kg   $150M  (returned 5.4g of sample)")
    lines.append(f"  Psyche:         2,608 kg   $985M  (flyby only, no mining)")
    lines.append(f"  Our seed:        {grand_mass:.0f} kg   ${total_budget/1e6:.1f}M"
                 f"  (MINES the asteroid, grows forever)")
    lines.append("")
    lines.append("  At year 3: processing 10m rocks (500 tonnes each)")
    lines.append("  At year 10: $1.4 billion in extracted metals")
    lines.append("  At year 50: $8.5 billion, 16-chamber station")
    lines.append("=" * 90)

    return "\n".join(lines)


if __name__ == "__main__":
    print(generate_bom_report())
