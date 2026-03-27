"""Radio protocol for worker <-> taskmaster communication via nRF24L01.

Packet format: fixed 32-byte packets (nRF24L01 max payload).
First byte = message type. Remaining 31 bytes = payload.

Both sides use the same protocol. Workers listen for commands,
send status reports. Taskmasters send commands, listen for reports.
"""

import struct

# Message types (first byte of every packet)
# Taskmaster -> Worker commands
CMD_MOVE_TO = 0x10
CMD_DETACH_RAIL = 0x11
CMD_ATTACH_RAIL = 0x12
CMD_DRILL = 0x20
CMD_DRILL_STOP = 0x21
CMD_SCOOP = 0x22
CMD_DUMP_HOPPER = 0x23
CMD_SWAP_TOOL = 0x30
CMD_REPORT_STATUS = 0x40
CMD_HALT = 0xFF

# Worker -> Taskmaster reports
RPT_HEARTBEAT = 0x80
RPT_DRILL_DONE = 0x81
RPT_AT_POSITION = 0x82
RPT_HOPPER_FULL = 0x83
RPT_SUPERCAP_LOW = 0x84
RPT_STALL = 0x85
RPT_TOOL_SEATED = 0x86
RPT_STATUS = 0x87


def pack_command(cmd_type: int, worker_id: int, **kwargs) -> bytes:
    """Pack a command into a 32-byte packet.

    Format: [type:1][worker_id:1][payload:30]
    """
    buf = bytearray(32)
    buf[0] = cmd_type
    buf[1] = worker_id & 0xFF

    if cmd_type == CMD_MOVE_TO:
        # payload: rail_position (float32)
        pos = kwargs.get("rail_position", 0.0)
        struct.pack_into("<f", buf, 2, pos)

    elif cmd_type == CMD_DRILL:
        # payload: duration_ms (uint16)
        duration = kwargs.get("duration_ms", 3000)
        struct.pack_into("<H", buf, 2, duration)

    elif cmd_type == CMD_SWAP_TOOL:
        # payload: dock_id (uint8), tool_type (uint8)
        dock = kwargs.get("dock_id", 0)
        tool = kwargs.get("tool_type", 0)
        buf[2] = dock
        buf[3] = tool

    # CMD_DETACH_RAIL, CMD_ATTACH_RAIL, CMD_DRILL_STOP, CMD_SCOOP,
    # CMD_DUMP_HOPPER, CMD_REPORT_STATUS, CMD_HALT: no payload needed

    return bytes(buf)


def pack_heartbeat(worker_id: int, rail_pos: float, supercap_pct: int,
                   hopper_pct: int, state: int, servo_ok_mask: int) -> bytes:
    """Pack a worker heartbeat report (sent every 5 seconds).

    Format: [type:1][id:1][rail_pos:4][supercap:1][hopper:1][state:1][servo_mask:1][pad:22]
    """
    buf = bytearray(32)
    buf[0] = RPT_HEARTBEAT
    buf[1] = worker_id & 0xFF
    struct.pack_into("<f", buf, 2, rail_pos)
    buf[6] = min(100, max(0, supercap_pct))
    buf[7] = min(100, max(0, hopper_pct))
    buf[8] = state
    buf[9] = servo_ok_mask  # Bit mask: bit 0 = servo 0 OK, etc.
    return bytes(buf)


def pack_stall_report(worker_id: int, servo_id: int, current_ma: int) -> bytes:
    """Report a servo stall."""
    buf = bytearray(32)
    buf[0] = RPT_STALL
    buf[1] = worker_id & 0xFF
    buf[2] = servo_id
    struct.pack_into("<H", buf, 3, current_ma)
    return bytes(buf)


def pack_status_report(worker_id: int, rail_pos: float, supercap_pct: int,
                       hopper_pct: int, state: int, servo_currents: list,
                       tool_id: int, cycles: int) -> bytes:
    """Full status report (response to CMD_REPORT_STATUS).

    More detailed than heartbeat. Includes servo currents and tool info.
    """
    buf = bytearray(32)
    buf[0] = RPT_STATUS
    buf[1] = worker_id & 0xFF
    struct.pack_into("<f", buf, 2, rail_pos)
    buf[6] = supercap_pct
    buf[7] = hopper_pct
    buf[8] = state
    buf[9] = tool_id
    struct.pack_into("<H", buf, 10, cycles)
    # Pack servo currents (8 servos, 1 byte each = mA/4)
    for i in range(min(8, len(servo_currents))):
        buf[12 + i] = min(255, servo_currents[i] // 4)
    return bytes(buf)


def unpack_packet(data: bytes) -> dict:
    """Unpack any packet into a dict."""
    if len(data) < 2:
        return {"type": "invalid"}

    msg_type = data[0]
    result = {"type": msg_type, "raw": data}

    if msg_type == RPT_HEARTBEAT:
        result.update({
            "worker_id": data[1],
            "rail_pos": struct.unpack_from("<f", data, 2)[0],
            "supercap_pct": data[6],
            "hopper_pct": data[7],
            "state": data[8],
            "servo_ok_mask": data[9],
        })

    elif msg_type == RPT_STALL:
        result.update({
            "worker_id": data[1],
            "servo_id": data[2],
            "current_ma": struct.unpack_from("<H", data, 3)[0],
        })

    elif msg_type == RPT_STATUS:
        result.update({
            "worker_id": data[1],
            "rail_pos": struct.unpack_from("<f", data, 2)[0],
            "supercap_pct": data[6],
            "hopper_pct": data[7],
            "state": data[8],
            "tool_id": data[9],
            "cycles": struct.unpack_from("<H", data, 10)[0],
            "servo_currents": [data[12 + i] * 4 for i in range(8)],
        })

    elif msg_type in (CMD_MOVE_TO,):
        result.update({
            "worker_id": data[1],
            "rail_position": struct.unpack_from("<f", data, 2)[0],
        })

    elif msg_type == CMD_DRILL:
        result.update({
            "worker_id": data[1],
            "duration_ms": struct.unpack_from("<H", data, 2)[0],
        })

    else:
        result["worker_id"] = data[1]

    return result
