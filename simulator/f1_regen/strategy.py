"""Energy-deployment strategies and their automatic tuning.

Each deployment mode has a single tuning parameter. ``tune_deploy`` finds, by
bisection, the value that makes the lap finish at a target state of charge:
  * race / charge-sustaining : SOC at the line equals SOC at the start of the lap
  * qualifying               : start full, finish at the bottom of the window
"""
from __future__ import annotations

from dataclasses import replace

from .config import PowerUnit, Strategy, Vehicle
from .simulation import _simulate, braking_envelope, simulate_lap
from .track import Track

# mode -> (lower bound, upper bound, sign); sign < 0 means a larger parameter deploys more
_BOUNDS = {
    "greedy": (0.0, 12.0, -1),
    "uniform": (0.0, 1.0, -1),
    "low_speed": (0.0, 400.0, -1),
    "high_speed": (0.0, 400.0, +1),
}


def tune_deploy(track: Track, veh: Vehicle, pu: PowerUnit, strat: Strategy,
                target_soc_end: float | None = None, tol: float = 1e-4,
                max_iter: int = 40) -> Strategy:
    """Return a copy of ``strat`` whose ``deploy_param`` ends the lap at the target SOC."""
    if not pu.ers_enabled or strat.deploy_mode not in _BOUNDS:
        return strat
    target = strat.soc_start if target_soc_end is None else target_soc_end
    lo, hi, sign = _BOUNDS[strat.deploy_mode]
    env = braking_envelope(track, veh)
    e0 = strat.soc_start * pu.es_window_mj * 1e6
    p_most, p_least = (hi, lo) if sign < 0 else (lo, hi)
    width = abs(hi - lo)

    def solve(v0: float) -> float:
        def run(p: float) -> tuple[float, float]:
            lap = _simulate(track, veh, pu, replace(strat, deploy_param=p), v0, e0, env)
            return float(lap.soc[-1]), float(lap.energy["deploy_dc"])

        soc_most, dep_most = run(p_most)
        if soc_most >= target - tol:
            # The target SOC cannot be reached (per-lap deploy limit or an energy surplus).
            # Spend the maximum usable energy where it helps most: the least-deploying
            # parameter that still uses all of it.
            goal = dep_most * (1.0 - 1e-4)
            if run(p_least)[1] >= goal:
                return p_least
            a, b = p_least, p_most      # dep(a) < goal <= dep(b)
            for _ in range(max_iter):
                mid = 0.5 * (a + b)
                if run(mid)[1] >= goal:
                    b = mid
                else:
                    a = mid
                if abs(b - a) < 1e-5 * width:
                    break
            return b

        if run(p_least)[0] <= target + tol:
            return p_least
        a, b = p_least, p_most          # soc_end(a) > target > soc_end(b)
        for _ in range(max_iter):
            mid = 0.5 * (a + b)
            if run(mid)[0] > target:
                a = mid
            else:
                b = mid
            if abs(b - a) < 1e-5 * width:
                break
        return a

    # the flying-start speed depends on the strategy itself, so iterate to a fixed point
    tuned = strat
    v0 = float(simulate_lap(track, veh, pu, strat).v[0])
    for _ in range(4):
        tuned = replace(strat, deploy_param=solve(v0))
        v0_new = float(simulate_lap(track, veh, pu, tuned).v[0])
        if abs(v0_new - v0) < 0.005:
            break
        v0 = v0_new
    return tuned


def race_strategy(track: Track, veh: Vehicle, pu: PowerUnit, mode: str = "low_speed",
                  soc: float = 0.5, superclip: bool = False, superclip_speed_kph: float = 300.0,
                  name: str | None = None, **extra) -> Strategy:
    """Charge-sustaining race lap: end the lap with the same SOC it started with.

    ``extra`` passes any other Strategy field (e.g. regen=False).
    """
    base = Strategy(
        name=name or "Race (charge-sustaining)",
        deploy_mode=mode,
        deploy_param=_BOUNDS.get(mode, (0, 0, 0))[1],
        soc_start=soc,
        superclip=superclip,
        superclip_speed_kph=superclip_speed_kph,
        **extra,
    )
    return tune_deploy(track, veh, pu, base)


def qualifying_strategy(track: Track, veh: Vehicle, pu: PowerUnit, mode: str = "low_speed",
                        superclip: bool = False, superclip_speed_kph: float = 300.0,
                        name: str | None = None, **extra) -> Strategy:
    """Qualifying lap: start with a full store and finish with it empty."""
    base = Strategy(
        name=name or "Qualifying (full store, empty at the line)",
        deploy_mode=mode,
        deploy_param=_BOUNDS.get(mode, (0, 0, 0))[1],
        soc_start=1.0,
        superclip=superclip,
        superclip_speed_kph=superclip_speed_kph,
        **extra,
    )
    return tune_deploy(track, veh, pu, base, target_soc_end=base.soc_min)
