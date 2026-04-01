"""UHF radio protocol -- command uplink and telemetry downlink.

Communicates with Earth ground station via UHF radio at 9600 bps.
Command latency: 4-32 minutes round trip depending on asteroid distance.

Packet format (64 bytes):
  [sync:2][type:1][seq:2][length:1][payload:56][crc:2]

Sync word: 0xAA55
CRC: CRC-16/CCITT over type+seq+length+payload.

Command types (ground -> mothership):
  0x01  SET_STATE     - Force mission state transition
  0x02  SET_PARAM     - Update config parameter
  0x03  QUERY_STATUS  - Request full status dump
  0x04  ABORT         - Abort current operation, hold position
  0x05  SAFE_MODE     - Enter safe mode immediately
  0x06  RESET_REBOOT  - Clear reboot counter
  0x07  ARM_CAPTURE   - Arm capture sequence (safety interlock)
  0x08  FIRE_RCS      - Manual RCS pulse command
  0x09  SET_EWIN_V    - Set electrowinning voltage

Telemetry types (mothership -> ground):
  0x80  BEACON        - Periodic health + state beacon
  0x81  STATUS_FULL   - Complete status dump (response to QUERY)
  0x82  EVENT         - State change or anomaly event
  0x83  ACK           - Command acknowledgment
  0x84  NACK          - Command rejected (with reason)
"""

import machine
import struct
import time


# -- Packet constants --
SYNC_WORD = 0xAA55
PACKET_SIZE = 64
HEADER_SIZE = 6       # sync(2) + type(1) + seq(2) + length(1)
CRC_SIZE = 2
MAX_PAYLOAD = PACKET_SIZE - HEADER_SIZE - CRC_SIZE  # 56 bytes

# -- Command types --
CMD_SET_STATE = 0x01
CMD_SET_PARAM = 0x02
CMD_QUERY_STATUS = 0x03
CMD_ABORT = 0x04
CMD_SAFE_MODE = 0x05
CMD_RESET_REBOOT = 0x06
CMD_ARM_CAPTURE = 0x07
CMD_FIRE_RCS = 0x08
CMD_SET_EWIN_V = 0x09

# -- Telemetry types --
TLM_BEACON = 0x80
TLM_STATUS_FULL = 0x81
TLM_EVENT = 0x82
TLM_ACK = 0x83
TLM_NACK = 0x84

# -- State codes (must match main.py) --
STATE_NAMES = {
    0: "LAUNCH_DETECT",
    1: "DEPLOY_PANELS",
    2: "TRANSIT",
    3: "APPROACH",
    4: "STATION_KEEP",
    5: "CAPTURE",
    6: "BIOLEACH",
    7: "ELECTROFORM",
    8: "WAAM_OPS",
    9: "GROWTH",
    10: "AUTONOMOUS",
    255: "SAFE_MODE",
}


def _crc16_ccitt(data):
    """CRC-16/CCITT (0xFFFF init, 0x1021 polynomial).

    Args:
        data: bytes or bytearray to checksum.

    Returns:
        16-bit CRC as int.
    """
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc


def init_comms(cfg):
    """Initialize UART for UHF radio.

    Args:
        cfg: Full mission config dict.

    Returns:
        Dict with uart object and protocol state.
    """
    comms_cfg = cfg.get("comms", {})
    uart_id = comms_cfg.get("uart_id", 1)
    tx_pin = comms_cfg.get("uart_tx", 17)
    rx_pin = comms_cfg.get("uart_rx", 16)
    baud = comms_cfg.get("baud", 9600)

    uart = None
    try:
        uart = machine.UART(uart_id,
                            baudrate=baud,
                            tx=machine.Pin(tx_pin),
                            rx=machine.Pin(rx_pin),
                            rxbuf=256)
    except Exception as e:
        print("COMMS: UART init failed:", e)

    return {
        "uart": uart,
        "tx_seq": 0,
        "rx_buf": bytearray(256),
        "rx_pos": 0,
        "beacon_interval_s": comms_cfg.get("beacon_interval_s", 30),
        "last_beacon_ms": 0,
        "packets_tx": 0,
        "packets_rx": 0,
        "crc_errors": 0,
    }


def _build_packet(msg_type, seq, payload):
    """Build a 64-byte packet with sync, header, payload, CRC.

    Args:
        msg_type: Message type byte.
        seq: Sequence number (uint16).
        payload: bytes or bytearray (max 56 bytes).

    Returns:
        64-byte packet as bytes.
    """
    plen = min(len(payload), MAX_PAYLOAD)
    buf = bytearray(PACKET_SIZE)

    # Sync word
    struct.pack_into("<H", buf, 0, SYNC_WORD)
    # Type
    buf[2] = msg_type & 0xFF
    # Sequence
    struct.pack_into("<H", buf, 3, seq & 0xFFFF)
    # Payload length
    buf[5] = plen
    # Payload
    buf[HEADER_SIZE:HEADER_SIZE + plen] = payload[:plen]
    # CRC over type+seq+length+payload
    crc_data = buf[2:HEADER_SIZE + plen]
    crc = _crc16_ccitt(crc_data)
    struct.pack_into("<H", buf, PACKET_SIZE - CRC_SIZE, crc)

    return bytes(buf)


def _send_raw(comms, packet):
    """Transmit a raw packet via UART.

    Args:
        comms: Comms state dict from init_comms().
        packet: 64-byte packet.
    """
    uart = comms.get("uart")
    if uart is None:
        return
    try:
        uart.write(packet)
        comms["packets_tx"] += 1
    except Exception as e:
        print("COMMS TX error:", e)


def send_beacon(comms, state_code, health_packet):
    """Send periodic telemetry beacon.

    Beacon payload (56 bytes max):
      [state:1][bat_soc:1][solar_w_x10:2][temps:2][alert_flags:1][uptime_s:4]
      [reserved:45]

    Args:
        comms: Comms state dict.
        state_code: Current mission state (0-255).
        health_packet: Dict from health.generate_health_packet().
    """
    payload = bytearray(MAX_PAYLOAD)
    payload[0] = state_code & 0xFF
    payload[1] = max(0, min(255, health_packet.get("battery_soc", 0)))
    sol_w = int(health_packet.get("solar_w", 0) * 10)
    struct.pack_into("<H", payload, 2, max(0, min(65535, sol_w)))

    temps = health_packet.get("temps_c", [])
    for i in range(min(2, len(temps))):
        t = int(temps[i]) if temps[i] != -999 else -128
        struct.pack_into("<b", payload, 4 + i, max(-128, min(127, t)))

    # Alert flags
    flags = 0
    for a in health_packet.get("alerts", []):
        if "TEMP" in a:
            flags |= 0x01
        if "BAT" in a:
            flags |= 0x02
        if "SOL" in a:
            flags |= 0x04
        if "CPU" in a:
            flags |= 0x08
        if "RAM" in a:
            flags |= 0x10
    payload[6] = flags

    uptime_s = health_packet.get("uptime_ms", 0) // 1000
    struct.pack_into("<I", payload, 7, uptime_s)

    seq = comms["tx_seq"]
    comms["tx_seq"] = (seq + 1) & 0xFFFF

    pkt = _build_packet(TLM_BEACON, seq, payload)
    _send_raw(comms, pkt)
    comms["last_beacon_ms"] = time.ticks_ms()


def send_event(comms, event_code, detail_str):
    """Send an event notification (state change, anomaly, etc).

    Args:
        comms: Comms state dict.
        event_code: Application-specific event code byte.
        detail_str: Short ASCII string description (max 54 chars).
    """
    payload = bytearray(MAX_PAYLOAD)
    payload[0] = event_code & 0xFF
    detail = detail_str[:54].encode("ascii")
    payload[1] = len(detail)
    payload[2:2 + len(detail)] = detail

    seq = comms["tx_seq"]
    comms["tx_seq"] = (seq + 1) & 0xFFFF
    pkt = _build_packet(TLM_EVENT, seq, payload)
    _send_raw(comms, pkt)


def send_ack(comms, cmd_seq):
    """Send command acknowledgment.

    Args:
        comms: Comms state dict.
        cmd_seq: Sequence number of the acknowledged command.
    """
    payload = bytearray(2)
    struct.pack_into("<H", payload, 0, cmd_seq)

    seq = comms["tx_seq"]
    comms["tx_seq"] = (seq + 1) & 0xFFFF
    pkt = _build_packet(TLM_ACK, seq, payload)
    _send_raw(comms, pkt)


def send_nack(comms, cmd_seq, reason_str):
    """Send command rejection with reason.

    Args:
        comms: Comms state dict.
        cmd_seq: Sequence number of the rejected command.
        reason_str: Short reason string (max 52 chars).
    """
    payload = bytearray(MAX_PAYLOAD)
    struct.pack_into("<H", payload, 0, cmd_seq)
    reason = reason_str[:52].encode("ascii")
    payload[2] = len(reason)
    payload[3:3 + len(reason)] = reason

    seq = comms["tx_seq"]
    comms["tx_seq"] = (seq + 1) & 0xFFFF
    pkt = _build_packet(TLM_NACK, seq, payload)
    _send_raw(comms, pkt)


def send_status_full(comms, state_code, health_pkt, nav_state, capture_state):
    """Send complete status dump (response to QUERY_STATUS).

    Args:
        comms: Comms state dict.
        state_code: Current mission state.
        health_pkt: Dict from health.generate_health_packet().
        nav_state: Dict from navigator (position, velocity, etc).
        capture_state: Dict from capture module state.
    """
    payload = bytearray(MAX_PAYLOAD)
    payload[0] = state_code & 0xFF
    payload[1] = max(0, min(255, health_pkt.get("battery_soc", 0)))

    # Position (3 floats = 12 bytes)
    pos = nav_state.get("position", (0.0, 0.0, 0.0))
    for i in range(3):
        struct.pack_into("<f", payload, 2 + i * 4, pos[i] if i < len(pos) else 0.0)

    # Velocity magnitude
    vel = nav_state.get("velocity", (0.0, 0.0, 0.0))
    v_mag = sum(v * v for v in vel) ** 0.5
    struct.pack_into("<f", payload, 14, v_mag)

    # Range to target
    rng = nav_state.get("range_to_target_m", -1.0)
    struct.pack_into("<f", payload, 18, rng)

    # Capture sub-state
    cap_st = capture_state.get("sub_state", 0)
    payload[22] = cap_st & 0xFF

    # Solar power
    sol_w = int(health_pkt.get("solar_w", 0) * 10)
    struct.pack_into("<H", payload, 23, max(0, min(65535, sol_w)))

    seq = comms["tx_seq"]
    comms["tx_seq"] = (seq + 1) & 0xFFFF
    pkt = _build_packet(TLM_STATUS_FULL, seq, payload)
    _send_raw(comms, pkt)


def check_for_commands(comms):
    """Check UART receive buffer for incoming commands.

    Non-blocking. Reads available bytes, scans for sync word,
    validates CRC, returns decoded command or None.

    Returns:
        Dict with command fields, or None if no valid command.
        Keys: type, seq, payload (bytes), raw.
    """
    uart = comms.get("uart")
    if uart is None:
        return None

    # Read available bytes into accumulation buffer
    try:
        avail = uart.any()
        if avail <= 0:
            return None
        chunk = uart.read(min(avail, 128))
        if chunk is None:
            return None
    except Exception:
        return None

    rx_buf = comms["rx_buf"]
    rx_pos = comms["rx_pos"]

    # Append new data
    for b in chunk:
        if rx_pos < len(rx_buf):
            rx_buf[rx_pos] = b
            rx_pos += 1

    comms["rx_pos"] = rx_pos

    # Scan for sync word + complete packet
    if rx_pos < PACKET_SIZE:
        return None

    # Find sync word
    sync_idx = -1
    for i in range(rx_pos - 1):
        if rx_buf[i] == 0x55 and rx_buf[i + 1] == 0xAA:
            # Little-endian: 0xAA55 stored as 0x55, 0xAA
            sync_idx = i
            break
        if rx_buf[i] == 0xAA and i + 1 < rx_pos and rx_buf[i + 1] == 0x55:
            # Check byte order
            w = struct.unpack_from("<H", rx_buf, i)[0]
            if w == SYNC_WORD:
                sync_idx = i
                break

    if sync_idx < 0 or sync_idx + PACKET_SIZE > rx_pos:
        # No complete packet yet; discard bytes before last possible sync
        if rx_pos > PACKET_SIZE * 2:
            # Shift buffer
            keep = rx_pos - PACKET_SIZE
            rx_buf[:keep] = rx_buf[rx_pos - keep:rx_pos]
            comms["rx_pos"] = keep
        return None

    # Extract packet
    pkt = bytes(rx_buf[sync_idx:sync_idx + PACKET_SIZE])

    # Shift remaining data
    remaining = rx_pos - (sync_idx + PACKET_SIZE)
    if remaining > 0:
        rx_buf[:remaining] = rx_buf[sync_idx + PACKET_SIZE:rx_pos]
    comms["rx_pos"] = remaining

    # Validate CRC
    msg_type = pkt[2]
    seq = struct.unpack_from("<H", pkt, 3)[0]
    plen = pkt[5]
    crc_data = pkt[2:HEADER_SIZE + plen]
    expected_crc = _crc16_ccitt(crc_data)
    actual_crc = struct.unpack_from("<H", pkt, PACKET_SIZE - CRC_SIZE)[0]

    if expected_crc != actual_crc:
        comms["crc_errors"] += 1
        return None

    comms["packets_rx"] += 1
    payload = pkt[HEADER_SIZE:HEADER_SIZE + plen]

    return {
        "type": msg_type,
        "seq": seq,
        "payload": payload,
        "raw": pkt,
    }


def decode_command(cmd_pkt):
    """Decode a validated command packet into action parameters.

    Args:
        cmd_pkt: Dict from check_for_commands() (type, seq, payload).

    Returns:
        Dict with 'cmd' string name and command-specific fields.
    """
    if cmd_pkt is None:
        return None

    msg_type = cmd_pkt["type"]
    payload = cmd_pkt["payload"]
    result = {"cmd": msg_type, "seq": cmd_pkt["seq"]}

    if msg_type == CMD_SET_STATE:
        if len(payload) >= 1:
            result["target_state"] = payload[0]
            result["cmd_name"] = "SET_STATE"
        else:
            result["cmd_name"] = "SET_STATE_BAD"

    elif msg_type == CMD_SET_PARAM:
        if len(payload) >= 5:
            param_id = payload[0]
            value = struct.unpack_from("<f", payload, 1)[0]
            result["param_id"] = param_id
            result["value"] = value
            result["cmd_name"] = "SET_PARAM"
        else:
            result["cmd_name"] = "SET_PARAM_BAD"

    elif msg_type == CMD_QUERY_STATUS:
        result["cmd_name"] = "QUERY_STATUS"

    elif msg_type == CMD_ABORT:
        result["cmd_name"] = "ABORT"

    elif msg_type == CMD_SAFE_MODE:
        result["cmd_name"] = "SAFE_MODE"

    elif msg_type == CMD_RESET_REBOOT:
        result["cmd_name"] = "RESET_REBOOT"

    elif msg_type == CMD_ARM_CAPTURE:
        result["cmd_name"] = "ARM_CAPTURE"
        if len(payload) >= 1:
            result["arm_code"] = payload[0]  # Safety interlock code

    elif msg_type == CMD_FIRE_RCS:
        if len(payload) >= 3:
            result["thruster_id"] = payload[0]
            result["duration_ms"] = struct.unpack_from("<H", payload, 1)[0]
            result["cmd_name"] = "FIRE_RCS"
        else:
            result["cmd_name"] = "FIRE_RCS_BAD"

    elif msg_type == CMD_SET_EWIN_V:
        if len(payload) >= 4:
            result["voltage"] = struct.unpack_from("<f", payload, 0)[0]
            result["cmd_name"] = "SET_EWIN_V"
        else:
            result["cmd_name"] = "SET_EWIN_V_BAD"

    else:
        result["cmd_name"] = "UNKNOWN_%02X" % msg_type

    return result


def handle_command(comms, cmd, state_machine):
    """Dispatch a decoded command to the appropriate handler.

    Args:
        comms: Comms state dict.
        cmd: Dict from decode_command().
        state_machine: Reference to main mission state machine dict.

    Returns:
        True if command was handled, False if rejected.
    """
    if cmd is None:
        return False

    cmd_name = cmd.get("cmd_name", "")
    seq = cmd.get("seq", 0)

    if cmd_name == "SET_STATE":
        target = cmd.get("target_state", 255)
        state_machine["requested_state"] = target
        send_ack(comms, seq)
        send_event(comms, target, "CMD:SET_STATE->%s" % STATE_NAMES.get(target, "?"))
        return True

    elif cmd_name == "QUERY_STATUS":
        # Status response is sent by main loop after this returns
        state_machine["status_requested"] = True
        send_ack(comms, seq)
        return True

    elif cmd_name == "ABORT":
        state_machine["abort_requested"] = True
        send_ack(comms, seq)
        send_event(comms, 0xFF, "CMD:ABORT received")
        return True

    elif cmd_name == "SAFE_MODE":
        state_machine["requested_state"] = 255  # SAFE_MODE code
        send_ack(comms, seq)
        send_event(comms, 0xFF, "CMD:SAFE_MODE")
        return True

    elif cmd_name == "ARM_CAPTURE":
        arm_code = cmd.get("arm_code", 0)
        if arm_code == 0xA5:  # Safety interlock
            state_machine["capture_armed"] = True
            send_ack(comms, seq)
            send_event(comms, 0x07, "CAPTURE ARMED")
            return True
        else:
            send_nack(comms, seq, "bad interlock code")
            return False

    elif cmd_name == "RESET_REBOOT":
        try:
            with open("reboot_count.dat", "w") as f:
                f.write("0")
            send_ack(comms, seq)
            send_event(comms, 0x06, "reboot counter reset")
            return True
        except Exception:
            send_nack(comms, seq, "file write failed")
            return False

    elif cmd_name == "SET_PARAM":
        state_machine["param_update"] = (cmd["param_id"], cmd["value"])
        send_ack(comms, seq)
        return True

    elif cmd_name == "FIRE_RCS":
        state_machine["rcs_command"] = (cmd["thruster_id"], cmd["duration_ms"])
        send_ack(comms, seq)
        return True

    elif cmd_name == "SET_EWIN_V":
        state_machine["ewin_voltage"] = cmd["voltage"]
        send_ack(comms, seq)
        return True

    else:
        send_nack(comms, seq, "unknown command")
        return False


def is_beacon_due(comms):
    """Check if it is time to send a telemetry beacon.

    Args:
        comms: Comms state dict.

    Returns:
        True if beacon_interval_s has elapsed since last beacon.
    """
    interval_ms = comms.get("beacon_interval_s", 30) * 1000
    elapsed = time.ticks_diff(time.ticks_ms(), comms.get("last_beacon_ms", 0))
    return elapsed >= interval_ms
