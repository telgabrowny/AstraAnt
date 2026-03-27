"""Walking gait controller for 6-legged ant with 1-DOF legs.

Alternating tripod gait: legs 0,2,4 move together (Group A),
legs 1,3,5 move together (Group B). One group stance (gripping),
the other swings (reaching forward).

For microgravity: "swing" means releasing grip and reaching forward.
"Stance" means gripping the surface and pulling the body forward.
The grip-pull replaces the push-step of terrestrial walking.

Each leg servo oscillates between two angles:
  - Forward position (swing): servo at SWING_ANGLE
  - Back position (stance): servo at STANCE_ANGLE
"""

import math
import time

# Servo angle ranges (degrees) — calibrate per servo
# SG90 servos: 0-180 degrees via PWM
DEFAULT_SWING_ANGLE = 120   # Leg reaches forward
DEFAULT_STANCE_ANGLE = 60   # Leg pulls back (provides thrust)
DEFAULT_NEUTRAL = 90        # Centered

# Leg indices and their tripod group
# Group A (move together): front-left(0), mid-right(3), rear-left(4)
# Group B (move together): front-right(1), mid-left(2), rear-right(5)
GROUP_A = [0, 3, 4]
GROUP_B = [1, 2, 5]


class GaitController:
    """Generates servo commands for alternating tripod gait."""

    def __init__(self, servo_pwms: list, step_period_ms: int = 400):
        """
        Args:
            servo_pwms: List of 6 machine.PWM objects (one per leg servo)
            step_period_ms: Time for one full step cycle (both groups)
        """
        self.servos = servo_pwms
        self.step_period_ms = step_period_ms
        self.phase = 0.0  # 0-1 cycle phase

        # Per-servo calibration (override with actual values after testing)
        self.swing_angles = [DEFAULT_SWING_ANGLE] * 6
        self.stance_angles = [DEFAULT_STANCE_ANGLE] * 6
        self.neutral_angles = [DEFAULT_NEUTRAL] * 6

        # Speed control
        self.speed = 1.0  # 0.0 = stopped, 1.0 = normal, 2.0 = double speed

    def set_servo_angle(self, servo_idx: int, angle_deg: int):
        """Set a single servo to a specific angle."""
        angle_deg = max(0, min(180, angle_deg))
        # SG90 PWM: 500us (0 deg) to 2500us (180 deg)
        pulse_us = 500 + (angle_deg / 180) * 2000
        self.servos[servo_idx].duty_ns(int(pulse_us * 1000))

    def all_neutral(self):
        """Set all legs to neutral position."""
        for i in range(6):
            self.set_servo_angle(i, self.neutral_angles[i])

    def all_grip(self):
        """All legs in stance position (maximum grip for working)."""
        for i in range(6):
            self.set_servo_angle(i, self.stance_angles[i])

    def step(self, dt_ms: int):
        """Advance the gait by dt_ms milliseconds. Call this in the main loop.

        Generates smooth sinusoidal motion for each leg group.
        """
        if self.speed <= 0:
            return

        # Advance phase
        self.phase += (dt_ms / self.step_period_ms) * self.speed
        self.phase = self.phase % 1.0

        # Convert phase to angle for each leg
        for i in range(6):
            if i in GROUP_A:
                # Group A: phase 0-0.5 = stance (pulling), 0.5-1.0 = swing (reaching)
                group_phase = self.phase
            else:
                # Group B: offset by half cycle (opposite of Group A)
                group_phase = (self.phase + 0.5) % 1.0

            # Sinusoidal interpolation between stance and swing angles
            # sin goes from -1 to 1, map to stance..swing range
            sin_val = math.sin(group_phase * 2 * math.pi)
            mid_angle = (self.swing_angles[i] + self.stance_angles[i]) / 2
            amplitude = (self.swing_angles[i] - self.stance_angles[i]) / 2
            angle = mid_angle + amplitude * sin_val

            self.set_servo_angle(i, int(angle))

    def walk_forward(self, steps: int = 1, step_ms: int = 400):
        """Walk forward a given number of complete step cycles.

        Blocking call — returns after all steps complete.
        """
        total_ms = steps * step_ms
        elapsed = 0
        tick_ms = 20  # 50 Hz update rate

        while elapsed < total_ms:
            self.step(tick_ms)
            time.sleep_ms(tick_ms)
            elapsed += tick_ms

    def walk_backward(self, steps: int = 1, step_ms: int = 400):
        """Walk backward by reversing swing/stance direction."""
        # Swap swing and stance for all legs
        old_swing = self.swing_angles[:]
        old_stance = self.stance_angles[:]
        self.swing_angles = old_stance
        self.stance_angles = old_swing

        self.walk_forward(steps, step_ms)

        # Restore original
        self.swing_angles = old_swing
        self.stance_angles = old_stance

    def turn_left(self, steps: int = 1):
        """Turn left by making right-side legs step bigger than left-side.

        Right legs: 0(FL), 2(ML), 4(RL) — wider swing
        Left legs: 1(FR), 3(MR), 5(RR) — smaller swing
        """
        old_swing = self.swing_angles[:]
        # Increase right-side swing, decrease left-side
        for i in [0, 2, 4]:
            self.swing_angles[i] = min(150, self.swing_angles[i] + 20)
        for i in [1, 3, 5]:
            self.swing_angles[i] = max(70, self.swing_angles[i] - 20)

        self.walk_forward(steps)
        self.swing_angles = old_swing

    def turn_right(self, steps: int = 1):
        """Turn right (opposite of turn_left)."""
        old_swing = self.swing_angles[:]
        for i in [1, 3, 5]:
            self.swing_angles[i] = min(150, self.swing_angles[i] + 20)
        for i in [0, 2, 4]:
            self.swing_angles[i] = max(70, self.swing_angles[i] - 20)

        self.walk_forward(steps)
        self.swing_angles = old_swing

    def calibrate_servo(self, servo_idx: int):
        """Interactive calibration for one servo.

        Sweeps the servo and asks for input via serial console.
        Run this once per servo to find actual min/max angles.
        """
        print(f"Calibrating servo {servo_idx}")
        print("Finding min angle (leg fully back)...")
        for angle in range(90, 0, -5):
            self.set_servo_angle(servo_idx, angle)
            time.sleep_ms(200)
            # In real use: check current draw, listen for grinding
            # The angle where current spikes = mechanical limit

        print("Finding max angle (leg fully forward)...")
        for angle in range(90, 180, 5):
            self.set_servo_angle(servo_idx, angle)
            time.sleep_ms(200)

        self.set_servo_angle(servo_idx, 90)
        print(f"Servo {servo_idx} calibration complete.")
        print(f"Set swing_angles[{servo_idx}] and stance_angles[{servo_idx}] based on results.")
