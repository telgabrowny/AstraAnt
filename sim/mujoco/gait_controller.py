"""MuJoCo gait controller for AstraAnt worker ant.

Ported from firmware/worker/gait.py (MicroPython).
Alternating tripod gait: Group A (0,3,4) and Group B (1,2,5)
alternate between stance (grip + pull) and swing (release + reach).

All angles returned in RADIANS for direct use with MuJoCo data.ctrl[].
Positive angle = forward swing, negative = backward stance.
"""

import math

# Tripod gait leg groups (matches firmware exactly)
GROUP_A = [0, 3, 4]  # Front-Left, Mid-Right, Rear-Left
GROUP_B = [1, 2, 5]  # Front-Right, Mid-Left, Rear-Right

# Default parameters (from firmware/worker/gait.py)
DEFAULT_AMPLITUDE_DEG = 30    # +/- degrees from neutral (firmware: 60-120 range)
DEFAULT_STEP_PERIOD = 0.400   # seconds per complete cycle


class GaitController:
    """Generates servo target angles for alternating tripod gait.

    Usage with MuJoCo:
        gait = GaitController()
        for each timestep:
            angles = gait.step(dt)
            for i in range(6):
                data.ctrl[i] = angles[i]  # radians, directly to actuator
    """

    def __init__(self, step_period=DEFAULT_STEP_PERIOD,
                 amplitude_deg=DEFAULT_AMPLITUDE_DEG):
        self.step_period = step_period
        self.amplitude_rad = math.radians(amplitude_deg)
        self.phase = 0.0   # 0.0 to 1.0
        self.speed = 1.0   # multiplier: 0=stopped, 1=normal, 2=fast

    def step(self, dt):
        """Advance gait phase by dt seconds. Returns 6 target angles in radians.

        Phase-angle mapping (same as firmware sinusoidal interpolation):
          phase 0.00 -> neutral (0 rad)
          phase 0.25 -> max swing (+amplitude)
          phase 0.50 -> neutral (0 rad)
          phase 0.75 -> max stance (-amplitude)
        Group B is offset by 0.5 (180 degrees out of phase).
        """
        if self.speed <= 0:
            return [0.0] * 6

        self.phase += (dt / self.step_period) * self.speed
        self.phase %= 1.0

        angles = [0.0] * 6
        for i in range(6):
            if i in GROUP_A:
                group_phase = self.phase
            else:
                group_phase = (self.phase + 0.5) % 1.0

            sin_val = math.sin(group_phase * 2.0 * math.pi)
            angles[i] = self.amplitude_rad * sin_val

        return angles

    def neutral(self):
        """All legs at neutral position (0 radians)."""
        return [0.0] * 6

    def all_grip(self):
        """All legs at maximum stance (backward, gripping surface)."""
        return [-self.amplitude_rad] * 6

    def set_speed(self, speed):
        """Set gait speed multiplier. 0=stopped, 1=normal, 2=fast."""
        self.speed = max(0.0, speed)

    def reset(self):
        """Reset phase to start of cycle."""
        self.phase = 0.0

    def get_phase_for_leg(self, leg_idx):
        """Get the current group phase (0.0-1.0) for a specific leg.

        Useful for external grip controllers that need to know each
        leg's stance/swing state without duplicating the phase math.
        """
        if leg_idx in GROUP_A:
            return self.phase
        else:
            return (self.phase + 0.5) % 1.0
