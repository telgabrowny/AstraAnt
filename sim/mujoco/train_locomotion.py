"""AstraAnt Locomotion Training -- Evolutionary Strategy (ES)

Trains a 6K-param MLP to walk the 8-leg worker ant using OpenAI-style
evolutionary strategy. No gradients needed -- just evaluate perturbed
policies and move toward the ones that walk better.

OpenAI (2017) showed ES matches PPO on MuJoCo locomotion tasks.
ES is simpler, naturally parallel, and works great on CPU.

Expected: ~32K steps/s on CPU. 50M steps in ~30 minutes.
With domain randomization + curriculum: 1-2 hours total.

Usage:
    python train_locomotion.py          # Train
    python train_locomotion.py --eval   # Evaluate best policy
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta

import numpy as np

try:
    import mujoco
except ImportError:
    print("ERROR: pip install mujoco")
    sys.exit(1)

DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(DIR, "worker_ant_8leg.xml")
OUTPUT_DIR = os.path.join(DIR, "training_output")

# ES Hyperparameters
POP_SIZE = 64                  # Perturbations per generation
SIGMA = 0.02                   # Noise standard deviation
LEARNING_RATE = 0.01           # ES learning rate
NUM_GENERATIONS = 10000        # Round 2: 3x more generations
EVAL_STEPS = 500               # 10 seconds per eval (was 6)
PHYSICS_STEPS = 10             # Substeps per control
CONTROL_DT = 0.02

# Policy
OBS_DIM = 34
ACT_DIM = 8
HIDDEN = 64

# Round 2 reward: STABILITY FIRST, speed second.
# "Slow and steady wins the race" -- a bot that never flips is worth
# infinitely more than one that's fast but tumbles.
FWD_REWARD = 0.5               # Reduced from 2.0: forward is nice, not critical
ALIVE_BONUS = 0.2              # Increased from 0.05: survival is #1 priority
ENERGY_COST = 0.002            # Slightly lower: don't punish careful movement
LIFTOFF_COST = 50.0            # 5x increase: flying off = mission failure
TILT_COST = 2.0                # 7x increase: tipping is catastrophic
JERK_COST = 0.01               # 2x increase: smooth = safe = servo longevity
ANGVEL_COST = 0.3              # NEW: penalize spinning/wobbling

# Domain randomization -- heavier emphasis on hard conditions
GRAVITY_LOG_MIN = math.log(5.8e-6)
GRAVITY_LOG_MAX = math.log(0.06)
FRICTION_MIN, FRICTION_MAX = 0.3, 0.8
GRIP_MIN, GRIP_MAX = 0.08, 0.30
CURRICULUM_WARMUP = 0.15       # Shorter warmup: get to hard stuff sooner

FOOT_IDS = [3, 5, 7, 9, 11, 13, 15, 17]
CHECKPOINT_INTERVAL = 300


# ============================================================================
# Policy as flat parameter vector
# ============================================================================
def make_policy_shape():
    """Define policy architecture: MLP [34, 64, 64, 8]."""
    shapes = [
        ("pw1", (OBS_DIM, HIDDEN)),
        ("pb1", (HIDDEN,)),
        ("pw2", (HIDDEN, HIDDEN)),
        ("pb2", (HIDDEN,)),
        ("pw3", (HIDDEN, ACT_DIM)),
        ("pb3", (ACT_DIM,)),
    ]
    total = sum(s[0] * s[1] if len(s) == 2 else s[0]
                for _, s in shapes)
    return shapes, total


def init_params():
    """Initialize flat parameter vector."""
    shapes, total = make_policy_shape()
    params = np.random.randn(total).astype(np.float32) * 0.02
    return params


def unpack_params(flat):
    """Unpack flat vector into weight matrices."""
    shapes, _ = make_policy_shape()
    params = {}
    idx = 0
    for name, shape in shapes:
        size = 1
        for s in shape:
            size *= s
        params[name] = flat[idx:idx + size].reshape(shape)
        idx += size
    return params


def policy_forward(params, obs):
    """Forward pass. obs: (batch, 34) -> actions: (batch, 8)."""
    x = np.tanh(obs @ params["pw1"] + params["pb1"])
    x = np.tanh(x @ params["pw2"] + params["pb2"])
    return np.tanh(x @ params["pw3"] + params["pb3"]) * 0.524


# ============================================================================
# Environment evaluation
# ============================================================================
def evaluate_policy(flat_params, mj_model, gravity, friction, grip,
                    eval_steps=EVAL_STEPS):
    """Run one episode, return total reward."""
    params = unpack_params(flat_params)
    data = mujoco.MjData(mj_model)
    mujoco.mj_resetData(mj_model, data)
    mj_model.opt.gravity[:] = [0, 0, -gravity]

    gid = 0
    mj_model.geom_friction[gid, 0] = friction

    total_reward = 0.0
    prev_action = np.zeros(ACT_DIM)

    for step in range(eval_steps):
        # Observation
        obs = np.zeros(OBS_DIM, dtype=np.float32)
        obs[:8] = data.qpos[7:15]
        obs[8:16] = data.qvel[6:14] * 0.1
        obs[16:20] = data.qpos[3:7]
        obs[20:23] = data.qvel[3:6] * 0.1
        obs[23:26] = data.qvel[0:3] * 0.1
        for j, fid in enumerate(FOOT_IDS):
            obs[26 + j] = 1.0 if data.xpos[fid, 2] < 0.012 else 0.0

        # Action
        action = policy_forward(params, obs.reshape(1, -1)).squeeze()
        data.ctrl[:ACT_DIM] = action

        # Grip
        data.xfrc_applied[:] = 0.0
        for fid in FOOT_IDS:
            if data.xpos[fid, 2] < 0.012:
                data.xfrc_applied[fid, 2] = -grip

        # Physics
        prev_x = float(data.qpos[0])
        for _ in range(PHYSICS_STEPS):
            mujoco.mj_step(mj_model, data)

        # Reward
        fwd_vel = (float(data.qpos[0]) - prev_x) / CONTROL_DT
        body_z = float(data.qpos[2])
        quat = data.qpos[3:7]
        up_z = 1.0 - 2.0 * (quat[1]**2 + quat[2]**2)
        tilt = math.acos(max(-1, min(1, up_z)))
        torque_sq = float(np.sum(data.qfrc_actuator[6:14]**2))
        jerk = float(np.sum((action - prev_action)**2))

        # Angular velocity penalty (wobbling = bad)
        angvel_sq = float(np.sum(data.qvel[3:6]**2))

        reward = (FWD_REWARD * fwd_vel
                  + ALIVE_BONUS
                  - ENERGY_COST * torque_sq
                  - LIFTOFF_COST * max(0, body_z - 0.07)
                  - TILT_COST * tilt
                  - JERK_COST * jerk
                  - ANGVEL_COST * angvel_sq)
        total_reward += reward
        prev_action = action

        # Early termination
        if body_z > 0.15 or body_z < -0.01 or tilt > 1.5:
            total_reward -= 50  # Harsh penalty for catastrophic failure
            break

    return total_reward


# ============================================================================
# Training
# ============================================================================
def train():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, "training_log.txt")

    # Clear old log
    with open(log_path, "w") as f:
        pass

    def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        with open(log_path, "a") as f:
            f.write(line + "\n")

    log("=" * 70)
    log("AstraAnt Locomotion Training (Evolutionary Strategy)")
    log("=" * 70)

    mj_model = mujoco.MjModel.from_xml_path(MODEL_PATH)
    _, param_count = make_policy_shape()

    # Warm-start from round 1 if available
    r1_path = os.path.join(OUTPUT_DIR, "best_policy.npz")
    if os.path.exists(r1_path):
        log("Warm-starting from round 1 best policy...")
        r1_data = np.load(r1_path)
        flat_params = r1_data["params"].copy()
        # Archive round 1
        r1_archive = os.path.join(OUTPUT_DIR, "round1_best_policy.npz")
        if not os.path.exists(r1_archive):
            np.savez(r1_archive, params=flat_params)
            log(f"  Round 1 archived to {r1_archive}")
    else:
        log("Cold start (no previous policy found)")
        flat_params = init_params()

    log(f"Policy params: {param_count:,} ({param_count * 4 / 1024:.1f} KB)")
    log(f"Population: {POP_SIZE}, Generations: {NUM_GENERATIONS}")
    log(f"Eval: {EVAL_STEPS} steps/episode ({EVAL_STEPS * CONTROL_DT:.0f}s)")
    log(f"Sigma: {SIGMA}, LR: {LEARNING_RATE}")
    log("")

    best_reward = -float("inf")
    best_params = flat_params.copy()
    reward_history = []
    last_ckpt = time.time()
    start_time = time.time()

    for gen in range(NUM_GENERATIONS):
        progress = gen / NUM_GENERATIONS

        # Domain randomization for this generation
        if progress < CURRICULUM_WARMUP:
            frac = progress / CURRICULUM_WARMUP
            log_min = GRAVITY_LOG_MAX * (1 - frac) + GRAVITY_LOG_MIN * frac
        else:
            log_min = GRAVITY_LOG_MIN

        # Each member gets different conditions
        gravities = np.exp(np.random.uniform(log_min, GRAVITY_LOG_MAX, POP_SIZE))
        frictions = np.random.uniform(FRICTION_MIN, FRICTION_MAX, POP_SIZE)
        grips = np.random.uniform(GRIP_MIN, GRIP_MAX, POP_SIZE)

        # Generate noise perturbations (mirrored sampling for variance reduction)
        noise = np.random.randn(POP_SIZE // 2, param_count).astype(np.float32)
        noise = np.concatenate([noise, -noise], axis=0)  # Mirrored

        # Evaluate all perturbations
        rewards = np.zeros(POP_SIZE)
        for i in range(POP_SIZE):
            perturbed = flat_params + SIGMA * noise[i]
            rewards[i] = evaluate_policy(
                perturbed, mj_model, gravities[i], frictions[i], grips[i])

        # Rank-based fitness shaping (more robust than raw rewards)
        ranks = np.zeros(POP_SIZE)
        sorted_idx = np.argsort(rewards)
        for rank, idx in enumerate(sorted_idx):
            ranks[idx] = rank
        # Normalize ranks to [-0.5, 0.5]
        shaped = (ranks / (POP_SIZE - 1)) - 0.5

        # ES gradient estimate
        gradient = np.dot(shaped, noise) / (POP_SIZE * SIGMA)

        # Update parameters
        flat_params += LEARNING_RATE * gradient

        # Adaptive learning rate decay
        if gen > NUM_GENERATIONS * 0.7:
            lr_scale = 1.0 - (gen / NUM_GENERATIONS - 0.7) / 0.3
            flat_params += (LEARNING_RATE * lr_scale - LEARNING_RATE) * gradient

        # Track stats
        mean_reward = rewards.mean()
        max_reward = rewards.max()
        reward_history.append(float(mean_reward))

        if max_reward > best_reward:
            best_reward = max_reward
            best_params = (flat_params + SIGMA * noise[rewards.argmax()]).copy()

        # Logging
        if gen % 5 == 0:
            elapsed = time.time() - start_time
            gens_per_sec = (gen + 1) / elapsed
            eta = (NUM_GENERATIONS - gen) / max(gens_per_sec, 0.01)
            steps_done = (gen + 1) * POP_SIZE * EVAL_STEPS
            sps = steps_done / elapsed

            g_mean = f"{gravities.mean():.2e}"
            log(f"  gen {gen:5d}/{NUM_GENERATIONS} | mean_r {mean_reward:>7.1f} "
                f"| max_r {max_reward:>7.1f} | best {best_reward:>7.1f} "
                f"| g={g_mean} | {sps:,.0f} sps "
                f"| ETA {timedelta(seconds=int(eta))}")

        # Checkpoint
        if time.time() - last_ckpt > CHECKPOINT_INTERVAL:
            np.savez(os.path.join(OUTPUT_DIR, "checkpoint.npz"),
                     params=flat_params, best_params=best_params,
                     generation=gen, best_reward=best_reward)
            np.savez(os.path.join(OUTPUT_DIR, "best_policy.npz"),
                     params=best_params)
            with open(os.path.join(OUTPUT_DIR, "reward_history.json"), "w") as f:
                json.dump(reward_history, f)
            last_ckpt = time.time()
            log(f"  ** Checkpoint (gen={gen}, best={best_reward:.1f})")

    # Final save
    elapsed = time.time() - start_time
    np.savez(os.path.join(OUTPUT_DIR, "best_policy.npz"), params=best_params)
    np.savez(os.path.join(OUTPUT_DIR, "final_policy.npz"), params=flat_params)
    with open(os.path.join(OUTPUT_DIR, "reward_history.json"), "w") as f:
        json.dump(reward_history, f)

    total_steps = NUM_GENERATIONS * POP_SIZE * EVAL_STEPS
    log("")
    log("=" * 70)
    log("  TRAINING COMPLETE")
    log("=" * 70)
    log(f"  Time: {timedelta(seconds=int(elapsed))}")
    log(f"  Generations: {NUM_GENERATIONS}")
    log(f"  Total env steps: {total_steps:,}")
    log(f"  Best reward: {best_reward:.2f}")
    log(f"  Policy: {OUTPUT_DIR}/best_policy.npz ({param_count * 4 / 1024:.1f} KB)")
    log(f"  Evaluate: python train_locomotion.py --eval")
    log("=" * 70)


def evaluate():
    """Evaluate saved policy across all asteroids."""
    path = os.path.join(OUTPUT_DIR, "best_policy.npz")
    if not os.path.exists(path):
        print("No policy found. Train first.")
        return

    data = np.load(path)
    flat_params = data["params"]
    params = unpack_params(flat_params)
    _, pc = make_policy_shape()
    print(f"Policy: {pc:,} params")

    mj_model = mujoco.MjModel.from_xml_path(MODEL_PATH)
    asteroids = [
        ("Bennu", 5.8e-6), ("Itokawa", 8.6e-6), ("2008 EV5", 1.4e-5),
        ("Ryugu", 1.1e-4), ("Didymos", 3.6e-4),
        ("Eros", 5.9e-3), ("Psyche", 0.06),
    ]

    print(f"\n{'Asteroid':>10} | {'Forward':>10} | {'Tilt':>8} | {'Reward':>8} | {'Stable':>6}")
    print("-" * 55)

    for name, g in asteroids:
        reward = evaluate_policy(flat_params, mj_model, g, 0.5, 0.15,
                                  eval_steps=500)
        # Quick forward/tilt check
        mj_model.opt.gravity[:] = [0, 0, -g]
        mj_data = mujoco.MjData(mj_model)
        mj_data.ctrl[:] = 0
        x0 = 0.0
        max_tilt = 0.0
        for step in range(500):
            obs = np.zeros((1, OBS_DIM), dtype=np.float32)
            obs[0, :8] = mj_data.qpos[7:15]
            obs[0, 8:16] = mj_data.qvel[6:14] * 0.1
            obs[0, 16:20] = mj_data.qpos[3:7]
            obs[0, 20:23] = mj_data.qvel[3:6] * 0.1
            obs[0, 23:26] = mj_data.qvel[0:3] * 0.1
            for j, fid in enumerate(FOOT_IDS):
                obs[0, 26+j] = 1.0 if mj_data.xpos[fid, 2] < 0.012 else 0.0
            action = policy_forward(params, obs).squeeze()
            mj_data.ctrl[:ACT_DIM] = action
            mj_data.xfrc_applied[:] = 0
            for fid in FOOT_IDS:
                if mj_data.xpos[fid, 2] < 0.012:
                    mj_data.xfrc_applied[fid, 2] = -0.15
            for _ in range(PHYSICS_STEPS):
                mujoco.mj_step(mj_model, mj_data)
            quat = mj_data.qpos[3:7]
            up_z = 1 - 2*(quat[1]**2 + quat[2]**2)
            t = math.degrees(math.acos(max(-1, min(1, up_z))))
            max_tilt = max(max_tilt, t)

        fwd = float(mj_data.qpos[0]) * 1000
        stable = "YES" if max_tilt < 15 else "NO"
        print(f"{name:>10} | {fwd:>8.1f} mm | {max_tilt:>6.1f} | "
              f"{reward:>8.1f} | {stable:>6}")

    # Compare to sinusoidal baseline
    print("\n--- Sinusoidal Baseline (hand-tuned) ---")
    print(f"{'Asteroid':>10} | {'Forward':>10} | {'Tilt':>8} | {'Stable':>6}")
    print("-" * 45)

    for name, g in asteroids:
        mj_model.opt.gravity[:] = [0, 0, -g]
        mj_data = mujoco.MjData(mj_model)
        GROUP_A = [0, 3, 4, 7]
        phase = 0.0
        max_tilt = 0.0
        for step in range(500):
            phase = (phase + CONTROL_DT / 0.4) % 1.0
            for i in range(8):
                gp = phase if i in GROUP_A else (phase + 0.5) % 1.0
                mj_data.ctrl[i] = 0.524 * math.sin(gp * 2 * math.pi)
            mj_data.xfrc_applied[:] = 0
            for fid in FOOT_IDS:
                if mj_data.xpos[fid, 2] < 0.012:
                    mj_data.xfrc_applied[fid, 2] = -0.15
            for _ in range(PHYSICS_STEPS):
                mujoco.mj_step(mj_model, mj_data)
            quat = mj_data.qpos[3:7]
            up_z = 1 - 2*(quat[1]**2 + quat[2]**2)
            t = math.degrees(math.acos(max(-1, min(1, up_z))))
            max_tilt = max(max_tilt, t)
        fwd = float(mj_data.qpos[0]) * 1000
        stable = "YES" if max_tilt < 15 else "NO"
        print(f"{name:>10} | {fwd:>8.1f} mm | {max_tilt:>6.1f} | {stable:>6}")

    print("\nDone.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="store_true")
    args = parser.parse_args()
    if args.eval:
        evaluate()
    else:
        train()


if __name__ == "__main__":
    main()
