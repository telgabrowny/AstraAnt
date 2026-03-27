"""Tests for the headless simulation engine."""

from astraant.gui.simulation.sim_engine import SimEngine
from astraant.gui.simulation.mission_clock import MissionClock
from astraant.gui.simulation.comms_delay import CommsDelay
from astraant.gui.simulation.tunnel_state import TunnelNetwork
from astraant.gui.simulation.ant_agent import AntAgent, AntState, Position


def test_mission_clock():
    clock = MissionClock()
    clock.speed = 100.0
    sim_dt = clock.tick(1.0)  # 1 real second at 100x
    assert sim_dt == 100.0
    assert clock.sim_time == 100.0
    assert clock.elapsed_hours > 0


def test_mission_clock_pause():
    clock = MissionClock()
    clock.paused = True
    sim_dt = clock.tick(1.0)
    assert sim_dt == 0.0
    assert clock.sim_time == 0.0


def test_comms_delay():
    comms = CommsDelay(asteroid_distance_au=1.0)
    assert abs(comms.one_way_delay_seconds - 499.0) < 1.0
    assert comms.one_way_delay_minutes > 8.0


def test_comms_message_transit():
    comms = CommsDelay(asteroid_distance_au=1.0)
    msg = comms.send_command({"type": "retarget"}, sim_time=0.0)
    assert msg.arrival_time > 0

    # Before arrival — nothing delivered
    commands, telemetry = comms.tick(sim_time=100.0)
    assert len(commands) == 0

    # After arrival
    commands, telemetry = comms.tick(sim_time=600.0)
    assert len(commands) == 1
    assert commands[0].content["type"] == "retarget"


def test_tunnel_network():
    tunnel = TunnelNetwork()
    assert tunnel.total_length_m > 0  # Initial shaft
    assert len(tunnel.segments) == 1

    # Extend tunnel
    tunnel.extend_tunnel(0, amount_m=1.0, regolith_kg=2.0)
    assert tunnel.total_length_m == 4.0  # 3m initial + 1m
    assert tunnel.total_material_extracted_kg == 2.0


def test_tunnel_sealing():
    tunnel = TunnelNetwork()
    seg = tunnel.add_segment(length_m=2.0)
    tunnel.seal_segment(seg.id, quality=0.5)
    assert seg.sealed is True
    assert seg.seal_quality == 0.5

    # Pressurize
    tunnel.pressurize_segment(seg.id)
    assert seg.pressurized is True
    assert seg.pressure_kpa > 0


def test_ant_agent_worker():
    agent = AntAgent(id=0, caste="worker")
    agent._target = Position(5, 5, 0)

    # Run for a few ticks
    for _ in range(100):
        agent.tick(1.0)
    assert agent.state != AntState.IDLE or agent._cycle_count > 0


def test_ant_agent_failure():
    agent = AntAgent(id=0, caste="worker", mtbf_hours=0.001)
    # With very low MTBF, should fail quickly
    for _ in range(1000):
        events = agent.tick(1.0)
        if agent.state == AntState.FAILED:
            break
    assert agent.state == AntState.FAILED


def test_sim_engine_setup():
    engine = SimEngine(workers=10, taskmasters=1, surface_ants=2)
    engine.setup()
    assert len(engine.agents) == 13  # 10 workers + 1 taskmaster + 2 surface
    assert engine.tunnel.total_length_m > 0


def test_sim_engine_tick():
    engine = SimEngine(workers=5, taskmasters=1, surface_ants=1)
    engine.setup()
    engine.clock.speed = 100.0

    # Run for 10 real seconds at 100x = 1000 sim seconds
    for _ in range(100):
        engine.tick(0.1)

    status = engine.status()
    assert status["total_ants"] == 7
    assert status["clock"] != "00:00"


def test_sim_engine_worker_roles():
    """Workers should be dynamically assigned roles (mining, sorting, etc.)."""
    engine = SimEngine(workers=20, taskmasters=1, surface_ants=1)
    engine.setup()
    roles = set(a.caste for a in engine.agents if a.caste not in ("taskmaster", "surface_ant"))
    # Should have multiple roles assigned from the worker pool
    assert "worker" in roles  # Mining role
    assert len(roles) >= 2    # At least mining + one other role


def test_sim_engine_status():
    engine = SimEngine(workers=3, taskmasters=1, surface_ants=1)
    engine.setup()
    status = engine.status()
    assert "ants_by_caste" in status
    assert "tunnel" in status
    assert "stats" in status
    assert "comms" in status


def test_sim_engine_player_command():
    engine = SimEngine(workers=3, taskmasters=1, surface_ants=1)
    engine.setup()
    engine.send_player_command({"type": "retarget", "area": "sector_b"})
    assert len(engine.comms.pending_outbound()) == 1


def test_position_distance():
    a = Position(0, 0, 0)
    b = Position(3, 4, 0)
    assert abs(a.distance_to(b) - 5.0) < 0.001


def test_position_move_toward():
    a = Position(0, 0, 0)
    b = Position(10, 0, 0)
    a.move_toward(b, speed=5.0, dt=1.0)
    assert a.x > 0
    assert a.x <= 5.0
