"""Readiness assessment framework — classifies every mission aspect by maturity level.

Every component, subsystem, and design decision is classified as:
- PROVEN: Real parts, tested designs. Can order/build today.
- NEEDS_PHYSICAL_TEST: Must build and test before flight commitment.
- NEEDS_SIM_VALIDATION: Our simulator can answer this question.
- OPEN_RESEARCH: Needs more investigation, no clear answer yet.

This is the "billionaire check" — at any time, we can say exactly what's
ready to go, what needs lab work, what needs sim runs, and what's unknown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .catalog import Catalog
from .configs import load_all_ant_configs, load_all_mothership_modules


class ReadinessLevel(Enum):
    PROVEN = "PROVEN"
    NEEDS_PHYSICAL_TEST = "NEEDS_PHYSICAL_TEST"
    NEEDS_SIM_VALIDATION = "NEEDS_SIM_VALIDATION"
    OPEN_RESEARCH = "OPEN_RESEARCH"

    @property
    def label(self) -> str:
        return {
            "PROVEN": "[PROVEN]",
            "NEEDS_PHYSICAL_TEST": "[NEEDS TEST]",
            "NEEDS_SIM_VALIDATION": "[NEEDS SIM]",
            "OPEN_RESEARCH": "[RESEARCH]",
        }[self.value]


@dataclass
class ReadinessItem:
    """A single item in the readiness assessment."""
    category: str           # e.g., "component", "subsystem", "physics", "operations"
    name: str               # Human-readable name
    level: ReadinessLevel
    description: str        # What this item is
    rationale: str          # Why it has this readiness level
    test_plan: str = ""     # What test would move it to PROVEN (if not already)
    blockers: list[str] = field(default_factory=list)
    estimated_cost_usd: float = 0.0    # Rough cost to resolve (test equipment, lab time)
    estimated_time_weeks: float = 0.0  # Rough time to resolve


@dataclass
class ReadinessReport:
    """Complete readiness assessment."""
    items: list[ReadinessItem] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    def add(self, item: ReadinessItem) -> None:
        self.items.append(item)

    def compute_summary(self) -> None:
        self.summary = {}
        for level in ReadinessLevel:
            self.summary[level.value] = sum(1 for i in self.items if i.level == level)

    def by_level(self, level: ReadinessLevel) -> list[ReadinessItem]:
        return [i for i in self.items if i.level == level]

    def by_category(self, category: str) -> list[ReadinessItem]:
        return [i for i in self.items if i.category == category]

    @property
    def readiness_score(self) -> float:
        """0-100 score. 100 = everything proven."""
        if not self.items:
            return 0.0
        weights = {
            ReadinessLevel.PROVEN: 1.0,
            ReadinessLevel.NEEDS_PHYSICAL_TEST: 0.5,
            ReadinessLevel.NEEDS_SIM_VALIDATION: 0.3,
            ReadinessLevel.OPEN_RESEARCH: 0.1,
        }
        total = sum(weights[i.level] for i in self.items)
        return round(100 * total / len(self.items), 1)


def assess_components(catalog: Catalog) -> list[ReadinessItem]:
    """Assess readiness of individual components from the catalog."""
    items = []

    for part in catalog.parts:
        env = part.get("environmental", {})
        vacuum_ok = env.get("vacuum_compatible", False)
        sealed_ok = env.get("sealed_tunnel_compatible", True)
        rad_tol = env.get("radiation_tolerance", "none")

        # Determine readiness
        if vacuum_ok and rad_tol in ("moderate", "high"):
            level = ReadinessLevel.PROVEN
            rationale = "Space-rated component, vacuum and radiation tolerant."
            test_plan = "Standard acceptance testing."
        elif sealed_ok and rad_tol == "none":
            level = ReadinessLevel.NEEDS_PHYSICAL_TEST
            rationale = (
                "COTS component. Should work in sealed tunnel (1-10 kPa) but "
                "needs vacuum chamber testing to validate MTBF claims. "
                "Radiation tolerance unknown under regolith shielding."
            )
            test_plan = (
                "1) Vacuum chamber test at 5 kPa for 1000 hours to validate MTBF. "
                "2) Thermal cycling test (-40C to +85C, 100 cycles). "
                "3) If possible, radiation beam test to measure SEU rate."
            )
        elif not sealed_ok:
            level = ReadinessLevel.NEEDS_PHYSICAL_TEST
            rationale = "Component may not function in reduced pressure environment."
            test_plan = "Vacuum chamber test at target pressure to verify operation."
        else:
            level = ReadinessLevel.PROVEN
            rationale = "Standard component, compatible with operating environment."
            test_plan = ""

        # Check price staleness
        stale_days = part.days_since_price_check()
        price_note = ""
        if stale_days and stale_days > 180:
            price_note = f" Price data is {stale_days} days old -- needs refresh."

        items.append(ReadinessItem(
            category="component",
            name=f"{part.get('name', part.id)} ({part.id})",
            level=level,
            description=f"Category: {part.get('category', '?')}. "
                        f"Vacuum: {'yes' if vacuum_ok else 'no'}. "
                        f"Radiation: {rad_tol}.{price_note}",
            rationale=rationale,
            test_plan=test_plan,
            estimated_cost_usd=500 if level == ReadinessLevel.NEEDS_PHYSICAL_TEST else 0,
            estimated_time_weeks=2 if level == ReadinessLevel.NEEDS_PHYSICAL_TEST else 0,
        ))

    return items


def assess_subsystems() -> list[ReadinessItem]:
    """Assess readiness of major subsystems."""
    return [
        # -- Ant Castes --
        ReadinessItem(
            category="subsystem",
            name="Worker Ant -- Mechanical Design",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="6-legged spider chassis with SG90 servos, 3D-printed PETG frame.",
            rationale="Design exists on paper. Needs physical prototype to validate "
                      "locomotion, payload capacity, and tether management.",
            test_plan="1) 3D print chassis. 2) Assemble with SG90 servos. "
                      "3) Test locomotion on flat surface. 4) Test with full payload. "
                      "5) Test tether drag. Build time: 1 week.",
            estimated_cost_usd=100,
            estimated_time_weeks=2,
        ),
        ReadinessItem(
            category="subsystem",
            name="Worker Ant -- Firmware",
            level=ReadinessLevel.NEEDS_SIM_VALIDATION,
            description="MicroPython state machine on RP2040: dig/load/haul/dump cycle.",
            rationale="State machine designed but not implemented. Needs simulation to "
                      "validate timing, power consumption, and task throughput.",
            test_plan="1) Implement in MicroPython. 2) Run in sim to validate cycle time. "
                      "3) Flash onto real RP2040 Pico. 4) Test on physical prototype.",
            estimated_cost_usd=50,
            estimated_time_weeks=3,
        ),
        ReadinessItem(
            category="subsystem",
            name="Taskmaster Ant -- Navigation",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="IMU + visual odometry + lidar for tunnel navigation.",
            rationale="Sensor fusion for GPS-denied navigation is well-understood on Earth "
                      "but untested in tunnel environment with regolith dust and low lighting.",
            test_plan="1) Build sensor rig (BNO055 + OV7670 + VL53L0x). "
                      "2) Test in darkened tunnel analog (drainage pipe). "
                      "3) Measure position drift over 100m traverse. "
                      "4) Test with dust and vibration.",
            estimated_cost_usd=200,
            estimated_time_weeks=4,
        ),
        ReadinessItem(
            category="subsystem",
            name="Courier Ant -- Vacuum Operations",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="Vacuum-rated actuators, solar panel, thermal management on asteroid surface.",
            rationale="Courier operates in full vacuum with extreme thermal cycling. "
                      "Most expensive caste. Needs thermal vacuum chamber testing.",
            test_plan="1) Build courier prototype with Maxon actuators. "
                      "2) Thermal vacuum test (-150C to +150C). "
                      "3) Validate solar panel output. 4) Test sail deployment.",
            estimated_cost_usd=5000,
            estimated_time_weeks=8,
            blockers=["Requires access to thermal vacuum chamber (university lab or NASA facility)"],
        ),

        # -- Mothership --
        ReadinessItem(
            category="subsystem",
            name="Mothership -- Drill Module",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="Rotary percussion drill for asteroid regolith excavation.",
            rationale="Drilling in microgravity is fundamentally different from Earth. "
                      "No gravity to push the drill into the rock. Needs anchoring system "
                      "validation and thrust/counter-thrust management.",
            test_plan="1) Test drill head on regolith simulant (CI chondrite analog). "
                      "2) Parabolic flight or drop tower test for microgravity drilling. "
                      "3) Validate penetration rate estimates.",
            estimated_cost_usd=20000,
            estimated_time_weeks=12,
            blockers=["Regolith simulant procurement", "Microgravity test facility access"],
        ),
        ReadinessItem(
            category="subsystem",
            name="Mothership -- Solar Array",
            level=ReadinessLevel.PROVEN,
            description="Deployable GaAs solar array, 20 m^2, ~5.8 kW at 1 AU.",
            rationale="GaAs space solar arrays are mature technology. Alta Devices cells are "
                      "commercially available. Deployment mechanisms are well-understood.",
            test_plan="Standard deployment testing. Verify power output matches spec.",
            estimated_cost_usd=0,
            estimated_time_weeks=0,
        ),
        ReadinessItem(
            category="subsystem",
            name="Mothership -- Tunnel Sealing (Polymer Spray)",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="Silicone spray sealant applied to tunnel walls for 5 kPa pressurization.",
            rationale="Polymer spray sealing is standard on Earth but untested on asteroid "
                      "regolith surfaces. Adhesion, cure time, and leak rate on porous "
                      "rubble-pile material are unknown.",
            test_plan="1) Obtain asteroid regolith simulant. "
                      "2) Spray seal on simulant surface in vacuum chamber. "
                      "3) Pressurize to 5 kPa, measure leak rate over 72 hours. "
                      "4) Test at temperature extremes.",
            estimated_cost_usd=3000,
            estimated_time_weeks=4,
        ),
        ReadinessItem(
            category="subsystem",
            name="Mothership -- Tunnel Sealing (Sintering)",
            level=ReadinessLevel.OPEN_RESEARCH,
            description="Microwave sintering of regolith into ceramic tunnel lining.",
            rationale="NASA has studied microwave sintering of lunar regolith but asteroid "
                      "regolith has different composition (carbonaceous vs. basaltic). "
                      "Sintering parameters for C-type asteroid material are unknown.",
            test_plan="1) Literature review of regolith sintering by composition type. "
                      "2) Obtain CI/CM chondrite analog material. "
                      "3) Microwave sintering experiments at various powers/durations. "
                      "4) Measure resulting material strength and gas permeability.",
            estimated_cost_usd=10000,
            estimated_time_weeks=16,
            blockers=["Suitable regolith simulant for C-type asteroids"],
        ),
        ReadinessItem(
            category="subsystem",
            name="Mothership -- Communication System",
            level=ReadinessLevel.PROVEN,
            description="X-band high-gain antenna + CAN bus backbone + nRF24L01 local RF.",
            rationale="All three communication tiers use mature, proven technology. "
                      "X-band deep space comms are standard. CAN bus is automotive-proven. "
                      "nRF24L01 is commodity hardware.",
            test_plan="Integration test of all three tiers. Range test for RF in tunnel analog.",
            estimated_cost_usd=500,
            estimated_time_weeks=2,
        ),

        # -- Bioreactor --
        ReadinessItem(
            category="subsystem",
            name="Bioreactor -- Centrifuge Design",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="Rotating drum bioreactors for microgravity bioleaching.",
            rationale="Centrifuge bioreactors exist on Earth but have not been tested in "
                      "actual microgravity with bioleaching cultures. Bacterial growth in "
                      "centrifuge-simulated gravity may differ from static 1g.",
            test_plan="1) Build benchtop centrifuge bioreactor prototype. "
                      "2) Run A. ferrooxidans culture at 0.01-0.1g (clinostat). "
                      "3) Compare extraction kinetics to static 1g control. "
                      "4) ISS experiment proposal if clinostat results are promising.",
            estimated_cost_usd=15000,
            estimated_time_weeks=20,
            blockers=["Clinostat or rotating wall vessel for simulated microgravity",
                      "BSL-1 lab access for bacterial culture work"],
        ),
        ReadinessItem(
            category="subsystem",
            name="Bioreactor -- Bacterial Radiation Tolerance",
            level=ReadinessLevel.OPEN_RESEARCH,
            description="Long-term viability of bioleaching cultures under deep space radiation.",
            rationale="2m regolith + water jacket provides significant shielding, but "
                      "residual GCR dose over months/years on bacterial cultures is unstudied. "
                      "A. ferrooxidans LD50 is ~200 Gy but chronic low-dose effects are unknown.",
            test_plan="1) Literature review of chronic radiation effects on iron-oxidizing bacteria. "
                      "2) Gamma irradiation experiments at expected dose rates. "
                      "3) Measure culture viability and extraction efficiency post-irradiation.",
            estimated_cost_usd=8000,
            estimated_time_weeks=12,
            blockers=["Access to gamma irradiation facility"],
        ),

        # -- Return Vehicle --
        ReadinessItem(
            category="subsystem",
            name="Return Vehicle -- Solar Sail Transit",
            level=ReadinessLevel.OPEN_RESEARCH,
            description="25 m^2 CP1 solar sail carrying 100 kg cargo from NEA to lunar orbit.",
            rationale="Solar sail technology is proven (IKAROS, LightSail 2, NEA Scout) but "
                      "trajectory optimization for cargo delivery from NEA to lunar orbit with "
                      "this specific mass ratio has not been computed.",
            test_plan="1) Compute optimal sail trajectories for top 3 asteroid targets. "
                      "2) Validate with published low-thrust trajectory optimization tools. "
                      "3) Determine transit times and feasibility.",
            estimated_cost_usd=0,
            estimated_time_weeks=4,
        ),
        ReadinessItem(
            category="subsystem",
            name="Return Vehicle -- Lunar Orbit Capture",
            level=ReadinessLevel.NEEDS_SIM_VALIDATION,
            description="Solar sail deceleration for Earth-Moon L2 insertion.",
            rationale="Sail-based orbit insertion is theoretically possible but the "
                      "delta-v budget and maneuver timeline need simulation.",
            test_plan="Simulate approach trajectory and sail orientation schedule for L2 insertion.",
            estimated_cost_usd=0,
            estimated_time_weeks=2,
        ),

        # -- Sugar Production --
        ReadinessItem(
            category="subsystem",
            name="Sugar Production -- Algae Photobioreactor",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="200L Chlorella vulgaris photobioreactor with fiber optic solar illumination.",
            rationale="Chlorella cultivation is proven (ISS heritage, MELiSSA). "
                      "Fiber optic photobioreactors published since 1996. But integration "
                      "of both systems in asteroid-analog conditions is untested. "
                      "Sugar yield under nitrogen starvation needs validation.",
            test_plan="1) Build 10L bench prototype with fiber optic illumination. "
                      "2) Validate sugar yield under nitrogen starvation (target 0.5 g/L/day). "
                      "3) Test with CO2 from carbonate pyrolysis (simulated asteroid source). "
                      "4) Run for 60 days to assess long-term stability.",
            estimated_cost_usd=5000,
            estimated_time_weeks=10,
        ),
        ReadinessItem(
            category="subsystem",
            name="Sugar Production -- CO2 from Asteroid Carbonates",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="Thermal decomposition of asteroid carbonate minerals to produce CO2 for algae.",
            rationale="CaCO3 thermal decomposition is textbook chemistry. But asteroid "
                      "carbonates (dolomite, breunnerite) may behave differently than "
                      "pure calcite. Need to test with CI/CM chondrite analog material.",
            test_plan="1) Obtain CI chondrite analog material. "
                      "2) Heat samples to 700C, measure CO2 yield. "
                      "3) Verify CO2 purity (no toxic contaminants for algae). "
                      "4) Calculate kg regolith needed per kg CO2.",
            estimated_cost_usd=2000,
            estimated_time_weeks=4,
        ),
        ReadinessItem(
            category="subsystem",
            name="Sugar Production -- Fiber Optic Light Delivery",
            level=ReadinessLevel.PROVEN,
            description="Solar concentrator + fiber optic bundle delivering PAR to underground photobioreactor.",
            rationale="Fiber optic illuminated photobioreactors demonstrated by Hirata (1996), "
                      "Ogbonna (1999). Solar concentrators are mature tech. 60% light "
                      "transmission through 10m silica fiber is achievable.",
            test_plan="Standard validation: measure PAR at reactor end vs. concentrator input.",
            estimated_cost_usd=500,
            estimated_time_weeks=1,
        ),

        # -- Thermal Sorting --
        ReadinessItem(
            category="subsystem",
            name="Thermal Sorter -- Ice Recovery",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="Heated rotating drum separates water ice from regolith at 120C.",
            rationale="Thermal separation is simple engineering. But ice sublimation "
                      "behavior in low-pressure (5 kPa) environment with regolith matrix "
                      "needs validation. Recovery rate (90% target) is estimated.",
            test_plan="1) Build bench-scale heated drum (5L). "
                      "2) Test with regolith simulant + water ice mixture at 5 kPa. "
                      "3) Measure ice recovery rate and processing time. "
                      "4) Verify no volatile contamination in recovered water.",
            estimated_cost_usd=2000,
            estimated_time_weeks=4,
        ),

        # -- Waste Slurry Sealing --
        ReadinessItem(
            category="subsystem",
            name="Waste Slurry Tunnel Sealant",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="Bioreactor waste + water paste applied to tunnel walls as sealant.",
            rationale="Concept is sound (CaO traces act as cement, fine rock particles fill "
                      "pores). But actual seal effectiveness with depleted bioleaching waste "
                      "is untested. The 75% pressure retention estimate needs validation.",
            test_plan="1) Run bioleaching cycle on regolith simulant. "
                      "2) Collect waste slurry, mix with water to paste consistency. "
                      "3) Apply to rock surface in vacuum chamber at 5 kPa. "
                      "4) Measure pressure retention over 72 hours. "
                      "5) Test multiple coat layers.",
            estimated_cost_usd=3000,
            estimated_time_weeks=6,
            blockers=["Requires completed bioleaching test first (waste material needed)"],
        ),

        # -- Modular Tool System --
        ReadinessItem(
            category="subsystem",
            name="Modular Tool System -- Magnetic Mount",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="Universal magnetic clip tool mount between mandible arms. "
                        "4mm neodymium magnets, 3N pull force.",
            rationale="Magnetic tool attachment is common in manufacturing jigs. "
                      "But reliable attach/detach by a small robot in dusty conditions "
                      "needs validation. Regolith dust on magnets could reduce grip.",
            test_plan="1) 3D print mount + tool heads. 2) Test attach/detach cycles (1000x). "
                      "3) Test with simulated regolith dust contamination. "
                      "4) Measure grip force degradation over time.",
            estimated_cost_usd=100,
            estimated_time_weeks=2,
        ),
        ReadinessItem(
            category="subsystem",
            name="Modular Tool System -- Tool Heads (6 types)",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="3D-printable tool heads: drill, scoop, paste nozzle, "
                        "thermal rake, sampling probe, cargo gripper.",
            rationale="Each tool head has been designed with printable dimensions "
                      "and OpenSCAD parametric models. Physical testing needed to "
                      "validate fit, function, and durability.",
            test_plan="1) Print all 6 tool heads. 2) Test each on worker ant prototype. "
                      "3) Validate drill excavation rate, scoop capacity, paste flow, "
                      "rake heat resistance, probe sensor readings, gripper hold strength.",
            estimated_cost_usd=200,
            estimated_time_weeks=4,
        ),
        ReadinessItem(
            category="subsystem",
            name="Mandible Arms -- 2-DOF Manipulation",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="Two SG51R micro servos as mandible arms for tool operation.",
            rationale="Small micro servos for manipulation are common in hobby robotics. "
                      "Key unknown: can 1.5N grip force reliably hold tools during "
                      "vibration (drilling) and thermal exposure (sorting)?",
            test_plan="1) Build mandible arm prototype on worker chassis. "
                      "2) Test tool grip during drill motor vibration. "
                      "3) Test grip with paste nozzle squeeze operation. "
                      "4) Measure mandible servo lifetime under load.",
            estimated_cost_usd=50,
            estimated_time_weeks=2,
        ),

        # -- Exterior Maintenance --
        ReadinessItem(
            category="subsystem",
            name="Mothership -- Exterior Maintenance Infrastructure",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="Grip rails, tool docking points, and ant access features on mothership hull.",
            rationale="ISS EVA handrails are proven concept. Scaling down to ant-sized "
                      "robots with magnetic feet is novel. Grip reliability in thermal "
                      "cycling environment needs testing.",
            test_plan="1) Build mock hull section with grip rails and magnetic docking points. "
                      "2) Test courier ant prototype traversal on mock hull. "
                      "3) Thermal cycle test: -150C to +150C, verify grip rail integrity. "
                      "4) Test tool swap at docking points.",
            estimated_cost_usd=1000,
            estimated_time_weeks=4,
        ),
    ]


def assess_operations() -> list[ReadinessItem]:
    """Assess readiness of operational concepts."""
    return [
        ReadinessItem(
            category="operations",
            name="Ant Locomotion in Microgravity",
            level=ReadinessLevel.NEEDS_PHYSICAL_TEST,
            description="6-legged spider gait in microgravity tunnel environment.",
            rationale="In sealed tunnels with 5 kPa pressure, there is still near-zero gravity. "
                      "Ant legs must grip regolith surface to move. Untested whether SG90 "
                      "servos provide enough force for regolith traction.",
            test_plan="1) Test ant prototype on regolith simulant on Earth. "
                      "2) Calculate required traction force vs. available servo torque. "
                      "3) Parabolic flight test for microgravity validation. "
                      "4) Consider magnetic foot pads as backup traction method.",
            estimated_cost_usd=5000,
            estimated_time_weeks=6,
        ),
        ReadinessItem(
            category="operations",
            name="Swarm Coordination Protocol",
            level=ReadinessLevel.NEEDS_SIM_VALIDATION,
            description="Taskmaster-worker squad coordination, task allocation, fault recovery.",
            rationale="Swarm behavior with hierarchical control (taskmaster + workers) is "
                      "well-studied in simulation but our specific protocol needs validation.",
            test_plan="1) Implement in simulator. 2) Test with various failure scenarios. "
                      "3) Validate throughput scales linearly with squad count. "
                      "4) Test squad re-assignment when taskmaster fails.",
            estimated_cost_usd=0,
            estimated_time_weeks=3,
        ),
        ReadinessItem(
            category="operations",
            name="Mission Economics -- Break-Even Analysis",
            level=ReadinessLevel.NEEDS_SIM_VALIDATION,
            description="At what swarm size and mission cadence does each track become profitable?",
            rationale="Current feasibility calculator uses rough estimates. Needs detailed "
                      "simulation with realistic extraction rates, attrition, and consumables.",
            test_plan="Run full mission simulation across parameter space. Sensitivity analysis.",
            estimated_cost_usd=0,
            estimated_time_weeks=4,
        ),
        ReadinessItem(
            category="operations",
            name="Tunnel Expansion Rate",
            level=ReadinessLevel.NEEDS_SIM_VALIDATION,
            description="How fast can the tunnel network grow given swarm size and power budget?",
            rationale="Tunnel expansion determines how quickly the operation scales. "
                      "Depends on worker count, drill rate, sealing rate, and power availability.",
            test_plan="Simulate tunnel growth with varying swarm sizes and power constraints.",
            estimated_cost_usd=0,
            estimated_time_weeks=2,
        ),
        ReadinessItem(
            category="operations",
            name="Emergency Response Under Comm Delay",
            level=ReadinessLevel.NEEDS_SIM_VALIDATION,
            description="Can the autonomous system handle emergencies (pressure leak, culture crash) "
                        "without ground control input during the communication delay window?",
            rationale="With 5-30 minute comm delay, the mothership must handle emergencies "
                      "autonomously. Need to validate that the decision logic is robust.",
            test_plan="Inject failure scenarios in simulation and measure response time "
                      "and recovery success rate with no ground input.",
            estimated_cost_usd=0,
            estimated_time_weeks=3,
        ),
    ]


def assess_mission(catalog: Catalog | None = None, track: str = "mechanical") -> ReadinessReport:
    """Run complete readiness assessment for a mission."""
    if catalog is None:
        catalog = Catalog()

    report = ReadinessReport()

    # Component-level assessment
    for item in assess_components(catalog):
        report.add(item)

    # Subsystem-level assessment
    for item in assess_subsystems():
        report.add(item)

    # Operations-level assessment
    for item in assess_operations():
        report.add(item)

    report.compute_summary()
    return report


def format_readiness_report(report: ReadinessReport) -> str:
    """Format readiness report as human-readable text."""
    lines = []
    lines.append("=" * 70)
    lines.append("ASTRAANT READINESS ASSESSMENT")
    lines.append(f"Overall Readiness Score: {report.readiness_score}/100")
    lines.append("=" * 70)

    # Summary
    lines.append("\n--- SUMMARY ---")
    for level in ReadinessLevel:
        count = report.summary.get(level.value, 0)
        bar = "#" * count
        lines.append(f"  {level.label:<16s} {count:>3d}  {bar}")
    lines.append(f"  {'TOTAL':<16s} {len(report.items):>3d}")

    # By category
    categories = sorted(set(i.category for i in report.items))
    for cat in categories:
        cat_items = report.by_category(cat)
        lines.append(f"\n--- {cat.upper()} ---")
        for item in sorted(cat_items, key=lambda x: x.level.value):
            lines.append(f"  {item.level.label:<16s} {item.name}")
            lines.append(f"  {'':16s} {item.rationale}")
            if item.test_plan:
                lines.append(f"  {'':16s} Test: {item.test_plan[:100]}...")
            if item.blockers:
                for b in item.blockers:
                    lines.append(f"  {'':16s} BLOCKER: {b}")
            if item.estimated_cost_usd > 0:
                lines.append(f"  {'':16s} Est. cost: ${item.estimated_cost_usd:,.0f} | "
                             f"Time: {item.estimated_time_weeks:.0f} weeks")
            lines.append("")

    # Total cost to reach PROVEN
    test_items = report.by_level(ReadinessLevel.NEEDS_PHYSICAL_TEST)
    total_test_cost = sum(i.estimated_cost_usd for i in test_items)
    total_test_weeks = max((i.estimated_time_weeks for i in test_items), default=0)
    research_items = report.by_level(ReadinessLevel.OPEN_RESEARCH)
    total_research_cost = sum(i.estimated_cost_usd for i in research_items)

    lines.append("--- PATH TO FLIGHT READY ---")
    lines.append(f"  Physical testing needed:  {len(test_items)} items")
    lines.append(f"  Estimated test budget:    ${total_test_cost:,.0f}")
    lines.append(f"  Longest test timeline:    {total_test_weeks:.0f} weeks")
    lines.append(f"  Open research questions:  {len(research_items)} items")
    lines.append(f"  Estimated research budget: ${total_research_cost:,.0f}")
    lines.append(f"  Sim validation needed:    {report.summary.get('NEEDS_SIM_VALIDATION', 0)} items")
    lines.append("")
    lines.append("  To move from current state to flight-ready:")
    lines.append(f"    Budget needed: ~${total_test_cost + total_research_cost:,.0f}")
    lines.append(f"    Timeline: ~{total_test_weeks:.0f} weeks (parallel testing)")
    lines.append("=" * 70)

    return "\n".join(lines)
