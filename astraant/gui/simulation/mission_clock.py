"""Mission clock with variable speed time progression."""

from __future__ import annotations


class MissionClock:
    """Simulation time manager with variable speed.

    Tracks elapsed mission time in seconds. Supports pause, speed changes,
    and conversion to human-readable formats.
    """

    def __init__(self) -> None:
        self.sim_time: float = 0.0      # Seconds of simulated mission time
        self.speed: float = 1.0         # 1.0 = real-time, 100.0 = 100x
        self.paused: bool = False
        self.total_real_time: float = 0.0  # Real seconds elapsed

    def tick(self, real_dt: float) -> float:
        """Advance the clock by real_dt seconds. Returns simulated dt."""
        self.total_real_time += real_dt
        if self.paused:
            return 0.0
        sim_dt = real_dt * self.speed
        self.sim_time += sim_dt
        return sim_dt

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.0, speed)

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    @property
    def elapsed_days(self) -> float:
        return self.sim_time / 86400.0

    @property
    def elapsed_hours(self) -> float:
        return self.sim_time / 3600.0

    def format_elapsed(self) -> str:
        """Human-readable elapsed time."""
        total_sec = int(self.sim_time)
        days = total_sec // 86400
        hours = (total_sec % 86400) // 3600
        minutes = (total_sec % 3600) // 60
        if days > 0:
            return f"Day {days}, {hours:02d}:{minutes:02d}"
        return f"{hours:02d}:{minutes:02d}"
