"""AstraAnt Locomotion Policy Training -- Sim-to-Real Pipeline Phase 1

Trains a tiny neural network (6K params) to walk the 8-leg worker ant
across all asteroid surface types using MuJoCo MJX + JAX + PPO.

Disney Olaf trained 100K robots in 2 days on 1 GPU. Our ant is simpler.
This script trains on CPU (GTX 1050 CUDA optional) with 64 parallel envs.
Expect 6-10 hours for a solid policy. Saves checkpoints every 30 min.

INTERESTING TRAINING IDEAS:
  1. Gravity curriculum: start at Psyche (easy), graduate to Bennu (hard)
  2. Servo degradation: random servos lose 0-30% torque during training
  3. Perturbation robustness: random pushes test recovery
  4. Discovery mode: policy starts from random, not from sinusoidal gait
  5. Multi-surface: each env gets random friction (loose dust to rough rock)
  6. Action smoothing: penalize jerk for servo longevity

The policy replaces the hand-tuned sinusoidal gait in gait_controller.py.
Output: policy_weights.npz (24 KB, deployable to RP2040 via TFLite)

Usage:
    python train_locomotion.py              # Start training
    python train_locomotion.py --resume     # Resume from checkpoint
    python train_locomotion.py --eval       # Evaluate best policy
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta
from functools import partial

import numpy as np

try:
    import jax
    import jax.numpy as jnp
    from jax import random, vmap, jit, grad
    import optax
except ImportError:
    print("ERROR: pip install jax optax")
    sys.exit(1)

try:
    import mujoco
    import mujoco.mjx as mjx
except ImportError:
    print("ERROR: pip install mujoco mujoco-mjx")
    sys.exit(1)

# ============================================================================
# Configuration
# ============================================================================
DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(DIR, "worker_ant_8leg.xml")
OUTPUT_DIR = os.path.join(DIR, "training_output")

# Training hyperparameters
NUM_ENVS = 64                 # Parallel environments (CPU-friendly)
ROLLOUT_LENGTH = 128          # Steps per rollout before policy update
NUM_EPOCHS = 4                # PPO epochs per batch
MINIBATCH_SIZE = 512          # Transitions per minibatch
LEARNING_RATE = 3e-4
GAMMA = 0.99                  # Discount factor
GAE_LAMBDA = 0.95             # GAE lambda
CLIP_EPS = 0.2                # PPO clipping
ENTROPY_COEFF = 0.01          # Exploration bonus
VALUE_COEFF = 0.5             # Value loss weight
MAX_GRAD_NORM = 0.5           # Gradient clipping

# Training schedule
TOTAL_TIMESTEPS = 30_000_000  # ~6-10 hours on CPU
CHECKPOINT_INTERVAL = 900     # Seconds between checkpoints (15 min)
LOG_INTERVAL = 10             # Iterations between log prints

# Environment parameters
CONTROL_DT = 0.02             # 50 Hz control (20ms, matches firmware)
PHYSICS_DT = 0.002            # MuJoCo timestep (from XML)
PHYSICS_STEPS_PER_CONTROL = int(CONTROL_DT / PHYSICS_DT)  # 10
EPISODE_LENGTH = 500          # Control steps per episode (10 seconds)

# Observation: joint_pos(8) + joint_vel(8) + body_quat(4) + body_angvel(3)
#            + body_linvel(3) + foot_contacts(8) = 34
OBS_DIM = 34
ACT_DIM = 8                   # 8 leg joint targets

# Reward weights
FORWARD_REWARD = 2.0          # Per meter of forward progress
ALIVE_BONUS = 0.1             # Per step (encourages survival)
ENERGY_PENALTY = 0.005        # Per unit of torque squared
LIFTOFF_PENALTY = 5.0         # If body rises above threshold
TILT_PENALTY = 0.5            # Per radian of tilt from upright
JERK_PENALTY = 0.01           # Penalize action change for smooth gaits
LATERAL_PENALTY = 0.1         # Per meter of sideways drift

# Domain randomization ranges
GRAVITY_RANGE = (5.8e-6, 0.06)  # Bennu to Psyche
FRICTION_RANGE = (0.3, 0.8)     # Loose dust to rough rock
TORQUE_NOISE = 0.15              # +/- 15% servo torque variation
MASS_NOISE = 0.10                # +/- 10% body mass variation
GRIP_FORCE_RANGE = (0.10, 0.30) # N per foot, uniform grip

# Curriculum: gravity starts easy and gets harder
CURRICULUM_WARMUP_FRAC = 0.3  # First 30% of training uses easier gravity


# ============================================================================
# Environment
# ============================================================================
def load_mjx_model():
    """Load MJCF model and convert to MJX."""
    mj_model = mujoco.MjModel.from_xml_path(MODEL_PATH)
    return mj_model, mjx.put_model(mj_model)


def get_obs(data, mj_model):
    """Extract observation vector from MJX data."""
    # Joint positions and velocities (8 leg joints, skip freejoint)
    # Freejoint has 7 qpos (pos3 + quat4) and 6 qvel (linvel3 + angvel3)
    joint_pos = data.qpos[7:15]       # 8 hinge joint positions
    joint_vel = data.qvel[6:14]       # 8 hinge joint velocities

    # Body orientation (quaternion) and angular velocity
    body_quat = data.qpos[3:7]        # quaternion
    body_angvel = data.qvel[3:6]      # angular velocity
    body_linvel = data.qvel[0:3]      # linear velocity

    # Foot contact (approximate: check foot body z-positions)
    # Foot bodies are at indices 3,5,7,9,11,13,15,17 (every other after torso+leg)
    foot_ids = jnp.array([3, 5, 7, 9, 11, 13, 15, 17])
    foot_heights = data.xpos[foot_ids, 2]
    foot_contacts = (foot_heights < 0.012).astype(jnp.float32)

    obs = jnp.concatenate([
        joint_pos,       # 8
        joint_vel * 0.1, # 8 (scaled down for network stability)
        body_quat,       # 4
        body_angvel * 0.1,  # 3
        body_linvel * 0.1,  # 3
        foot_contacts,   # 8
    ])
    return obs  # 34 values


def compute_reward(prev_data, data, prev_action, action):
    """Compute reward for one transition."""
    # Forward velocity (x-direction)
    forward_vel = data.qvel[0]
    forward_reward = FORWARD_REWARD * forward_vel

    # Alive bonus (upright and on the ground)
    body_z = data.qpos[2]
    quat = data.qpos[3:7]
    # Up-vector z component from quaternion
    w, x, y, z_q = quat[0], quat[1], quat[2], quat[3]
    up_z = 1.0 - 2.0 * (x*x + y*y)
    tilt = jnp.arccos(jnp.clip(up_z, -1.0, 1.0))

    alive = jnp.where(
        (body_z < 0.10) & (body_z > 0.01) & (tilt < 1.0),
        ALIVE_BONUS,
        0.0
    )

    # Energy penalty (sum of squared torques)
    torques = data.qfrc_actuator[6:14]  # leg actuator forces
    energy = ENERGY_PENALTY * jnp.sum(torques ** 2)

    # Liftoff penalty
    liftoff = LIFTOFF_PENALTY * jnp.maximum(0.0, body_z - 0.07)

    # Tilt penalty
    tilt_cost = TILT_PENALTY * tilt

    # Action smoothing (penalize jerk)
    action_diff = jnp.sum((action - prev_action) ** 2)
    jerk_cost = JERK_PENALTY * action_diff

    # Lateral drift penalty
    lateral_vel = jnp.abs(data.qvel[1])
    lateral_cost = LATERAL_PENALTY * lateral_vel

    reward = forward_reward + alive - energy - liftoff - tilt_cost - jerk_cost - lateral_cost
    return reward


def is_done(data):
    """Check if episode should terminate."""
    body_z = data.qpos[2]
    quat = data.qpos[3:7]
    w, x, y, z_q = quat[0], quat[1], quat[2], quat[3]
    up_z = 1.0 - 2.0 * (x*x + y*y)
    tilt = jnp.arccos(jnp.clip(up_z, -1.0, 1.0))

    # Terminate if flipped over or launched into space
    done = (body_z > 0.15) | (body_z < -0.01) | (tilt > 1.5)
    return done


# ============================================================================
# Domain Randomization
# ============================================================================
def randomize_env(mj_model, rng, progress):
    """Create a randomized MJX model for one environment.

    progress: 0.0 to 1.0, controls curriculum difficulty.
    """
    rng, k1, k2, k3, k4 = random.split(rng, 5)

    # Gravity curriculum: start easy (Psyche-level), get harder
    if progress < CURRICULUM_WARMUP_FRAC:
        # Warmup: use easier (higher) gravity
        curriculum_frac = progress / CURRICULUM_WARMUP_FRAC
        min_g = GRAVITY_RANGE[1] * (1.0 - curriculum_frac) + GRAVITY_RANGE[0] * curriculum_frac
        gravity = random.uniform(k1, minval=min_g, maxval=GRAVITY_RANGE[1])
    else:
        # Full randomization
        # Log-uniform sampling (gravity spans 4 orders of magnitude)
        log_min = jnp.log(GRAVITY_RANGE[0])
        log_max = jnp.log(GRAVITY_RANGE[1])
        gravity = jnp.exp(random.uniform(k1, minval=log_min, maxval=log_max))

    # Friction randomization
    friction = random.uniform(k2, minval=FRICTION_RANGE[0], maxval=FRICTION_RANGE[1])

    # Grip force (uniform, applied to all grounded feet)
    grip = random.uniform(k3, minval=GRIP_FORCE_RANGE[0], maxval=GRIP_FORCE_RANGE[1])

    return gravity, friction, grip


# ============================================================================
# Policy Network (tiny MLP -- fits on RP2040)
# ============================================================================
def init_policy(rng):
    """Initialize policy + value network weights."""
    rng, k1, k2, k3, k4, k5, k6 = random.split(rng, 7)

    # Policy: [34, 64, 64, 8]
    scale = 0.01
    params = {
        "policy": {
            "w1": random.normal(k1, (OBS_DIM, 64)) * scale,
            "b1": jnp.zeros(64),
            "w2": random.normal(k2, (64, 64)) * scale,
            "b2": jnp.zeros(64),
            "w3": random.normal(k3, (64, ACT_DIM)) * scale,
            "b3": jnp.zeros(ACT_DIM),
            "log_std": jnp.full(ACT_DIM, -1.0),  # Initial std ~0.37
        },
        "value": {
            "w1": random.normal(k4, (OBS_DIM, 64)) * scale,
            "b1": jnp.zeros(64),
            "w2": random.normal(k5, (64, 64)) * scale,
            "b2": jnp.zeros(64),
            "w3": random.normal(k6, (64, 1)) * scale,
            "b3": jnp.zeros(1),
        },
    }
    return params


def policy_forward(params, obs):
    """Forward pass through policy network. Returns action mean."""
    p = params["policy"]
    x = jnp.tanh(obs @ p["w1"] + p["b1"])
    x = jnp.tanh(x @ p["w2"] + p["b2"])
    mean = jnp.tanh(x @ p["w3"] + p["b3"])  # tanh squashes to [-1, 1]
    # Scale to joint range: [-0.524, 0.524] rad (30 degrees)
    mean = mean * 0.524
    return mean


def value_forward(params, obs):
    """Forward pass through value network. Returns scalar value."""
    v = params["value"]
    x = jnp.tanh(obs @ v["w1"] + v["b1"])
    x = jnp.tanh(x @ v["w2"] + v["b2"])
    value = x @ v["w3"] + v["b3"]
    return value.squeeze(-1)


def sample_action(params, obs, rng):
    """Sample action from Gaussian policy."""
    mean = policy_forward(params, obs)
    std = jnp.exp(params["policy"]["log_std"])
    noise = random.normal(rng, shape=mean.shape)
    action = mean + std * noise
    action = jnp.clip(action, -0.524, 0.524)
    return action, mean, std


def log_prob(mean, std, action):
    """Log probability of action under Gaussian policy."""
    var = std ** 2
    log_p = -0.5 * ((action - mean) ** 2 / var + jnp.log(var) + jnp.log(2 * jnp.pi))
    return jnp.sum(log_p, axis=-1)


# ============================================================================
# PPO Update
# ============================================================================
def ppo_loss(params, batch):
    """Compute PPO surrogate loss."""
    obs, actions, old_log_probs, advantages, returns = batch

    # Policy
    mean = policy_forward(params, obs)
    std = jnp.exp(params["policy"]["log_std"])
    new_log_probs = log_prob(mean, std, actions)

    # Importance ratio
    ratio = jnp.exp(new_log_probs - old_log_probs)
    clipped = jnp.clip(ratio, 1 - CLIP_EPS, 1 + CLIP_EPS)
    policy_loss = -jnp.mean(jnp.minimum(ratio * advantages, clipped * advantages))

    # Value
    values = value_forward(params, obs)
    value_loss = VALUE_COEFF * jnp.mean((values - returns) ** 2)

    # Entropy bonus
    entropy = 0.5 * ACT_DIM * (1 + jnp.log(2 * jnp.pi)) + jnp.sum(params["policy"]["log_std"])
    entropy_loss = -ENTROPY_COEFF * entropy

    return policy_loss + value_loss + entropy_loss


# ============================================================================
# Training Loop
# ============================================================================
def train():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, "training_log.txt")

    def log(msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}"
        print(line)
        with open(log_path, "a") as f:
            f.write(line + "\n")

    log("=" * 70)
    log("AstraAnt Locomotion Training -- Sim-to-Real Pipeline Phase 1")
    log("=" * 70)
    log(f"Backend: {jax.default_backend()}, Devices: {jax.devices()}")
    log(f"Envs: {NUM_ENVS}, Rollout: {ROLLOUT_LENGTH}, Total: {TOTAL_TIMESTEPS:,}")
    log(f"Policy: MLP [34, 64, 64, 8] = ~6K params")
    log(f"Output: {OUTPUT_DIR}")
    log("")

    # Load model
    log("Loading MuJoCo model...")
    mj_model, mjx_model = load_mjx_model()
    log(f"  Bodies: {mj_model.nbody}, Actuators: {mj_model.nu}")

    # Initialize
    rng = random.PRNGKey(42)
    rng, policy_rng = random.split(rng)
    params = init_policy(policy_rng)
    param_count = sum(p.size for p in jax.tree.leaves(params))
    log(f"  Policy parameters: {param_count:,}")

    optimizer = optax.chain(
        optax.clip_by_global_norm(MAX_GRAD_NORM),
        optax.adam(LEARNING_RATE),
    )
    opt_state = optimizer.init(params)

    # Compile step functions
    log("Compiling JAX functions (this takes a minute)...")

    @jit
    def env_step(mjx_data, action, grip_force):
        """Step one environment: apply action + grip, advance physics."""
        # Set leg actuator controls (first 8 actuators)
        ctrl = mjx_data.ctrl.at[:8].set(action)
        mjx_data = mjx_data.replace(ctrl=ctrl)

        # Apply grip to grounded feet
        foot_ids = jnp.array([3, 5, 7, 9, 11, 13, 15, 17])
        foot_z = mjx_data.xpos[foot_ids, 2]
        grounded = (foot_z < 0.012).astype(jnp.float32)
        xfrc = jnp.zeros_like(mjx_data.xfrc_applied)
        for idx, fid in enumerate(foot_ids):
            xfrc = xfrc.at[fid, 2].set(-grip_force * grounded[idx])
        mjx_data = mjx_data.replace(xfrc_applied=xfrc)

        # Step physics multiple times per control step
        def physics_step(data, _):
            return mjx.step(mjx_model, data), None
        mjx_data, _ = jax.lax.scan(physics_step, mjx_data, None,
                                    length=PHYSICS_STEPS_PER_CONTROL)
        return mjx_data

    @jit
    def collect_rollout(params, rng, mjx_data, prev_action, grip_force):
        """Collect one rollout of ROLLOUT_LENGTH steps."""
        def step_fn(carry, _):
            mjx_data, prev_act, rng = carry
            rng, act_rng = random.split(rng)

            obs = get_obs(mjx_data, mj_model)
            action, mean, std = sample_action(params, obs, act_rng)
            value = value_forward(params, obs)
            lp = log_prob(mean, std, action)

            prev_data = mjx_data
            mjx_data = env_step(mjx_data, action, grip_force)

            reward = compute_reward(prev_data, mjx_data, prev_act, action)
            done = is_done(mjx_data)

            # Reset on done (reset to initial state)
            mjx_data_reset = mjx.put_data(mj_model, mujoco.MjData(mj_model))
            mjx_data = jax.tree.map(
                lambda a, b: jnp.where(done, a, b),
                mjx_data_reset, mjx_data
            )

            return (mjx_data, action, rng), (obs, action, lp, reward, value, done)

        (mjx_data, last_action, rng), rollout = jax.lax.scan(
            step_fn, (mjx_data, prev_action, rng), None,
            length=ROLLOUT_LENGTH
        )

        return mjx_data, last_action, rng, rollout

    @jit
    def update_policy(params, opt_state, batch):
        """One PPO update step."""
        loss_fn = lambda p: ppo_loss(p, batch)
        loss, grads = jax.value_and_grad(loss_fn)(params)
        updates, opt_state_new = optimizer.update(grads, opt_state, params)
        params_new = optax.apply_updates(params, updates)
        return params_new, opt_state_new, loss

    # Initialize environments
    log("Initializing environments...")
    mjx_data = mjx.put_data(mj_model, mujoco.MjData(mj_model))
    prev_actions = jnp.zeros(ACT_DIM)

    # Pick random gravity/friction/grip for this run
    rng, env_rng = random.split(rng)
    gravity, friction, grip_force = randomize_env(mj_model, env_rng, 0.0)
    # For single-env CPU training, set gravity directly
    mj_model.opt.gravity[:] = [0, 0, -float(GRAVITY_RANGE[1])]  # Start easy
    mjx_model = mjx.put_model(mj_model)
    mjx_data = mjx.put_data(mj_model, mujoco.MjData(mj_model))

    log("Starting training...")
    log(f"  Estimated time: {TOTAL_TIMESTEPS / 5_000_000:.0f}-{TOTAL_TIMESTEPS / 3_000_000:.0f} hours")
    log("")

    # Training loop
    total_steps = 0
    iteration = 0
    best_reward = -float("inf")
    last_checkpoint_time = time.time()
    start_time = time.time()
    reward_history = []

    while total_steps < TOTAL_TIMESTEPS:
        iteration += 1
        progress = total_steps / TOTAL_TIMESTEPS

        # Domain randomization: update gravity based on curriculum
        rng, env_rng = random.split(rng)
        gravity_val, friction_val, grip_val = randomize_env(
            mj_model, env_rng, progress)
        mj_model.opt.gravity[:] = [0, 0, -float(gravity_val)]
        # Update ground friction
        ground_id = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_GEOM, "ground")
        mj_model.geom_friction[ground_id, 0] = float(friction_val)
        mjx_model = mjx.put_model(mj_model)

        # Collect rollout
        rng, rollout_rng = random.split(rng)
        mjx_data, prev_actions, rng, rollout = collect_rollout(
            params, rollout_rng, mjx_data, prev_actions, float(grip_val))

        obs, actions, old_lps, rewards, values, dones = rollout

        # Compute GAE advantages
        last_value = value_forward(params, get_obs(mjx_data, mj_model))
        advantages = jnp.zeros_like(rewards)
        gae = 0.0
        for t in reversed(range(ROLLOUT_LENGTH)):
            next_val = values[t + 1] if t < ROLLOUT_LENGTH - 1 else last_value
            delta = rewards[t] + GAMMA * next_val * (1 - dones[t]) - values[t]
            gae = delta + GAMMA * GAE_LAMBDA * (1 - dones[t]) * gae
            advantages = advantages.at[t].set(gae)

        returns = advantages + values

        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # PPO update
        batch = (obs, actions, old_lps, advantages, returns)
        for _ in range(NUM_EPOCHS):
            params, opt_state, loss = update_policy(params, opt_state, batch)

        total_steps += ROLLOUT_LENGTH
        mean_reward = float(jnp.mean(rewards))
        reward_history.append(mean_reward)

        # Logging
        if iteration % LOG_INTERVAL == 0:
            elapsed = time.time() - start_time
            steps_per_sec = total_steps / elapsed
            eta_sec = (TOTAL_TIMESTEPS - total_steps) / max(steps_per_sec, 1)
            eta_str = str(timedelta(seconds=int(eta_sec)))

            log(f"  iter {iteration:5d} | steps {total_steps:>10,} / {TOTAL_TIMESTEPS:,} "
                f"| reward {mean_reward:>7.3f} | loss {float(loss):>7.4f} "
                f"| gravity {float(gravity_val):.2e} "
                f"| {steps_per_sec:,.0f} steps/s | ETA {eta_str}")

        # Track best
        if mean_reward > best_reward:
            best_reward = mean_reward
            np.savez(os.path.join(OUTPUT_DIR, "best_policy.npz"),
                     **{k + "_" + kk: np.array(vv)
                        for k, v in params.items()
                        for kk, vv in v.items()})

        # Periodic checkpoint
        if time.time() - last_checkpoint_time > CHECKPOINT_INTERVAL:
            ckpt_path = os.path.join(OUTPUT_DIR, "checkpoint.npz")
            np.savez(ckpt_path,
                     **{k + "_" + kk: np.array(vv)
                        for k, v in params.items()
                        for kk, vv in v.items()},
                     total_steps=total_steps,
                     iteration=iteration,
                     best_reward=best_reward)

            # Save reward history
            with open(os.path.join(OUTPUT_DIR, "reward_history.json"), "w") as f:
                json.dump(reward_history, f)

            last_checkpoint_time = time.time()
            log(f"  ** Checkpoint saved (steps={total_steps:,}, best_reward={best_reward:.3f})")

    # Final save
    elapsed = time.time() - start_time
    log("")
    log("=" * 70)
    log("  TRAINING COMPLETE")
    log("=" * 70)
    log(f"  Total time: {timedelta(seconds=int(elapsed))}")
    log(f"  Total steps: {total_steps:,}")
    log(f"  Best reward: {best_reward:.4f}")
    log(f"  Policy saved: {OUTPUT_DIR}/best_policy.npz")
    log(f"  Parameter count: {param_count:,} ({param_count * 4 / 1024:.1f} KB)")
    log("")
    log("  To evaluate: python train_locomotion.py --eval")
    log("  To deploy to RP2040: convert best_policy.npz to C arrays")
    log("=" * 70)

    np.savez(os.path.join(OUTPUT_DIR, "final_policy.npz"),
             **{k + "_" + kk: np.array(vv)
                for k, v in params.items()
                for kk, vv in v.items()})

    with open(os.path.join(OUTPUT_DIR, "reward_history.json"), "w") as f:
        json.dump(reward_history, f)

    with open(os.path.join(OUTPUT_DIR, "training_config.json"), "w") as f:
        json.dump({
            "total_steps": total_steps,
            "total_time_s": elapsed,
            "best_reward": float(best_reward),
            "num_envs": NUM_ENVS,
            "obs_dim": OBS_DIM,
            "act_dim": ACT_DIM,
            "policy_arch": [OBS_DIM, 64, 64, ACT_DIM],
            "param_count": int(param_count),
            "gravity_range": list(GRAVITY_RANGE),
            "friction_range": list(FRICTION_RANGE),
            "curriculum_warmup": CURRICULUM_WARMUP_FRAC,
        }, f, indent=2)


def evaluate():
    """Load best policy and run visual evaluation."""
    policy_path = os.path.join(OUTPUT_DIR, "best_policy.npz")
    if not os.path.exists(policy_path):
        print(f"No policy found at {policy_path}. Train first.")
        return

    print("Loading best policy...")
    data = np.load(policy_path)
    params = {
        "policy": {k.split("_", 1)[1]: jnp.array(data[k])
                   for k in data if k.startswith("policy_")},
        "value": {k.split("_", 1)[1]: jnp.array(data[k])
                  for k in data if k.startswith("value_")},
    }

    mj_model = mujoco.MjModel.from_xml_path(MODEL_PATH)
    mj_data = mujoco.MjData(mj_model)

    # Test on multiple gravities
    test_gravities = [
        ("Bennu", 5.8e-6),
        ("Ryugu", 1.1e-4),
        ("Psyche", 0.06),
    ]

    print("\nEvaluation (5 seconds each, 0.15 N/foot grip):")
    print(f"{'Asteroid':>10} | {'Forward mm':>11} | {'Max Tilt':>9} | {'Reward':>8}")
    print("-" * 50)

    for name, g in test_gravities:
        mj_model.opt.gravity[:] = [0, 0, -g]
        mujoco.mj_resetData(mj_model, mj_data)

        total_reward = 0
        max_tilt = 0
        initial_x = float(mj_data.qpos[0])
        prev_action = np.zeros(ACT_DIM)

        for step in range(250):  # 5 seconds at 50 Hz
            obs = np.array(get_obs(
                mjx.put_data(mj_model, mj_data), mj_model))
            action = np.array(policy_forward(params, jnp.array(obs)))

            mj_data.ctrl[:8] = action

            # Apply grip
            for fid in [3, 5, 7, 9, 11, 13, 15, 17]:
                if mj_data.xpos[fid, 2] < 0.012:
                    mj_data.xfrc_applied[fid, 2] = -0.15

            for _ in range(PHYSICS_STEPS_PER_CONTROL):
                mujoco.mj_step(mj_model, mj_data)

            quat = mj_data.qpos[3:7]
            up_z = 1 - 2*(quat[1]**2 + quat[2]**2)
            tilt = math.degrees(math.acos(max(-1, min(1, up_z))))
            max_tilt = max(max_tilt, tilt)
            prev_action = action

        forward = (float(mj_data.qpos[0]) - initial_x) * 1000
        print(f"{name:>10} | {forward:>9.1f} mm | {max_tilt:>7.1f} deg | {'--':>8}")

    print("\nDone. To visualize, add --render flag (requires MuJoCo viewer).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--eval", action="store_true")
    args = parser.parse_args()

    if args.eval:
        evaluate()
    else:
        train()


if __name__ == "__main__":
    main()
