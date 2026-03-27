"""Command handler -- executes commands from the taskmaster.

This is the core control loop. The worker receives commands via radio,
executes them, and reports back. The same logic runs in both:
  1. Real hardware (MicroPython on RP2040)
  2. Simulation (Python sim engine)

By keeping command handling identical, the sim accurately predicts
what the real ant will do.
"""

from radio_protocol import *

# States (shared between firmware and sim)
STATE_IDLE = 0
STATE_MOVING = 1
STATE_DRILLING = 2
STATE_SCOOPING = 3
STATE_HAULING = 4
STATE_DUMPING = 5
STATE_RETURNING = 6
STATE_SWAPPING_TOOL = 7
STATE_FAILED = 8


class CommandHandler:
    """Processes commands and manages the worker's state machine.

    This class is designed to work on both real hardware and in the sim.
    Hardware-specific functions (set_servo, read_sensor, send_radio)
    are passed in as callbacks so the same logic runs everywhere.
    """

    def __init__(self, worker_id: int,
                 set_servo_fn=None,      # fn(servo_idx, angle_deg)
                 read_supercap_fn=None,  # fn() -> pct (0-100)
                 read_hopper_fn=None,    # fn() -> pct (0-100)
                 read_proximity_fn=None, # fn() -> distance_mm
                 send_radio_fn=None,     # fn(packet_bytes)
                 drill_motor_fn=None,    # fn(speed_pct) or fn(0) to stop
                 gait_step_fn=None):     # fn(dt_ms) advance walking gait
        self.worker_id = worker_id
        self.state = STATE_IDLE
        self.rail_position = 0.0
        self.hopper_pct = 0
        self.supercap_pct = 100
        self.servo_ok_mask = 0xFF       # All 8 servos OK
        self.current_tool = 0
        self.cycles = 0

        # Hardware callbacks (or sim stubs)
        self._set_servo = set_servo_fn or (lambda idx, angle: None)
        self._read_supercap = read_supercap_fn or (lambda: 100)
        self._read_hopper = read_hopper_fn or (lambda: 0)
        self._read_proximity = read_proximity_fn or (lambda: 100)
        self._send_radio = send_radio_fn or (lambda pkt: None)
        self._drill_motor = drill_motor_fn or (lambda speed: None)
        self._gait_step = gait_step_fn or (lambda dt: None)

        # Command state
        self._cmd_timer_ms = 0
        self._target_position = 0.0

    def handle_command(self, packet: bytes) -> None:
        """Process a command packet from the taskmaster."""
        cmd = unpack_packet(packet)
        msg_type = cmd.get("type", 0)

        if msg_type == CMD_MOVE_TO:
            self._target_position = cmd.get("rail_position", 0.0)
            self.state = STATE_MOVING

        elif msg_type == CMD_DETACH_RAIL:
            # Release rail contact, go on supercap power
            self.state = STATE_MOVING  # Off-rail movement

        elif msg_type == CMD_ATTACH_RAIL:
            # Re-engage rail
            pass  # Supercap starts charging automatically

        elif msg_type == CMD_DRILL:
            duration = cmd.get("duration_ms", 3000)
            self._cmd_timer_ms = duration
            self._drill_motor(80)  # 80% speed
            self.state = STATE_DRILLING

        elif msg_type == CMD_DRILL_STOP:
            self._drill_motor(0)
            self.state = STATE_IDLE

        elif msg_type == CMD_SCOOP:
            self._set_servo(6, 110)  # Close left mandible
            self._set_servo(7, 70)   # Close right mandible
            self.state = STATE_SCOOPING
            self._cmd_timer_ms = 2000  # 2 seconds to scoop

        elif msg_type == CMD_DUMP_HOPPER:
            self.state = STATE_DUMPING
            self._cmd_timer_ms = 1000

        elif msg_type == CMD_SWAP_TOOL:
            self.state = STATE_SWAPPING_TOOL
            self._cmd_timer_ms = 30000  # 30 seconds for tool swap

        elif msg_type == CMD_REPORT_STATUS:
            self._send_status_report()

        elif msg_type == CMD_HALT:
            self._drill_motor(0)
            self.state = STATE_IDLE

    def tick(self, dt_ms: int) -> None:
        """Main control loop tick. Call every 20ms."""
        # Update sensor readings
        self.supercap_pct = self._read_supercap()
        self.hopper_pct = self._read_hopper()

        # Supercap emergency
        if self.supercap_pct < 15 and self.state not in (STATE_IDLE, STATE_FAILED):
            self._drill_motor(0)
            self.state = STATE_RETURNING
            pkt = pack_heartbeat(self.worker_id, self.rail_position,
                                 self.supercap_pct, self.hopper_pct,
                                 self.state, self.servo_ok_mask)
            self._send_radio(pkt)

        # State-specific behavior
        if self.state == STATE_MOVING:
            self._gait_step(dt_ms)
            # Check if arrived (simplified — real version uses odometry)
            self._cmd_timer_ms -= dt_ms
            if self._cmd_timer_ms <= 0:
                self.state = STATE_IDLE
                pkt = pack_heartbeat(self.worker_id, self.rail_position,
                                     self.supercap_pct, self.hopper_pct,
                                     self.state, self.servo_ok_mask)
                self._send_radio(pkt)

        elif self.state == STATE_DRILLING:
            self._cmd_timer_ms -= dt_ms
            if self._cmd_timer_ms <= 0:
                self._drill_motor(0)
                self.state = STATE_IDLE
                pkt = bytearray(32)
                pkt[0] = RPT_DRILL_DONE
                pkt[1] = self.worker_id
                pkt[6] = self.hopper_pct
                self._send_radio(bytes(pkt))

        elif self.state == STATE_SCOOPING:
            self._cmd_timer_ms -= dt_ms
            if self._cmd_timer_ms <= 0:
                self.hopper_pct = min(100, self.hopper_pct + 12)  # ~12% per scoop
                if self.hopper_pct >= 95:
                    pkt = bytearray(32)
                    pkt[0] = RPT_HOPPER_FULL
                    pkt[1] = self.worker_id
                    self._send_radio(bytes(pkt))
                self.state = STATE_IDLE

        elif self.state == STATE_DUMPING:
            self._cmd_timer_ms -= dt_ms
            if self._cmd_timer_ms <= 0:
                dumped = self.hopper_pct
                self.hopper_pct = 0
                self.cycles += 1
                self.state = STATE_IDLE

        elif self.state == STATE_SWAPPING_TOOL:
            self._cmd_timer_ms -= dt_ms
            if self._cmd_timer_ms <= 0:
                pkt = bytearray(32)
                pkt[0] = RPT_TOOL_SEATED
                pkt[1] = self.worker_id
                self._send_radio(bytes(pkt))
                self.state = STATE_IDLE

    def _send_status_report(self) -> None:
        """Send full status to taskmaster."""
        pkt = pack_status_report(
            self.worker_id, self.rail_position,
            self.supercap_pct, self.hopper_pct,
            self.state, [100] * 8,  # Placeholder servo currents
            self.current_tool, self.cycles,
        )
        self._send_radio(pkt)
