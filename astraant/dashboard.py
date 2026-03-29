"""AstraAnt Web Dashboard -- Streamlit-based GUI for all analysis commands.

Launch with: streamlit run astraant/dashboard.py
Or: astraant dashboard
"""

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from astraant.catalog import Catalog
from astraant.configs import load_all_ant_configs, compute_ant_mass, compute_ant_power, compute_ant_cost
from astraant.feasibility import MissionConfig, SwarmConfig, analyze_mission, format_report
from astraant.mission_economics import calculate_site_economics, format_economics_report
from astraant.reality_check import reality_check
from astraant.readiness import assess_mission, format_readiness_report
from astraant.composition import simulate_mining_variability, format_variability_report
from astraant.manufacturing import plan_manufacturing, format_manufacturing_report
from astraant.price_tracker import price_health_report
from astraant.mission_planner import plan_mission, format_mission_plan, OBJECTIVES
from astraant.phase2 import plan_phase2, format_phase2_report, FACILITIES
from astraant.launch_planner import plan_single_launch, format_manifest
from astraant.endgame import HabitatGoal, format_endgame_report
from astraant.orbits import get_orbital_state, analyze_redirection, format_orbital_report


st.set_page_config(page_title="AstraAnt Dashboard", page_icon="ant", layout="wide")

st.title("AstraAnt -- Asteroid Mining Feasibility Dashboard")
st.caption("Ant Swarm Asteroid Mining Simulator & Feasibility Tracker | 100 tests, 22 CLI commands")

# Sidebar
st.sidebar.header("Mission Parameters")
asteroid = st.sidebar.selectbox("Target Asteroid",
    ["bennu", "ryugu", "itokawa", "eros", "2008_ev5", "didymos", "psyche"])
destination = st.sidebar.selectbox("Destination",
    ["lunar_orbit", "mars_orbit", "earth_return"])
track = st.sidebar.selectbox("Extraction Track",
    ["bioleaching", "mechanical", "hybrid"],
    format_func=lambda x: {"mechanical": "Mechanical", "bioleaching": "Bioleaching", "hybrid": "Hybrid"}[x])
workers = st.sidebar.slider("Workers", 10, 500, 100)
mission_years = st.sidebar.slider("Mission Lifetime (years)", 1, 20, 5)
power = st.sidebar.selectbox("Power Source",
    ["solar", "nuclear_10kw", "nuclear_40kw"])
fanciful = st.sidebar.checkbox("Fanciful Findings Mode", value=False)

catalog = Catalog()
taskmasters = max(1, workers // 20)
surface_ants = max(1, workers // 50)

# Tabs
tabs = st.tabs([
    "Mission Plan", "Feasibility", "Economics", "Catalog",
    "Composition", "Manufacturing", "Phase 2", "Launch",
    "Orbit", "Endgame", "Readiness", "Prices"
])

with tabs[0]:  # Mission Plan
    st.header("Mission Planner")
    objective = st.selectbox("Objective", [o.id for o in OBJECTIVES],
                              format_func=lambda x: next(o.name for o in OBJECTIVES if o.id == x))
    if st.button("Plan Mission"):
        result = plan_mission(objective)
        st.code(format_mission_plan(result))

with tabs[1]:  # Feasibility
    st.header("Feasibility Analysis")
    mission = MissionConfig(
        swarm=SwarmConfig(workers=workers, taskmasters=taskmasters,
                          surface_ants=surface_ants, track=track),
        asteroid_id=asteroid, destination=destination,
    )
    report = analyze_mission(mission, catalog)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Mass", f"{report.mass_budget.total_with_margin_kg:.0f} kg")
    with col2:
        st.metric("Total Cost", f"${report.cost_estimate.total_first_cycle_usd:,.0f}")
    with col3:
        be = report.break_even_cycles
        st.metric("Break-Even", f"{be} cycles" if be > 0 else "NEVER")
    with st.expander("Full Report"):
        st.code(format_report(report))

with tabs[2]:  # Economics
    st.header(f"Site Economics: {asteroid.upper()}")
    econ = calculate_site_economics(asteroid, destination, track,
                                     workers=workers, mission_years=mission_years)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Revenue", f"${econ.total_revenue_usd:,.0f}")
    with col2:
        st.metric("Cost", f"${econ.total_mission_cost_usd:,.0f}")
    with col3:
        st.metric("ROI", f"{econ.roi_pct:,.0f}%")
    if econ.revenue_by_material:
        st.subheader("Revenue by Material")
        rev_data = {k: v for k, v in econ.revenue_by_material.items() if v > 0}
        st.bar_chart(rev_data)
    with st.expander("Full Report"):
        st.code(format_economics_report(econ))
    with st.expander("Reality Check"):
        st.code(reality_check(econ))

with tabs[3]:  # Catalog
    st.header("Component Catalog")
    cat_tab = st.radio("Category", ["Parts", "Asteroids", "Species", "Tools"])
    if cat_tab == "Parts":
        for p in catalog.parts:
            price = p.best_price()
            st.text(f"{p.id:30s} {p.get('category', '?'):15s} "
                    f"{'$'+str(price) if price else '?'}")
    elif cat_tab == "Asteroids":
        for a in catalog.asteroids:
            dv = a.get("mining_relevance", {}).get("accessibility", {}).get("delta_v_from_leo_km_per_s", "?")
            st.text(f"{a.get('name', a.id):25s} dv={dv}  "
                    f"Water: {'Yes' if a.get('mining_relevance', {}).get('water_availability') else 'No'}")
    elif cat_tab == "Species":
        for s in catalog.species:
            st.text(f"{s.id:40s} {', '.join(s.get('extraction', {}).get('target_metals', []))}")
    elif cat_tab == "Tools":
        import yaml
        tools_dir = Path(__file__).parent.parent / "catalog" / "tools"
        for f in sorted(tools_dir.glob("*.yaml")):
            with open(f) as fh:
                t = yaml.safe_load(fh)
            st.text(f"{t.get('id', '?'):20s} {t.get('type', '?'):18s} "
                    f"{t.get('physical', {}).get('total_mass_g', '?')}g")

with tabs[4]:  # Composition
    st.header("Composition Variability")
    n_batches = st.slider("Batches", 50, 500, 200)
    if st.button("Analyze Composition"):
        result = simulate_mining_variability(asteroid, n_batches=n_batches)
        st.code(format_variability_report(result))
        if result.get("zone_distribution"):
            st.bar_chart(result["zone_distribution"])

with tabs[5]:  # Manufacturing
    st.header("In-Situ Manufacturing")
    if st.button("Generate Plan"):
        econ = calculate_site_economics(asteroid, "lunar_orbit", track,
                                         workers=workers, mission_years=mission_years)
        excess = {
            "iron": econ.metals_extracted_kg.get("iron", 0) * 0.8,
            "nickel": econ.metals_extracted_kg.get("nickel", 0) * 0.8,
            "copper": econ.metals_extracted_kg.get("copper", 0) * 0.8,
            "waste_paste": econ.total_regolith_processed_kg * 0.7,
            "water": max(0, econ.total_water_recovered_kg - 300),
        }
        plan = plan_manufacturing(excess)
        st.code(format_manufacturing_report(plan, excess))

with tabs[6]:  # Phase 2
    st.header("Phase 2 Facilities")
    all_fac = st.checkbox("All Facilities", value=True)
    fac_ids = [f.id for f in FACILITIES] if all_fac else ["fuel_depot", "bioreactor_farm", "comms_relay"]
    plan = plan_phase2(fac_ids)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Equipment Mass", f"{plan.total_equipment_mass_kg:,.0f} kg")
    with col2:
        st.metric("Total Cost", f"${plan.total_cost_usd:,.0f}")
    with col3:
        st.metric("Annual Revenue", f"${plan.total_annual_revenue_usd:,.0f}")
    with st.expander("Full Report"):
        econ = calculate_site_economics(asteroid, destination, track, workers=workers)
        st.code(format_phase2_report(plan, phase1_revenue=econ.total_revenue_usd))

with tabs[7]:  # Launch
    st.header("Single-Launch Manifest")
    manifest = plan_single_launch(workers=workers, include_phase2=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Payload", f"{manifest.total_mass_kg:,.0f} kg")
    with col2:
        st.metric("Margin", f"{manifest.margin_pct:.0f}%")
    with col3:
        fits = "YES" if manifest.margin_kg >= 0 else "NO"
        st.metric("Fits in Starship", fits)
    with st.expander("Full Manifest"):
        st.code(format_manifest(manifest))

with tabs[8]:  # Orbit
    st.header("Orbital Analysis")
    date = st.text_input("Date (YYYY-MM-DD)", "2032-01-01")
    motherships = st.slider("Motherships for redirection", 1, 100, 16)
    state = get_orbital_state(asteroid, date)
    redir = analyze_redirection(asteroid, n_motherships=motherships, power_source=power)
    if state:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Distance", f"{state.heliocentric_distance_au:.2f} AU")
        with col2:
            st.metric("Solar Power", f"{state.solar_power_factor:.2f}x")
        with col3:
            st.metric("Delta-v (5yr)", f"{redir.delta_v_m_per_s*1000:.1f} mm/s")
        st.code(format_orbital_report(state, redir))

with tabs[9]:  # Endgame
    st.header("Endgame: Rotating Habitat")
    target_r = st.slider("Target Radius (m)", 5, 300, 224)
    target_l = st.slider("Target Length (m)", 10, 500, 200)
    goal = HabitatGoal(target_radius_m=target_r, target_length_m=target_l)
    st.metric("Total Sections", len(goal.sections))
    st.metric("Target Gravity", f"1.0g at {goal.rpm} RPM")
    with st.expander("Habitat Report"):
        st.code(format_endgame_report(goal))

with tabs[10]:  # Readiness
    st.header("Readiness Assessment")
    readiness_report = assess_mission(catalog, track=track)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Score", f"{readiness_report.readiness_score}/100")
    with col2:
        st.metric("Items", len(readiness_report.items))
    st.bar_chart(readiness_report.summary)
    with st.expander("Full Report"):
        st.code(format_readiness_report(readiness_report))

with tabs[11]:  # Prices
    st.header("Price Health Check")
    st.code(price_health_report(catalog))
