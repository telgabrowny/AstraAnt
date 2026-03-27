"""AstraAnt Web Dashboard — Streamlit-based GUI for all analysis commands.

Launch with: streamlit run astraant/dashboard.py
Or: astraant dashboard
"""

import streamlit as st
import sys
from pathlib import Path

# Add project root to path
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


st.set_page_config(page_title="AstraAnt Dashboard", page_icon="🐜", layout="wide")

st.title("AstraAnt -- Asteroid Mining Feasibility Dashboard")
st.caption("Ant Swarm Asteroid Mining Simulator & Feasibility Tracker")

# Sidebar: mission parameters
st.sidebar.header("Mission Parameters")
asteroid = st.sidebar.selectbox("Target Asteroid", ["bennu", "ryugu", "itokawa", "eros", "2008_ev5", "didymos", "psyche"])
destination = st.sidebar.selectbox("Destination", ["lunar_orbit", "mars_orbit", "earth_return"])
track = st.sidebar.selectbox("Extraction Track", ["b", "a", "c"], format_func=lambda x: {"a": "A (Mechanical)", "b": "B (Bioleaching)", "c": "C (Hybrid)"}[x])
workers = st.sidebar.slider("Workers", 10, 500, 100)
taskmasters = st.sidebar.slider("Taskmasters", 1, 25, max(1, workers // 20))
surface_ants = st.sidebar.slider("Surface Ants", 1, 10, 3)
mission_years = st.sidebar.slider("Mission Lifetime (years)", 1, 20, 5)

catalog = Catalog()

# Tabs
tab_feasibility, tab_economics, tab_catalog, tab_composition, tab_manufacturing, tab_readiness, tab_prices = st.tabs([
    "Feasibility", "Economics", "Catalog", "Composition", "Manufacturing", "Readiness", "Prices"
])

with tab_feasibility:
    st.header("Feasibility Analysis")
    mission = MissionConfig(
        swarm=SwarmConfig(workers=workers, taskmasters=taskmasters,
                          surface_ants=surface_ants, track=track),
        asteroid_id=asteroid, destination=destination,
    )
    report = analyze_mission(mission, catalog)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Mass (with margin)", f"{report.mass_budget.total_with_margin_kg:.0f} kg")
        st.metric("Swarm Hardware", f"${report.cost_estimate.swarm_hardware_usd:,.0f}")
    with col2:
        st.metric("Launch Cost", f"${report.cost_estimate.launch_cost_usd:,.0f}")
        st.metric("Total 1st Cycle", f"${report.cost_estimate.total_first_cycle_usd:,.0f}")
    with col3:
        st.metric("Revenue/Cycle", f"${report.revenue_per_cycle_usd:,.0f}")
        be = report.break_even_cycles
        st.metric("Break-Even", f"{be} cycles" if be > 0 else "NEVER")

    with st.expander("Full Report"):
        st.code(format_report(report))

with tab_economics:
    st.header(f"5-Year Site Economics: {asteroid.upper()}")

    econ = calculate_site_economics(
        asteroid_id=asteroid, destination=destination, track=track,
        workers=workers, taskmasters=taskmasters, surface_ants=surface_ants,
        mission_years=mission_years,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Regolith Processed", f"{econ.total_regolith_processed_kg:,.0f} kg")
        st.metric("Water Recovered", f"{econ.total_water_recovered_kg:,.0f} kg")
    with col2:
        st.metric("Total Revenue", f"${econ.total_revenue_usd:,.0f}")
        st.metric("Total Cost", f"${econ.total_mission_cost_usd:,.0f}")
    with col3:
        st.metric("Net Profit", f"${econ.net_profit_usd:,.0f}")
        st.metric("ROI", f"{econ.roi_pct:,.0f}%")

    if econ.revenue_by_material:
        st.subheader("Revenue by Material")
        rev_data = {k: v for k, v in econ.revenue_by_material.items() if v > 0}
        st.bar_chart(rev_data)

    with st.expander("Full Economics Report"):
        st.code(format_economics_report(econ))

    with st.expander("Reality Check (Hidden Costs)"):
        st.code(reality_check(econ))

with tab_catalog:
    st.header("Component Catalog")

    cat_tab1, cat_tab2, cat_tab3, cat_tab4 = st.tabs(["Parts", "Asteroids", "Species", "Tools"])

    with cat_tab1:
        st.subheader(f"{len(catalog.parts)} Parts")
        for p in catalog.parts:
            price = p.best_price()
            st.text(f"{p.id:30s} {p.get('category', '?'):15s} ${price:.2f}" if price else f"{p.id}: no price")

    with cat_tab2:
        st.subheader(f"{len(catalog.asteroids)} Asteroids")
        for a in catalog.asteroids:
            dv = a.get("mining_relevance", {}).get("accessibility", {}).get("delta_v_from_leo_km_per_s", "?")
            water = "Yes" if a.get("mining_relevance", {}).get("water_availability") else "No"
            conf = a.get("composition", {}).get("confidence", "?")
            st.text(f"{a.get('name', a.id):25s} dv={dv} km/s  Water: {water}  Confidence: {conf}")

    with cat_tab3:
        st.subheader(f"{len(catalog.species)} Species")
        for s in catalog.species:
            targets = s.get("extraction", {}).get("target_metals", [])
            st.text(f"{s.id:40s} {s.get('type', '?'):10s} {', '.join(targets)}")

    with cat_tab4:
        st.subheader("Tool Heads")
        import yaml
        tools_dir = Path(__file__).parent.parent / "catalog" / "tools"
        for f in sorted(tools_dir.glob("*.yaml")):
            with open(f) as fh:
                t = yaml.safe_load(fh)
            mass = t.get("physical", {}).get("total_mass_g", "?")
            cost = t.get("cost_usd", "?")
            st.text(f"{t.get('id', '?'):20s} {t.get('type', '?'):18s} {mass}g  ${cost}")

with tab_composition:
    st.header(f"Composition Variability: {asteroid.upper()}")
    n_batches = st.slider("Mining batches to simulate", 50, 500, 200)

    if st.button("Run Variability Analysis"):
        result = simulate_mining_variability(asteroid, n_batches=n_batches)
        st.code(format_variability_report(result))

        # Zone distribution chart
        if result.get("zone_distribution"):
            st.subheader("Zone Distribution")
            st.bar_chart(result["zone_distribution"])

with tab_manufacturing:
    st.header("In-Situ Manufacturing Plan")
    st.caption("What to build from excess extracted materials")

    if st.button("Generate Manufacturing Plan"):
        econ = calculate_site_economics(asteroid, "lunar_orbit", track,
                                         workers=workers, mission_years=mission_years)
        excess = {
            "iron": econ.metals_extracted_kg.get("iron", 0) * 0.8,
            "nickel": econ.metals_extracted_kg.get("nickel", 0) * 0.8,
            "copper": econ.metals_extracted_kg.get("copper", 0) * 0.8,
            "cobalt": econ.metals_extracted_kg.get("cobalt", 0) * 0.8,
            "waste_paste": econ.total_regolith_processed_kg * 0.7,
            "water": max(0, econ.total_water_recovered_kg - 300),
        }
        plan = plan_manufacturing(excess)
        st.code(format_manufacturing_report(plan, excess))

with tab_readiness:
    st.header("Readiness Assessment")
    readiness_report = assess_mission(catalog, track=track)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Readiness Score", f"{readiness_report.readiness_score}/100")
    with col2:
        st.metric("Items Assessed", len(readiness_report.items))

    # Summary bar
    summary = readiness_report.summary
    st.bar_chart(summary)

    with st.expander("Full Readiness Report"):
        st.code(format_readiness_report(readiness_report))

with tab_prices:
    st.header("Price Health Check")
    st.code(price_health_report(catalog))
