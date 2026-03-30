"""AstraAnt Locomotion Policy Training -- CPU-Optimized

Uses regular MuJoCo (not MJX) for physics -- 1000x faster on CPU.
64 parallel environments via vectorized numpy. PPO from scratch.

Trains a 6K-param MLP to walk the 8-leg worker ant on all asteroid
surfaces. Domain randomization across gravity, friction, servo torque.

Expected: ~50K steps/s on CPU. 50M steps in ~17 minutes.
With full evaluation suite: 1-2 hours for thorough training + analysis.

Usage:
    python train_locomotion.py          # Train (runs ~1-2 hours)
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

# ============================================================================
# Configuration
# ============================================================================
NUM_ENVS = 64
ROLLOUT_LENGTH = 256           # Steps per rollout
NUM_EPOCHS = 4                 # PPO epochs per batch
MINIBATCH_SIZE = 1024
LEARNING_RATE = 3e-4
GAMMA = 0.99
GAE_LAMBDA = 0.95
CLIP_EPS = 0.2
ENTROPY_COEFF = 0.005
VALUE_COEFF = 0.5
MAX_GRAD_NORM = 0.5

TOTAL_TIMESTEPS = 50_000_000   # 50M steps
CHECKPOINT_INTERVAL = 300      # Seconds between checkpoints (5 min)
LOG_INTERVAL = 5               # Iterations between prints
EVAL_INTERVAL = 50             # Iterations between full evaluations

CONTROL_DT = 0.02             # 50 Hz control
PHYSICS_STEPS = 10             # Physics substeps per control step
EPISODE_LENGTH = 500           # 10 seconds per episode

OBS_DIM = 34                   # joint_pos(8)+joint_vel(8)+quat(4)+angvel(3)+linvel(3)+contacts(8)
ACT_DIM = 8                   # 8 leg joints

# Reward
FWD_REWARD = 2.0
ALIVE_BONUS = 0.05
ENERGY_COST = 0.003
LIFTOFF_COST = 10.0
TILT_COST = 0.3
JERK_COST = 0.005
LATERAL_COST = 0.05

# Domain randomization
GRAVITY_LOG_MIN = math.log(5.8e-6)   # Bennu
GRAVITY_LOG_MAX = math.log(0.06)     # Psyche
FRICTION_MIN, FRICTION_MAX = 0.3, 0.8
GRIP_MIN, GRIP_MAX = 0.08, 0.30
TORQUE_NOISE = 0.15
CURRICULUM_WARMUP = 0.2

# Foot body indices in MuJoCo (from XML structure)
FOOT_IDS = [3, 5, 7, 9, 11, 13, 15, 17]


# ============================================================================
# Vectorized Environment
# ============================================================================
class VecEnv:
    """64 parallel MuJoCo environments with domain randomization."""

    def __init__(self, num_envs):
        self.n = num_envs
        self.mj_model = mujoco.MjModel.from_xml_path(MODEL_PATH)
        self.envs = [mujoco.MjData(self.mj_model) for _ in range(num_envs)]
        self.step_count = np.zeros(num_envs, dtype=int)
        self.prev_actions = np.zeros((num_envs, ACT_DIM))
        self.episode_rewards = np.zeros(num_envs)
        self.completed_rewards = []

        # Per-env domain randomization parameters
        self.gravities = np.zeros(num_envs)
        self.frictions = np.zeros(num_envs)
        self.grips = np.zeros(num_envs)
        self.torque_scales = np.ones((num_envs, ACT_DIM))  # Per-servo noise

        self.progress = 0.0  # Curriculum progress 0-1

    def randomize_env(self, idx):
        """Set random gravity/friction/grip for one environment."""
        # Gravity curriculum
        if self.progress < CURRICULUM_WARMUP:
            frac = self.progress / CURRICULUM_WARMUP
            log_min = GRAVITY_LOG_MAX * (1 - frac) + GRAVITY_LOG_MIN * frac
        else:
            log_min = GRAVITY_LOG_MIN
        g = np.exp(np.random.uniform(log_min, GRAVITY_LOG_MAX))
        self.gravities[idx] = g

        self.frictions[idx] = np.random.uniform(FRICTION_MIN, FRICTION_MAX)
        self.grips[idx] = np.random.uniform(GRIP_MIN, GRIP_MAX)

        # Per-servo torque variation
        self.torque_scales[idx] = 1.0 + np.random.uniform(
            -TORQUE_NOISE, TORQUE_NOISE, ACT_DIM)

    def reset_env(self, idx):
        """Reset one environment."""
        mujoco.mj_resetData(self.mj_model, self.envs[idx])
        self.step_count[idx] = 0
        self.prev_actions[idx] = 0.0
        self.randomize_env(idx)

        if self.episode_rewards[idx] != 0:
            self.completed_rewards.append(float(self.episode_rewards[idx]))
        self.episode_rewards[idx] = 0.0

    def reset_all(self):
        for i in range(self.n):
            self.reset_env(i)
        return self._get_obs_batch()

    def _get_obs(self, data):
        """Get observation from one MjData."""
        joint_pos = data.qpos[7:15].copy()
        joint_vel = data.qvel[6:14].copy() * 0.1
        body_quat = data.qpos[3:7].copy()
        body_angvel = data.qvel[3:6].copy() * 0.1
        body_linvel = data.qvel[0:3].copy() * 0.1
        foot_contacts = np.array([
            1.0 if data.xpos[fid, 2] < 0.012 else 0.0 for fid in FOOT_IDS])
        return np.concatenate([joint_pos, joint_vel, body_quat,
                               body_angvel, body_linvel, foot_contacts])

    def _get_obs_batch(self):
        return np.array([self._get_obs(e) for e in self.envs])

    def step(self, actions):
        """Step all environments. actions: (num_envs, ACT_DIM)."""
        obs_batch = np.zeros((self.n, OBS_DIM))
        rewards = np.zeros(self.n)
        dones = np.zeros(self.n, dtype=bool)

        for i in range(self.n):
            data = self.envs[i]

            # Apply domain-randomized gravity
            self.mj_model.opt.gravity[:] = [0, 0, -self.gravities[i]]

            # Set ground friction
            gid = 0  # ground is first geom
            self.mj_model.geom_friction[gid, 0] = self.frictions[i]

            # Scale actions by per-servo torque variation
            scaled_action = actions[i] * self.torque_scales[i]
            data.ctrl[:ACT_DIM] = np.clip(scaled_action, -0.524, 0.524)

            # Apply grip to grounded feet
            data.xfrc_applied[:] = 0.0
            for fid in FOOT_IDS:
                if data.xpos[fid, 2] < 0.012:
                    data.xfrc_applied[fid, 2] = -self.grips[i]

            # Physics substeps
            prev_x = float(data.qpos[0])
            for _ in range(PHYSICS_STEPS):
                mujoco.mj_step(self.mj_model, data)

            # Observation
            obs_batch[i] = self._get_obs(data)

            # Reward
            fwd_vel = (float(data.qpos[0]) - prev_x) / CONTROL_DT
            body_z = float(data.qpos[2])
            quat = data.qpos[3:7]
            up_z = 1.0 - 2.0 * (quat[1]**2 + quat[2]**2)
            tilt = math.acos(max(-1, min(1, up_z)))
            lat_vel = abs(float(data.qvel[1]))
            torque_sq = float(np.sum(data.qfrc_actuator[6:14]**2))
            action_diff = float(np.sum((actions[i] - self.prev_actions[i])**2))

            r = (FWD_REWARD * fwd_vel
                 + ALIVE_BONUS
                 - ENERGY_COST * torque_sq
                 - LIFTOFF_COST * max(0, body_z - 0.07)
                 - TILT_COST * tilt
                 - JERK_COST * action_diff
                 - LATERAL_COST * lat_vel)
            rewards[i] = r
            self.episode_rewards[i] += r

            # Done check
            self.step_count[i] += 1
            done = (body_z > 0.15 or body_z < -0.01 or
                    tilt > 1.5 or self.step_count[i] >= EPISODE_LENGTH)
            if done:
                self.reset_env(i)
                obs_batch[i] = self._get_obs(self.envs[i])
            dones[i] = done

        self.prev_actions[:] = actions
        return obs_batch, rewards, dones


# ============================================================================
# Policy Network (numpy)
# ============================================================================
class Policy:
    """Tiny MLP policy + value network. Pure numpy."""

    def __init__(self):
        s = 0.02
        self.params = {
            "pw1": np.random.randn(OBS_DIM, 64).astype(np.float32) * s,
            "pb1": np.zeros(64, dtype=np.float32),
            "pw2": np.random.randn(64, 64).astype(np.float32) * s,
            "pb2": np.zeros(64, dtype=np.float32),
            "pw3": np.random.randn(64, ACT_DIM).astype(np.float32) * s,
            "pb3": np.zeros(ACT_DIM, dtype=np.float32),
            "log_std": np.full(ACT_DIM, -1.0, dtype=np.float32),
            "vw1": np.random.randn(OBS_DIM, 64).astype(np.float32) * s,
            "vb1": np.zeros(64, dtype=np.float32),
            "vw2": np.random.randn(64, 64).astype(np.float32) * s,
            "vb2": np.zeros(64, dtype=np.float32),
            "vw3": np.random.randn(64, 1).astype(np.float32) * s,
            "vb3": np.zeros(1, dtype=np.float32),
        }
        self.optimizer = {k: {"m": np.zeros_like(v), "v": np.zeros_like(v), "t": 0}
                          for k, v in self.params.items()}

    def forward(self, obs):
        """Policy forward: returns action mean. obs: (batch, OBS_DIM)."""
        p = self.params
        x = np.tanh(obs @ p["pw1"] + p["pb1"])
        x = np.tanh(x @ p["pw2"] + p["pb2"])
        mean = np.tanh(x @ p["pw3"] + p["pb3"]) * 0.524
        return mean

    def value(self, obs):
        """Value forward: returns scalar. obs: (batch, OBS_DIM)."""
        p = self.params
        x = np.tanh(obs @ p["vw1"] + p["vb1"])
        x = np.tanh(x @ p["vw2"] + p["vb2"])
        v = (x @ p["vw3"] + p["vb3"]).squeeze(-1)
        return v

    def sample(self, obs):
        """Sample actions. Returns actions, means, log_probs, values."""
        mean = self.forward(obs)
        std = np.exp(self.params["log_std"])
        noise = np.random.randn(*mean.shape).astype(np.float32)
        actions = np.clip(mean + std * noise, -0.524, 0.524)
        log_probs = self._log_prob(mean, std, actions)
        values = self.value(obs)
        return actions, mean, log_probs, values

    def _log_prob(self, mean, std, action):
        var = std ** 2
        lp = -0.5 * ((action - mean)**2 / var + np.log(var) + np.log(2 * np.pi))
        return lp.sum(axis=-1)

    def param_count(self):
        return sum(v.size for v in self.params.values())

    def save(self, path):
        np.savez(path, **self.params)

    def load(self, path):
        data = np.load(path)
        for k in self.params:
            if k in data:
                self.params[k] = data[k]


# ============================================================================
# PPO (numpy, finite differences for gradients)
# ============================================================================
def compute_gae(rewards, values, dones, last_value):
    """Generalized Advantage Estimation."""
    T = len(rewards)
    advantages = np.zeros(T, dtype=np.float32)
    gae = 0.0
    for t in reversed(range(T)):
        next_val = last_value if t == T - 1 else values[t + 1]
        delta = rewards[t] + GAMMA * next_val * (1 - dones[t]) - values[t]
        gae = delta + GAMMA * GAE_LAMBDA * (1 - dones[t]) * gae
        advantages[t] = gae
    returns = advantages + values
    return advantages, returns


def ppo_update(policy, rollout_data):
    """One PPO update using numerical gradients (simple but works)."""
    obs_all, act_all, old_lp_all, adv_all, ret_all = rollout_data
    N = len(obs_all)

    # Normalize advantages
    adv_all = (adv_all - adv_all.mean()) / (adv_all.std() + 1e-8)

    total_loss = 0.0
    for epoch in range(NUM_EPOCHS):
        indices = np.random.permutation(N)
        for start in range(0, N, MINIBATCH_SIZE):
            end = min(start + MINIBATCH_SIZE, N)
            idx = indices[start:end]
            mb_obs = obs_all[idx]
            mb_act = act_all[idx]
            mb_old_lp = old_lp_all[idx]
            mb_adv = adv_all[idx]
            mb_ret = ret_all[idx]

            # Compute current policy outputs
            mean = policy.forward(mb_obs)
            std = np.exp(policy.params["log_std"])
            new_lp = policy._log_prob(mean, std, mb_act)
            values = policy.value(mb_obs)

            # PPO loss components
            ratio = np.exp(new_lp - mb_old_lp)
            clipped = np.clip(ratio, 1 - CLIP_EPS, 1 + CLIP_EPS)
            policy_loss = -np.mean(np.minimum(ratio * mb_adv, clipped * mb_adv))
            value_loss = VALUE_COEFF * np.mean((values - mb_ret) ** 2)
            entropy = 0.5 * ACT_DIM * (1 + np.log(2 * np.pi)) + np.sum(policy.params["log_std"])
            loss = policy_loss + value_loss - ENTROPY_COEFF * entropy

            # Numerical gradient update (parameter perturbation)
            eps = 1e-4
            lr = LEARNING_RATE
            for key in policy.params:
                param = policy.params[key]
                grad = np.zeros_like(param)
                flat = param.ravel()
                # Approximate gradient for a random subset of params
                n_sample = min(50, len(flat))
                sample_idx = np.random.choice(len(flat), n_sample, replace=False)
                for si in sample_idx:
                    old_val = flat[si]
                    flat[si] = old_val + eps
                    mean_p = policy.forward(mb_obs)
                    lp_p = policy._log_prob(mean_p, np.exp(policy.params["log_std"]), mb_act)
                    r_p = np.exp(lp_p - mb_old_lp)
                    loss_p = -np.mean(np.minimum(r_p * mb_adv,
                                                  np.clip(r_p, 1-CLIP_EPS, 1+CLIP_EPS) * mb_adv))
                    flat[si] = old_val - eps
                    mean_m = policy.forward(mb_obs)
                    lp_m = policy._log_prob(mean_m, np.exp(policy.params["log_std"]), mb_act)
                    r_m = np.exp(lp_m - mb_old_lp)
                    loss_m = -np.mean(np.minimum(r_m * mb_adv,
                                                  np.clip(r_m, 1-CLIP_EPS, 1+CLIP_EPS) * mb_adv))
                    flat[si] = old_val
                    grad.ravel()[si] = (loss_p - loss_m) / (2 * eps)

                # Adam update
                opt = policy.optimizer[key]
                opt["t"] += 1
                opt["m"] = 0.9 * opt["m"] + 0.1 * grad
                opt["v"] = 0.999 * opt["v"] + 0.001 * grad**2
                m_hat = opt["m"] / (1 - 0.9**opt["t"])
                v_hat = opt["v"] / (1 - 0.999**opt["t"])
                policy.params[key] -= lr * m_hat / (np.sqrt(v_hat) + 1e-8)

            total_loss += float(loss)

    return total_loss / (NUM_EPOCHS * max(1, N // MINIBATCH_SIZE))


# ============================================================================
# Main Training
# ============================================================================
def train():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_path = os.path.join(OUTPUT_DIR, "training_log.txt")

    def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        with open(log_path, "a") as f:
            f.write(line + "\n")

    log("=" * 70)
    log("AstraAnt Locomotion Training (CPU-Optimized)")
    log("=" * 70)

    env = VecEnv(NUM_ENVS)
    policy = Policy()
    log(f"Envs: {NUM_ENVS}, Policy params: {policy.param_count():,}")
    log(f"Total steps: {TOTAL_TIMESTEPS:,}")
    log("")

    obs = env.reset_all()
    total_steps = 0
    iteration = 0
    best_ep_reward = -float("inf")
    last_ckpt = time.time()
    start_time = time.time()
    reward_history = []

    while total_steps < TOTAL_TIMESTEPS:
        iteration += 1
        env.progress = total_steps / TOTAL_TIMESTEPS

        # Collect rollout
        rollout_obs = []
        rollout_act = []
        rollout_lp = []
        rollout_rew = []
        rollout_val = []
        rollout_done = []

        for _ in range(ROLLOUT_LENGTH):
            actions, means, log_probs, values = policy.sample(obs)
            next_obs, rewards, dones = env.step(actions)

            rollout_obs.append(obs)
            rollout_act.append(actions)
            rollout_lp.append(log_probs)
            rollout_rew.append(rewards)
            rollout_val.append(values)
            rollout_done.append(dones.astype(np.float32))

            obs = next_obs

        steps_this_iter = ROLLOUT_LENGTH * NUM_ENVS
        total_steps += steps_this_iter

        # Stack rollout
        R_obs = np.array(rollout_obs).reshape(-1, OBS_DIM)
        R_act = np.array(rollout_act).reshape(-1, ACT_DIM)
        R_lp = np.array(rollout_lp).reshape(-1)
        R_rew = np.array(rollout_rew)
        R_val = np.array(rollout_val)
        R_done = np.array(rollout_done)

        # GAE per environment
        last_values = policy.value(obs)
        all_adv = np.zeros_like(R_rew)
        all_ret = np.zeros_like(R_rew)
        for i in range(NUM_ENVS):
            adv, ret = compute_gae(R_rew[:, i], R_val[:, i],
                                    R_done[:, i], last_values[i])
            all_adv[:, i] = adv
            all_ret[:, i] = ret

        R_adv = all_adv.reshape(-1)
        R_ret = all_ret.reshape(-1)

        # PPO update
        loss = ppo_update(policy, (R_obs, R_act, R_lp, R_adv, R_ret))

        # Stats
        mean_reward = float(R_rew.mean())
        reward_history.append(mean_reward)

        # Episode reward tracking
        ep_rewards = env.completed_rewards[-100:] if env.completed_rewards else [0]
        mean_ep = np.mean(ep_rewards)

        if mean_ep > best_ep_reward and len(env.completed_rewards) > 10:
            best_ep_reward = mean_ep
            policy.save(os.path.join(OUTPUT_DIR, "best_policy.npz"))

        # Logging
        if iteration % LOG_INTERVAL == 0:
            elapsed = time.time() - start_time
            sps = total_steps / elapsed
            eta = (TOTAL_TIMESTEPS - total_steps) / max(sps, 1)

            gravity_str = f"{env.gravities.mean():.2e}"
            log(f"  iter {iteration:5d} | {total_steps:>10,}/{TOTAL_TIMESTEPS:,} "
                f"| step_r {mean_reward:>7.3f} | ep_r {mean_ep:>7.1f} "
                f"| loss {loss:>7.3f} | g={gravity_str} "
                f"| {sps:,.0f} sps | ETA {timedelta(seconds=int(eta))}")

        # Checkpoint
        if time.time() - last_ckpt > CHECKPOINT_INTERVAL:
            policy.save(os.path.join(OUTPUT_DIR, "checkpoint.npz"))
            with open(os.path.join(OUTPUT_DIR, "reward_history.json"), "w") as f:
                json.dump(reward_history, f)
            last_ckpt = time.time()
            log(f"  ** Checkpoint (best_ep={best_ep_reward:.1f})")

    # Final save
    elapsed = time.time() - start_time
    policy.save(os.path.join(OUTPUT_DIR, "final_policy.npz"))
    with open(os.path.join(OUTPUT_DIR, "reward_history.json"), "w") as f:
        json.dump(reward_history, f)

    log("")
    log("=" * 70)
    log("  TRAINING COMPLETE")
    log("=" * 70)
    log(f"  Time: {timedelta(seconds=int(elapsed))}")
    log(f"  Steps: {total_steps:,}")
    log(f"  Best episode reward: {best_ep_reward:.2f}")
    log(f"  Policies: {OUTPUT_DIR}/best_policy.npz, final_policy.npz")
    log(f"  To evaluate: python train_locomotion.py --eval")
    log("=" * 70)


def evaluate():
    """Evaluate saved policy across asteroids."""
    path = os.path.join(OUTPUT_DIR, "best_policy.npz")
    if not os.path.exists(path):
        path = os.path.join(OUTPUT_DIR, "final_policy.npz")
    if not os.path.exists(path):
        print("No policy found. Train first.")
        return

    policy = Policy()
    policy.load(path)
    print(f"Loaded policy from {path}")

    model = mujoco.MjModel.from_xml_path(MODEL_PATH)
    asteroids = [
        ("Bennu", 5.8e-6), ("Itokawa", 8.6e-6), ("Ryugu", 1.1e-4),
        ("Didymos", 3.6e-4), ("Eros", 5.9e-3), ("Psyche", 0.06),
    ]

    print(f"\n{'Asteroid':>10} | {'Forward mm':>11} | {'Max Tilt':>9} | {'Ep Reward':>10}")
    print("-" * 50)

    for name, g in asteroids:
        model.opt.gravity[:] = [0, 0, -g]
        data = mujoco.MjData(model)
        mujoco.mj_resetData(model, data)

        total_r = 0
        max_tilt = 0
        x0 = float(data.qpos[0])

        for step in range(500):
            obs = np.zeros(OBS_DIM)
            obs[:8] = data.qpos[7:15]
            obs[8:16] = data.qvel[6:14] * 0.1
            obs[16:20] = data.qpos[3:7]
            obs[20:23] = data.qvel[3:6] * 0.1
            obs[23:26] = data.qvel[0:3] * 0.1
            obs[26:34] = [1.0 if data.xpos[fid, 2] < 0.012 else 0.0
                          for fid in FOOT_IDS]

            action = policy.forward(obs.reshape(1, -1)).squeeze()
            data.ctrl[:8] = action
            data.xfrc_applied[:] = 0
            for fid in FOOT_IDS:
                if data.xpos[fid, 2] < 0.012:
                    data.xfrc_applied[fid, 2] = -0.15
            for _ in range(PHYSICS_STEPS):
                mujoco.mj_step(model, data)

            quat = data.qpos[3:7]
            up_z = 1 - 2*(quat[1]**2 + quat[2]**2)
            tilt = math.degrees(math.acos(max(-1, min(1, up_z))))
            max_tilt = max(max_tilt, tilt)

        fwd = (float(data.qpos[0]) - x0) * 1000
        print(f"{name:>10} | {fwd:>9.1f} mm | {tilt:>7.1f} deg | {'--':>10}")


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
