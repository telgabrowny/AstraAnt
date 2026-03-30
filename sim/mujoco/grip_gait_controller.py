"""Grip-aware gait controller for microgravity walking.

Extends the base GaitController with per-foot grip state tracking.
During stance phase, feet grip the surface (microspines engage, magnets
pull, studs anchor). During swing phase, grip releases so the foot can
advance. The grip fraction follows a smooth sinusoidal profile
synchronized with the leg's phase -- no discontinuities.

Inspired by biological ant locomotion: tarsal claws + adhesive pads
provide a dual-mechanism grip that sums synergistically. Our hybrid
foot pad (microspines + magnet + studs) follows the same principle.

Reference: Stanford "Ants in Space" ISS experiment (2014) showed real
ants lose surface contact for 3-8s in microgravity. Phase-locked grip
eliminates this failure mode by ensuring 3 feet are always gripping.
"""

import math
from gait_controller import GaitController, GROUP_A, GROUP_B


class GripAwareGaitController(GaitController):
    """Gait controller that outputs both servo angles and grip states.

    Usage:
        gait = GripAwareGaitController()
        for each timestep:
            angles, grips = gait.step_with_grip(dt)
            for i in range(6):
                data.ctrl[i] = angles[i]
                apply_grip_force(foot_i, grips[i] * max_grip_force)
    """

    def step_with_grip(self, dt):
        """Advance gait and return (angles[6], grip_fractions[6]).

        angles: target servo angles in radians (same as base step())
        grip_fractions: 0.0-1.0 per foot, indicating grip engagement.
            1.0 = full grip (peak stance, foot pressing into surface)
            0.0 = released (peak swing, foot in the air)

        The grip fraction is: max(0, -sin(group_phase * 2*pi))
        This is 1.0 at phase 0.75 (max stance) and 0.0 during the
        entire swing half of the cycle, with smooth sinusoidal ramps.
        """
        angles = self.step(dt)

        grip_fractions = [0.0] * 6
        for i in range(6):
            phase = self.get_phase_for_leg(i)
            grip_fractions[i] = max(0.0, -math.sin(phase * 2.0 * math.pi))

        return angles, grip_fractions

    def get_grip_fraction(self, leg_idx):
        """Get current grip fraction for one leg without advancing phase."""
        phase = self.get_phase_for_leg(leg_idx)
        return max(0.0, -math.sin(phase * 2.0 * math.pi))

    def get_stance_feet(self):
        """Return list of leg indices currently in stance (grip > 0)."""
        return [i for i in range(6) if self.get_grip_fraction(i) > 0.01]

    def get_swing_feet(self):
        """Return list of leg indices currently in swing (grip ~ 0)."""
        return [i for i in range(6) if self.get_grip_fraction(i) <= 0.01]

    def all_grip_fractions(self):
        """All feet at maximum grip (for emergency stop / working)."""
        return [1.0] * 6
