"""Communication delay model — simulates Earth-to-asteroid signal travel time."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


# Speed of light in AU/second
C_AU_PER_SEC = 1.0 / 499.0  # 1 AU = 499 light-seconds


@dataclass
class Message:
    """A message in transit between Earth and the asteroid."""
    content: dict[str, Any]
    send_time: float           # Sim time when sent
    arrival_time: float        # Sim time when it arrives
    direction: str             # "earth_to_asteroid" or "asteroid_to_earth"

    @property
    def delay_seconds(self) -> float:
        return self.arrival_time - self.send_time


class CommsDelay:
    """Manages communication delay between Earth ground control and the asteroid mothership.

    Commands from the player (Earth) take minutes to reach the asteroid.
    Telemetry from the asteroid takes the same time to reach Earth.
    The player sees past state and their commands arrive in the future.
    """

    def __init__(self, asteroid_distance_au: float = 1.0) -> None:
        self.distance_au = asteroid_distance_au
        self._outbound: deque[Message] = deque()  # Earth -> asteroid
        self._inbound: deque[Message] = deque()    # Asteroid -> Earth
        self._delivered_to_asteroid: list[Message] = []
        self._delivered_to_earth: list[Message] = []

    @property
    def one_way_delay_seconds(self) -> float:
        """One-way light travel time in seconds."""
        return self.distance_au / C_AU_PER_SEC

    @property
    def one_way_delay_minutes(self) -> float:
        return self.one_way_delay_seconds / 60.0

    @property
    def round_trip_minutes(self) -> float:
        return self.one_way_delay_minutes * 2

    def send_command(self, command: dict[str, Any], sim_time: float) -> Message:
        """Player sends a command from Earth. It enters the outbound queue."""
        msg = Message(
            content=command,
            send_time=sim_time,
            arrival_time=sim_time + self.one_way_delay_seconds,
            direction="earth_to_asteroid",
        )
        self._outbound.append(msg)
        return msg

    def send_telemetry(self, telemetry: dict[str, Any], sim_time: float) -> Message:
        """Mothership sends telemetry to Earth. It enters the inbound queue."""
        msg = Message(
            content=telemetry,
            send_time=sim_time,
            arrival_time=sim_time + self.one_way_delay_seconds,
            direction="asteroid_to_earth",
        )
        self._inbound.append(msg)
        return msg

    def tick(self, sim_time: float) -> tuple[list[Message], list[Message]]:
        """Process message queues. Returns (commands arrived at asteroid, telemetry arrived at Earth)."""
        arrived_commands = []
        while self._outbound and self._outbound[0].arrival_time <= sim_time:
            msg = self._outbound.popleft()
            arrived_commands.append(msg)
            self._delivered_to_asteroid.append(msg)

        arrived_telemetry = []
        while self._inbound and self._inbound[0].arrival_time <= sim_time:
            msg = self._inbound.popleft()
            arrived_telemetry.append(msg)
            self._delivered_to_earth.append(msg)

        return arrived_commands, arrived_telemetry

    def pending_outbound(self) -> list[Message]:
        """Commands currently in transit to the asteroid."""
        return list(self._outbound)

    def pending_inbound(self) -> list[Message]:
        """Telemetry currently in transit to Earth."""
        return list(self._inbound)

    @property
    def recent_telemetry(self) -> list[Message]:
        """Last 20 telemetry messages received on Earth."""
        # Cap delivered lists to prevent unbounded growth
        if len(self._delivered_to_earth) > 100:
            self._delivered_to_earth = self._delivered_to_earth[-50:]
        if len(self._delivered_to_asteroid) > 100:
            self._delivered_to_asteroid = self._delivered_to_asteroid[-50:]
        return self._delivered_to_earth[-20:]

    def update_distance(self, distance_au: float) -> None:
        """Update the asteroid distance (changes as orbits progress)."""
        self.distance_au = max(0.01, distance_au)
