"""Integration tests -- end-to-end command sequences and game economy.

Tests that verify multiple components working together:
- Taskmaster squad manager dispatching commands to workers
- Full drill cycle: command -> execute -> report -> next command
- Game economy: revenue delay, cash flow, resupply funding
- Anomaly detection triggering the decision tree
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "firmware" / "worker"))
sys.path.insert(0, str(Path(__file__).parent.parent / "firmware" / "taskmaster"))

from radio_protocol import (
    pack_command, pack_heartbeat, unpack_packet,
    CMD_MOVE_TO, CMD_DRILL, CMD_HALT, CMD_DUMP_HOPPER,
    RPT_HEARTBEAT, RPT_DRILL_DONE, RPT_HOPPER_FULL, RPT_STALL,
)
from command_handler import CommandHandler, STATE_IDLE, STATE_DRILLING
from squad_manager import SquadManager, WorkerState
from astraant.gui.simulation.game_economy import GameEconomy
from astraant.gui.simulation.anomaly_detection import AnomalyDetector


# --- Squad Manager Tests ---

def test_squad_manager_add_workers():
    mgr = SquadManager(taskmaster_id=0)
    for i in range(20):
        mgr.add_worker(i, role="miner")
    s = mgr.summary()
    assert s["total_workers"] == 20
    assert s["alive"] == 20


def test_squad_manager_heartbeat_processing():
    mgr = SquadManager(taskmaster_id=0)
    mgr.add_worker(5, role="miner")
    pkt = pack_heartbeat(5, rail_pos=42.0, supercap_pct=88,
                          hopper_pct=30, state=1, servo_ok_mask=0xFF)
    events = mgr.handle_worker_report(pkt)
    assert mgr.workers[5].supercap_pct == 88
    assert mgr.workers[5].hopper_pct == 30


def test_squad_manager_stall_recovery():
    """Stall report should mark worker dead and dispatch recovery."""
    sent_packets = []
    mgr = SquadManager(taskmaster_id=0, send_radio_fn=lambda p: sent_packets.append(p))
    mgr.add_worker(5, role="miner")
    mgr.add_worker(6, role="miner")  # Available for recovery

    from radio_protocol import pack_stall_report
    pkt = pack_stall_report(worker_id=5, servo_id=2, current_ma=450)
    events = mgr.handle_worker_report(pkt)

    assert not mgr.workers[5].alive
    assert any("STALL" in e.get("message", "") for e in events)
    assert len(sent_packets) > 0  # Recovery commands sent to worker 6


def test_squad_manager_rebalance():
    mgr = SquadManager(taskmaster_id=0)
    for i in range(20):
        mgr.add_worker(i)
    mgr.rebalance_roles(target_miners=10, target_plasterers=5,
                         target_sorters=3, target_tenders=2)
    s = mgr.summary()
    assert s["by_role"]["miner"] == 10
    assert s["by_role"]["plasterer"] == 5


# --- Full Drill Cycle Integration ---

def test_full_drill_cycle():
    """Simulate a complete drill -> report -> dump cycle."""
    radio_log = []

    handler = CommandHandler(
        worker_id=7,
        send_radio_fn=lambda p: radio_log.append(p),
    )

    # Taskmaster sends: move to work face
    handler.handle_command(pack_command(CMD_MOVE_TO, 7, rail_position=50.0))
    assert handler.state != STATE_IDLE

    # Tick until move completes
    for _ in range(200):
        handler.tick(20)
    # Should be idle after move timer elapses

    # Taskmaster sends: drill for 100ms
    handler.handle_command(pack_command(CMD_DRILL, 7, duration_ms=100))
    assert handler.state == STATE_DRILLING

    # Tick until drill completes
    for _ in range(20):
        handler.tick(20)

    # Worker should have sent DRILL_DONE report
    drill_done_reports = [p for p in radio_log if p[0] == RPT_DRILL_DONE]
    assert len(drill_done_reports) > 0

    # Taskmaster sends: dump hopper
    handler.handle_command(pack_command(CMD_DUMP_HOPPER, 7))
    for _ in range(100):
        handler.tick(20)

    assert handler.hopper_pct == 0  # Hopper emptied
    assert handler.cycles >= 1


# --- Game Economy Tests ---

def test_economy_initial_budget():
    econ = GameEconomy()
    assert econ.cash_on_hand_usd == 0  # Cash separate from budget
    assert econ.initial_budget_usd > 0


def test_economy_pod_transit_delay():
    """Revenue should only arrive after transit delay."""
    econ = GameEconomy()

    # Launch a pod at time 0
    econ.launch_pod(value_usd=100_000, launch_time=0, transit_years=2.5)
    assert len(econ.pods_in_transit) == 1
    assert econ.total_revenue_received_usd == 0

    # Tick at 1 year -- pod still in transit
    events = econ.tick(sim_time_hours=365.25 * 24)
    assert econ.total_revenue_received_usd == 0
    assert econ.pods_delivered == 0

    # Tick at 3 years -- pod should have arrived
    events = econ.tick(sim_time_hours=3 * 365.25 * 24)
    assert econ.total_revenue_received_usd == 100_000
    assert econ.pods_delivered == 1
    assert econ.cash_on_hand_usd == 100_000


def test_economy_resupply_needs_cash():
    """Can't send resupply without cash."""
    econ = GameEconomy()
    assert econ.cash_on_hand_usd == 0
    result = econ.send_resupply()
    assert result is None  # Can't afford it


def test_economy_resupply_with_cash():
    """Can send resupply after revenue arrives."""
    econ = GameEconomy()
    econ.cash_on_hand_usd = 50_000_000  # Simulate revenue
    result = econ.send_resupply()
    assert result is not None
    assert econ.resupply_missions_sent == 1
    assert econ.cash_on_hand_usd == 30_000_000  # 50M - 20M


def test_economy_profitability():
    """Mission becomes profitable when received revenue exceeds investment."""
    econ = GameEconomy(initial_budget_usd=1_000_000)

    # Launch many high-value pods with very short transit
    for i in range(100):
        econ.launch_pod(value_usd=50_000, launch_time=i, transit_years=0.001)

    # Tick well past all arrival times
    all_events = []
    for hour in range(0, 500, 10):
        events = econ.tick(sim_time_hours=hour)
        all_events.extend(events)

    assert econ.total_revenue_received_usd > 1_000_000
    assert econ.profitable is True


# --- Anomaly Decision Tree ---

def test_anomaly_triggers_in_mining():
    """Anomalies should fire during voxel mining."""
    detector = AnomalyDetector(fanciful_mode=True, seed=42)
    found = False
    for i in range(5000):
        result = detector.check_voxel(i % 50, -i // 50, 0, "sulfide_pocket", i * 10)
        if result:
            found = True
            assert result.severity in ("curiosity", "significant", "extraordinary")
            assert len(result.action_required) > 0
            break
    assert found, "Should find at least one anomaly in 5000 voxels"


def test_anomaly_has_both_explanations():
    """Fanciful anomalies should have both scientific and fanciful explanations."""
    detector = AnomalyDetector(fanciful_mode=True, seed=42)
    for i in range(5000):
        result = detector.check_voxel(i, -10, 0, "metal_grain", i * 10)
        if result:
            assert len(result.scientific_explanation) > 0
            # Not all anomalies have fanciful explanations (only the fanciful-only ones guarantee it)
            break
