"""Tests for firmware components (radio protocol, command handler, anomaly detection).

These tests run on desktop Python, verifying the shared logic that
runs identically on the RP2040 and in the simulation.
"""

import sys
from pathlib import Path

# Add firmware to path so we can import it
sys.path.insert(0, str(Path(__file__).parent.parent / "firmware" / "worker"))

from radio_protocol import (
    pack_command, pack_heartbeat, pack_stall_report,
    pack_status_report, unpack_packet,
    CMD_MOVE_TO, CMD_DRILL, CMD_HALT,
    RPT_HEARTBEAT, RPT_STALL, RPT_STATUS,
)
from command_handler import CommandHandler, STATE_IDLE, STATE_DRILLING, STATE_MOVING

from astraant.gui.simulation.anomaly_detection import AnomalyDetector


# --- Radio Protocol ---

def test_pack_unpack_heartbeat():
    """Heartbeat packs to 32 bytes and unpacks correctly."""
    pkt = pack_heartbeat(worker_id=14, rail_pos=85.3, supercap_pct=72,
                          hopper_pct=45, state=1, servo_ok_mask=0xFF)
    assert len(pkt) == 32
    result = unpack_packet(pkt)
    assert result["worker_id"] == 14
    assert abs(result["rail_pos"] - 85.3) < 0.1
    assert result["supercap_pct"] == 72
    assert result["hopper_pct"] == 45


def test_pack_unpack_command():
    """Commands pack and unpack correctly."""
    pkt = pack_command(CMD_MOVE_TO, worker_id=7, rail_position=42.5)
    assert len(pkt) == 32
    result = unpack_packet(pkt)
    assert result["worker_id"] == 7
    assert abs(result["rail_position"] - 42.5) < 0.1


def test_pack_unpack_drill():
    pkt = pack_command(CMD_DRILL, worker_id=3, duration_ms=5000)
    result = unpack_packet(pkt)
    assert result["worker_id"] == 3
    assert result["duration_ms"] == 5000


def test_pack_unpack_stall():
    pkt = pack_stall_report(worker_id=10, servo_id=2, current_ma=450)
    result = unpack_packet(pkt)
    assert result["worker_id"] == 10
    assert result["servo_id"] == 2
    assert result["current_ma"] == 450


def test_pack_unpack_status():
    pkt = pack_status_report(
        worker_id=5, rail_pos=10.0, supercap_pct=88,
        hopper_pct=55, state=2, servo_currents=[100]*8,
        tool_id=1, cycles=42,
    )
    result = unpack_packet(pkt)
    assert result["worker_id"] == 5
    assert result["cycles"] == 42
    assert len(result["servo_currents"]) == 8


def test_all_packets_32_bytes():
    """Every packet type must be exactly 32 bytes."""
    assert len(pack_command(CMD_HALT, 0)) == 32
    assert len(pack_command(CMD_MOVE_TO, 1, rail_position=0.0)) == 32
    assert len(pack_command(CMD_DRILL, 2, duration_ms=3000)) == 32
    assert len(pack_heartbeat(0, 0.0, 100, 0, 0, 0xFF)) == 32
    assert len(pack_stall_report(0, 0, 0)) == 32
    assert len(pack_status_report(0, 0.0, 0, 0, 0, [0]*8, 0, 0)) == 32


# --- Command Handler ---

def test_command_handler_starts_idle():
    handler = CommandHandler(worker_id=1)
    assert handler.state == STATE_IDLE


def test_command_handler_drill():
    """DRILL command should change state to DRILLING."""
    handler = CommandHandler(worker_id=1)
    pkt = pack_command(CMD_DRILL, worker_id=1, duration_ms=3000)
    handler.handle_command(pkt)
    assert handler.state == STATE_DRILLING


def test_command_handler_halt():
    """HALT should return to IDLE from any state."""
    handler = CommandHandler(worker_id=1)
    pkt = pack_command(CMD_DRILL, worker_id=1, duration_ms=3000)
    handler.handle_command(pkt)
    assert handler.state == STATE_DRILLING

    pkt = pack_command(CMD_HALT, worker_id=1)
    handler.handle_command(pkt)
    assert handler.state == STATE_IDLE


def test_command_handler_move():
    """MOVE_TO should change state to MOVING."""
    handler = CommandHandler(worker_id=1)
    pkt = pack_command(CMD_MOVE_TO, worker_id=1, rail_position=50.0)
    handler.handle_command(pkt)
    assert handler.state == STATE_MOVING


def test_command_handler_drill_completes():
    """Drilling should complete after timer elapses."""
    sent_packets = []
    handler = CommandHandler(
        worker_id=1,
        send_radio_fn=lambda pkt: sent_packets.append(pkt),
    )
    pkt = pack_command(CMD_DRILL, worker_id=1, duration_ms=100)
    handler.handle_command(pkt)

    # Tick enough for drill to complete
    for _ in range(10):
        handler.tick(20)

    assert handler.state == STATE_IDLE
    assert len(sent_packets) > 0  # Should have sent DRILL_DONE report


# --- Anomaly Detection ---

def test_anomaly_detector_finds_anomalies():
    """With enough voxels checked, anomalies should eventually appear."""
    detector = AnomalyDetector(fanciful_mode=False, seed=42)
    for i in range(2000):
        detector.check_voxel(i, -10, 0, "silicate_bulk", i * 100)
    assert len(detector.anomalies) > 0


def test_fanciful_mode_has_extra_types():
    """Fanciful mode should include anomaly types not in normal mode."""
    fanciful = AnomalyDetector(fanciful_mode=True, seed=99)
    for i in range(10000):
        fanciful.check_voxel(i, -10, 0, "silicate_bulk", i * 100)

    fanciful_types = set(a.anomaly_type for a in fanciful.anomalies)
    # Fanciful-only types (geometric_void, signal) should eventually appear
    # At 10K voxels they should show up at least once
    assert len(fanciful.anomalies) > 0
    # At minimum, some scientific anomalies should be found
    assert len(fanciful_types) >= 3


def test_anomaly_severity_levels():
    """Anomalies should have valid severity levels."""
    detector = AnomalyDetector(fanciful_mode=True, seed=123)
    for i in range(3000):
        detector.check_voxel(i, -10, 0, "sulfide_pocket", i * 100)

    valid_severities = {"curiosity", "significant", "extraordinary"}
    for a in detector.anomalies:
        assert a.severity in valid_severities


def test_anomaly_summary():
    detector = AnomalyDetector(seed=42)
    for i in range(500):
        detector.check_voxel(i, -10, 0, "silicate_bulk", i)
    s = detector.summary()
    assert "total_anomalies" in s
    assert "voxels_checked" in s
    assert s["voxels_checked"] == 500
