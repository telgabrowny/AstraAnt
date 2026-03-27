"""Taskmaster squad management -- dispatches commands to workers.

The taskmaster is the local brain for its squad of ~20 workers.
It receives directives from the mothership Pi4 via CAN bus,
translates them into individual worker commands, and monitors
worker status via radio.

Decision loop:
  1. Pi4 says: "mine at position X, seal behind the miners"
  2. Taskmaster assigns workers: 12 miners, 3 haulers, 3 plasterers, 2 sorters
  3. For each miner: generate drill cycle commands and send via radio
  4. Monitor heartbeats, detect failures, reassign as needed
  5. Report squad status back to Pi4
"""

from __future__ import annotations

import time
from typing import Any


# Import from worker firmware (shared protocol)
import sys
sys.path.insert(0, "../worker")
try:
    from radio_protocol import (
        pack_command, unpack_packet,
        CMD_MOVE_TO, CMD_DETACH_RAIL, CMD_ATTACH_RAIL,
        CMD_DRILL, CMD_DRILL_STOP, CMD_SCOOP, CMD_DUMP_HOPPER,
        CMD_SWAP_TOOL, CMD_REPORT_STATUS, CMD_HALT,
        RPT_HEARTBEAT, RPT_STALL, RPT_HOPPER_FULL, RPT_DRILL_DONE,
    )
except ImportError:
    pass  # Running in sim mode without firmware imports


class WorkerState:
    """Tracked state of one worker in the squad."""
    def __init__(self, worker_id: int):
        self.id = worker_id
        self.role = "miner"           # miner, hauler, plasterer, sorter, tender
        self.tool = "drill_head"
        self.state = 0                # From last heartbeat
        self.rail_position = 0.0
        self.supercap_pct = 100
        self.hopper_pct = 0
        self.last_heartbeat_ms = 0
        self.alive = True
        self.cycles_completed = 0
        self.assigned_command_idx = 0  # Progress through drill cycle commands


class SquadManager:
    """Manages a squad of workers from the taskmaster."""

    def __init__(self, taskmaster_id: int, send_radio_fn=None, send_can_fn=None):
        self.taskmaster_id = taskmaster_id
        self.workers: dict[int, WorkerState] = {}
        self._send_radio = send_radio_fn or (lambda pkt: None)
        self._send_can = send_can_fn or (lambda msg: None)

        # Mining parameters (set by Pi4)
        self.target_rail_position = 0.0
        self.face_distance_m = 3.0
        self.drill_duration_ms = 3000
        self.mining_priority = ""     # From player command

    def add_worker(self, worker_id: int, role: str = "miner", tool: str = "drill_head"):
        self.workers[worker_id] = WorkerState(worker_id)
        self.workers[worker_id].role = role
        self.workers[worker_id].tool = tool

    def handle_worker_report(self, packet: bytes) -> list[dict[str, Any]]:
        """Process a status report from a worker. Returns events."""
        report = unpack_packet(packet)
        wid = report.get("worker_id", -1)
        events = []

        if wid not in self.workers:
            return events

        worker = self.workers[wid]
        msg_type = report.get("type", 0)

        if msg_type == RPT_HEARTBEAT:
            worker.last_heartbeat_ms = time.ticks_ms() if hasattr(time, 'ticks_ms') else 0
            worker.rail_position = report.get("rail_pos", 0)
            worker.supercap_pct = report.get("supercap_pct", 0)
            worker.hopper_pct = report.get("hopper_pct", 0)
            worker.state = report.get("state", 0)
            worker.alive = True

        elif msg_type == RPT_DRILL_DONE:
            # Drill burst complete. Check hopper and decide next action.
            worker.hopper_pct = report.get("hopper_pct", worker.hopper_pct)
            if worker.hopper_pct >= 90:
                # Hopper nearly full -- send to dump
                self._send_worker_to_dump(wid)
                events.append({"type": "worker_hauling", "worker_id": wid})
            else:
                # More room -- continue drilling
                self._send_drill_command(wid)

        elif msg_type == RPT_HOPPER_FULL:
            self._send_worker_to_dump(wid)
            events.append({"type": "worker_hauling", "worker_id": wid,
                           "message": f"Worker #{wid} hopper full, heading to dump"})

        elif msg_type == RPT_STALL:
            servo_id = report.get("servo_id", -1)
            current = report.get("current_ma", 0)
            worker.alive = False
            events.append({"type": "worker_stall", "worker_id": wid,
                           "servo_id": servo_id, "current_ma": current,
                           "message": f"STALL: Worker #{wid} servo {servo_id} at {current}mA"})
            # Send recovery worker
            self._dispatch_recovery(wid)

        return events

    def tick(self) -> list[dict[str, Any]]:
        """Periodic squad management. Check for missing heartbeats, rebalance."""
        events = []
        now = time.ticks_ms() if hasattr(time, 'ticks_ms') else 0

        for wid, worker in self.workers.items():
            if not worker.alive:
                continue

            # Check for missed heartbeats (15 seconds = 3 missed)
            if now > 0 and worker.last_heartbeat_ms > 0:
                elapsed = time.ticks_diff(now, worker.last_heartbeat_ms)
                if elapsed > 15000:
                    worker.alive = False
                    events.append({
                        "type": "worker_lost",
                        "worker_id": wid,
                        "message": f"HEARTBEAT LOST: Worker #{wid} unresponsive for 15s",
                    })
                    self._dispatch_recovery(wid)

            # If worker is idle and should be mining, send to work
            if worker.state == 0 and worker.role == "miner":
                self._send_drill_cycle(wid)

        return events

    def _send_drill_cycle(self, wid: int):
        """Send a worker on a complete drill cycle."""
        # Step 1: Move to work face area
        pkt = pack_command(CMD_MOVE_TO, wid, rail_position=self.target_rail_position)
        self._send_radio(pkt)
        # Steps 2+: queued via the worker's command handler
        # (TaskMaster sends DETACH -> DRILL -> SCOOP in sequence based on reports)

    def _send_drill_command(self, wid: int):
        """Send a single drill burst command."""
        pkt = pack_command(CMD_DRILL, wid, duration_ms=self.drill_duration_ms)
        self._send_radio(pkt)

    def _send_worker_to_dump(self, wid: int):
        """Command a worker to return to rail and dump."""
        self._send_radio(pack_command(CMD_ATTACH_RAIL, wid))
        self._send_radio(pack_command(CMD_MOVE_TO, wid, rail_position=0))
        self._send_radio(pack_command(CMD_DUMP_HOPPER, wid))

    def _dispatch_recovery(self, failed_wid: int):
        """Send the nearest idle worker to recover a failed ant."""
        for wid, worker in self.workers.items():
            if worker.alive and worker.state == 0 and wid != failed_wid:
                # Reassign to hauler temporarily, send to retrieve the carcass
                pkt = pack_command(CMD_SWAP_TOOL, wid, tool_type=5)  # cargo_gripper
                self._send_radio(pkt)
                pkt = pack_command(CMD_MOVE_TO, wid,
                                   rail_position=self.workers[failed_wid].rail_position)
                self._send_radio(pkt)
                break

    def rebalance_roles(self, target_miners: int = 12, target_plasterers: int = 3,
                         target_sorters: int = 2, target_tenders: int = 2):
        """Rebalance squad roles based on colony needs."""
        alive_workers = [w for w in self.workers.values() if w.alive]
        for i, worker in enumerate(alive_workers):
            if i < target_miners:
                worker.role = "miner"
                worker.tool = "drill_head"
            elif i < target_miners + target_plasterers:
                worker.role = "plasterer"
                worker.tool = "paste_nozzle"
            elif i < target_miners + target_plasterers + target_sorters:
                worker.role = "sorter"
                worker.tool = "thermal_rake"
            elif i < target_miners + target_plasterers + target_sorters + target_tenders:
                worker.role = "tender"
                worker.tool = "sampling_probe"
            else:
                worker.role = "miner"
                worker.tool = "drill_head"

    def summary(self) -> dict[str, Any]:
        alive = sum(1 for w in self.workers.values() if w.alive)
        by_role = {}
        for w in self.workers.values():
            if w.alive:
                by_role[w.role] = by_role.get(w.role, 0) + 1
        return {
            "taskmaster_id": self.taskmaster_id,
            "total_workers": len(self.workers),
            "alive": alive,
            "dead": len(self.workers) - alive,
            "by_role": by_role,
            "total_cycles": sum(w.cycles_completed for w in self.workers.values()),
        }
