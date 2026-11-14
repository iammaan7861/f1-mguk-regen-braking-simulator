"""Quasi-steady-state (QSS) lap simulation with MGU-K regenerative braking.

Method
------
1. Cornering limit from the adhesion condition  m v^2 kappa <= mu_y (m g + k_L v^2).
2. Backward pass: maximum-braking envelope (friction ellipse; drag and rolling
   resistance help the brakes).
3. Forward pass: full-throttle acceleration with ICE + MGU-K deployment, clipped by
   the envelope. Where the envelope binds, the car is either at part throttle or
   braking. The braking demand is blended between the MGU-K (rear axle only,
   power- and energy-limited) and the friction brakes, as a brake-by-wire system does.

Every joule is tracked, so the lap energy balance closes to round-off.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .config import G, PowerUnit, Strategy, Vehicle
from .ers import Battery, deploy_power_limit_kw
from .track import Track

MODE_BRAKE, MODE_PART, MODE_FULL = 0, 1, 2
MODE_NAMES = {MODE_BRAKE: "Braking", MODE_PART: "Part throttle", MODE_FULL: "Full throttle"}
HOLD_TOL_KPH = 0.05  # speed thresholds are held, not toggled, within this band


# ----------------------------------------------------------------------------------------
# Speed limits
# ----------------------------------------------------------------------------------------
def corner_speed_limits(track: Track, veh: Vehicle) -> np.ndarray:
    """Maximum steady cornering speed for every step (m/s)."""
    v_cap = veh.v_max_kph / 3.6
    m = veh.mass_kg
    k_l = 0.5 * veh.air_density * veh.cla_m2
    kap = np.abs(track.kappa)
    denom = m * kap - veh.mu_lat * k_l
    with np.errstate(divide="ignore", invalid="ignore"):
        v = np.sqrt(veh.mu_lat * m * G / denom)
    v = np.where(denom > 0, v, v_cap)
    return np.minimum(v, v_cap)


def braking_envelope(track: Track, veh: Vehicle) -> np.ndarray:
    """Highest speed at each node from which the car can still make every corner ahead.

    Returned array has N+1 nodes; node N is the start of the following lap.
    """
    cache = track.__dict__.setdefault("_env_cache", {})
    if veh in cache:
        return cache[veh]

    n = track.n_steps
    vc = corner_speed_limits(track, veh)
    node_lim = np.minimum(vc, np.roll(vc, 1))  # node i touches steps i-1 and i

    m, me = veh.mass_kg, veh.effective_mass
    k_d = 0.5 * veh.air_density * veh.cda_m2
    k_l = 0.5 * veh.air_density * veh.cla_m2
    mu_x, mu_y, crr = veh.mu_long, veh.mu_lat, veh.c_rr
    a_cap = veh.max_decel_g * G
    ds = track.ds
    kap = np.abs(track.kappa)

    v = np.empty(2 * n + 1)
    v[2 * n] = node_lim[0]
    for j in range(2 * n - 1, -1, -1):
        i = j % n
        vn = v[j + 1]
        nz = m * G + k_l * vn * vn
        fy_max = mu_y * nz
        r = m * vn * vn * kap[i] / fy_max
        ell = math.sqrt(1.0 - r * r) if r < 1.0 else 0.0
        decel = min((mu_x * nz * ell + k_d * vn * vn + crr * nz) / me, a_cap)
        v[j] = min(node_lim[i], math.sqrt(vn * vn + 2.0 * decel * ds[i]))
    env = v[: n + 1].copy()
    cache[veh] = env
    return env


# ----------------------------------------------------------------------------------------
# Results container
# ----------------------------------------------------------------------------------------
@dataclass
class LapResult:
    track: Track
    vehicle: Vehicle
    pu: PowerUnit
    strategy: Strategy
    lap_index: int
    v: np.ndarray            # node speeds, m/s (N+1)
    t: np.ndarray            # node times, s (N+1)
    soc: np.ndarray          # node state of charge, fraction of window (N+1)
    dt: np.ndarray           # step durations (N)
    mode: np.ndarray         # step mode (N)
    p_ice: np.ndarray        # ICE crank power, W
    p_deploy: np.ndarray     # DC power from ES to MGU-K, W
    p_regen: np.ndarray      # DC power recovered from braking, W
    p_clip: np.ndarray       # DC power harvested at full throttle (super-clipping), W
    p_pt: np.ndarray         # DC power harvested at part throttle, W
    p_brake: np.ndarray      # total braking power at the wheels, W
    p_friction: np.ndarray   # friction-brake power (heat), W
    p_tractive: np.ndarray   # tractive power at the wheels, W
    i_batt: np.ndarray       # battery current, A (+ discharge, - charge)
    v_batt: np.ndarray       # battery terminal voltage, V
    p_batt_loss: np.ndarray  # battery Joule loss, W
    p_fuel: np.ndarray       # fuel power, W
    energy: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)

    @property
    def lap_time(self) -> float:
        return float(self.t[-1])

    @property
    def s(self) -> np.ndarray:
        return self.track.s

    @property
    def s_mid(self) -> np.ndarray:
        return self.track.s_mid

    @property
    def p_harvest(self) -> np.ndarray:
        return self.p_regen + self.p_clip + self.p_pt


# ----------------------------------------------------------------------------------------
# Core forward pass
# ----------------------------------------------------------------------------------------
def _shaft_power_to(vt, v, ds, kd, kl, m, me, crr, eta_gb):
    """Crank power that brings the car from v to vt over one step (negative = must slow)."""
    v_avg = 0.5 * (v + vt)
    f = me * (vt * vt - v * v) / (2.0 * ds) + kd * v_avg * v_avg + crr * (m * G + kl * v_avg * v_avg)
    return f * v_avg / eta_gb


def _simulate(track: Track, veh: Vehicle, pu: PowerUnit, strat: Strategy,
              v0: float, e0: float, env: np.ndarray, lap_index: int = 0) -> LapResult:
    n = track.n_steps
    ds_l = track.ds.tolist()
    kap_abs = np.abs(track.kappa)
    kap_l = kap_abs.tolist()
    env_l = env.tolist()

    m, me = veh.mass_kg, veh.effective_mass
    k_d = 0.5 * veh.air_density * veh.cda_m2
    k_l = 0.5 * veh.air_density * veh.cla_m2
    # aero coefficients when not braking: low-drag straight mode on straights (2026 active aero)
    if veh.active_aero:
        on_straight = kap_abs < 1e-3
        kd_l = np.where(on_straight, k_d * veh.straight_cda_factor, k_d).tolist()
        kl_l = np.where(on_straight, k_l * veh.straight_cla_factor, k_l).tolist()
    else:
        kd_l = [k_d] * n
        kl_l = [k_l] * n
    mu_x, mu_y, crr = veh.mu_long, veh.mu_lat, veh.c_rr
    rear, bshare, eta_gb = veh.rear_load_fraction, veh.rear_brake_share, veh.gearbox_efficiency

    p_ice_max = pu.ice_power_kw * 1e3
    ers = pu.ers_enabled
    eta_e = pu.electrical_chain_efficiency
    p_k = pu.mguk_power_kw * 1e3
    p_clip_max = min(pu.superclip_power_kw * 1e3, p_k)
    inf = float("inf")
    harv_cap = pu.harvest_limit_mj * 1e6 if (ers and pu.harvest_limit_mj is not None) else inf
    dep_cap = pu.deploy_limit_mj * 1e6 if (ers and pu.deploy_limit_mj is not None) else inf
    mode_d = strat.deploy_mode
    param = strat.deploy_param
    if mode_d == "greedy":
        dep_cap = min(dep_cap, max(0.0, param) * 1e6)
    frac = min(1.0, max(0.0, param)) if mode_d == "uniform" else 1.0
    taper = pu.deploy_taper
    override = strat.override
    use_regen = ers and strat.regen
    use_clip = ers and strat.superclip
    clip_v = strat.superclip_speed_kph
    use_pt = ers and strat.part_throttle_harvest

    batt = Battery(pu)
    cap = batt.capacity_j
    e_min, e_max = strat.soc_min * cap, strat.soc_max * cap
    e = min(max(e0, e_min), e_max) if cap > 0 else 0.0
    e_start = e

    v_out = [0.0] * (n + 1)
    t_out = [0.0] * (n + 1)
    soc_out = [0.0] * (n + 1)
    z = [0.0] * n
    dt_o, ice_o, dep_o, reg_o, clip_o, pt_o = z[:], z[:], z[:], z[:], z[:], z[:]
    brk_o, fric_o, trac_o, ib_o, vb_o, loss_o, fuel_o = z[:], z[:], z[:], z[:], z[:], z[:], z[:]
    mode_o = [0] * n

    acc = dict(ice=0.0, tractive=0.0, brake=0.0, regen_wheel=0.0, regen_dc=0.0, clip_dc=0.0,
               pt_dc=0.0, deploy_dc=0.0, friction=0.0, drag=0.0, rolling=0.0, gearbox=0.0,
               emachine=0.0, battery=0.0)

    v = max(v0, 1.0)
    t = 0.0
    e_harv = e_dep = 0.0
    v_out[0], soc_out[0] = v, (e / cap if cap > 0 else 0.0)

    for i in range(n):
        ds = ds_l[i]
        kap = kap_l[i]
        kd_i, kl_i = kd_l[i], kl_l[i]
        v_next_cap = env_l[i + 1]
        dt_est = ds / v
        v_kph = v * 3.6
        voc = batt.voc(e) if cap > 0 else 0.0

        # ---------------- ERS commands for this step ----------------
        p_dep_cmd = 0.0
        p_clip_cmd = 0.0
        if ers and cap > 0:
            if mode_d == "none":
                want = False
            elif mode_d == "low_speed":
                want = v_kph < param + HOLD_TOL_KPH
            elif mode_d == "high_speed":
                want = v_kph > param
            else:
                want = True
            if want:
                p = deploy_power_limit_kw(v_kph, taper, pu.mguk_power_kw, override) * 1e3 * frac
                if mode_d == "low_speed":
                    # never push past the threshold; hold it if the ICE alone cannot
                    p = min(p, (_shaft_power_to(param / 3.6, v, ds, kd_i, kl_i, m, me, crr, eta_gb)
                                - p_ice_max) / eta_e)
                p = min(p, (dep_cap - e_dep) / dt_est,
                        batt.max_discharge_terminal_energy(e - e_min, dt_est, voc) / dt_est)
                p_dep_cmd = max(0.0, p)
            if use_clip and v_kph >= clip_v - HOLD_TOL_KPH:
                # super-clipping: the MGU-K absorbs the ICE power not needed to hold clip_v
                need = _shaft_power_to(clip_v / 3.6, v, ds, kd_i, kl_i, m, me, crr, eta_gb)
                p = min(p_clip_max, (p_ice_max - max(0.0, need)) * eta_e, (harv_cap - e_harv) / dt_est,
                        batt.max_charge_terminal_energy(e_max - e, dt_est, voc) / dt_est)
                if p > 0.0:
                    p_clip_cmd = p
                    p_dep_cmd = 0.0

        # ---------------- full-throttle candidate (semi-implicit) ----------------
        p_wheel = (p_ice_max + p_dep_cmd * eta_e - p_clip_cmd / eta_e) * eta_gb
        v_eval = v
        f_trac = f_drag = f_roll = 0.0
        v_acc = v
        for _ in range(2):
            nz = m * G + kl_i * v_eval * v_eval
            fy_max = mu_y * nz
            r = m * v_eval * v_eval * kap / fy_max
            ell = math.sqrt(1.0 - r * r) if r < 1.0 else 0.0
            f_trac = min(p_wheel / v_eval, mu_x * rear * nz * ell)
            f_drag = kd_i * v_eval * v_eval
            f_roll = crr * nz
            v2 = v * v + 2.0 * (f_trac - f_drag - f_roll) / me * ds
            v_acc = math.sqrt(v2) if v2 > 1.0 else 1.0
            v_eval = 0.5 * (v + v_acc)

        w_ice = w_dep_dc = w_regen_dc = w_clip_dc = w_pt_dc = 0.0
        w_trac = w_brake = w_regen_wheel = 0.0

        if v_acc <= v_next_cap:
            # ================= full throttle =================
            mode = MODE_FULL
            v_new = v_acc
            dt = 2.0 * ds / (v + v_new)
            w_trac = f_trac * ds
            w_drag, w_roll = f_drag * ds, f_roll * ds
            w_shaft = w_trac / eta_gb
            w_ice_max = p_ice_max * dt
            if p_clip_cmd > 0.0:
                w_clip_dc = p_clip_cmd * dt
                allowed = min(harv_cap - e_harv, batt.max_charge_terminal_energy(e_max - e, dt, voc))
                w_clip_dc = max(0.0, min(w_clip_dc, allowed))
                w_ice = w_shaft + w_clip_dc / eta_e
            else:
                w_dep_mech = min(p_dep_cmd * eta_e * dt, max(0.0, w_shaft - w_ice_max))
                allowed = min(dep_cap - e_dep, batt.max_discharge_terminal_energy(e - e_min, dt, voc)) \
                    if (ers and cap > 0) else 0.0
                w_dep_dc = max(0.0, min(w_dep_mech / eta_e if eta_e > 0 else 0.0, allowed))
                w_ice = w_shaft - w_dep_dc * eta_e
        else:
            v_new = v_next_cap
            v_avg = 0.5 * (v + v_new)
            dt = ds / v_avg
            inertia = me * (v_new * v_new - v * v) / (2.0 * ds)
            nz = m * G + kl_i * v_avg * v_avg
            f_drag = kd_i * v_avg * v_avg
            f_roll = crr * nz
            f_req = inertia + f_drag + f_roll
            if f_req < 0.0 and (kd_i != k_d or kl_i != k_l):
                # braking closes the active-aero flaps: corner-mode drag and downforce
                nz = m * G + k_l * v_avg * v_avg
                f_drag = k_d * v_avg * v_avg
                f_roll = crr * nz
                f_req = inertia + f_drag + f_roll
            w_drag, w_roll = f_drag * ds, f_roll * ds
            if f_req >= 0.0:
                # ================= part throttle =================
                mode = MODE_PART
                w_trac = f_req * ds
                w_shaft = w_trac / eta_gb
                w_ice_max = p_ice_max * dt
                w_dep_mech = min(max(0.0, w_shaft - w_ice_max), p_dep_cmd * eta_e * dt)
                if w_dep_mech > 0.0:
                    allowed = min(dep_cap - e_dep, batt.max_discharge_terminal_energy(e - e_min, dt, voc))
                    w_dep_dc = max(0.0, min(w_dep_mech / eta_e, allowed))
                w_ice = w_shaft - w_dep_dc * eta_e
                if use_pt and w_dep_dc == 0.0 and cap > 0:
                    surplus_mech = max(0.0, w_ice_max - w_ice)
                    allowed = min(harv_cap - e_harv, p_k * dt,
                                  batt.max_charge_terminal_energy(e_max - e, dt, voc))
                    w_pt_dc = max(0.0, min(surplus_mech * eta_e, allowed))
                    w_ice += w_pt_dc / eta_e
            else:
                # ================= braking (composite: MGU-K + friction) =================
                mode = MODE_BRAKE
                w_brake = -f_req * ds
                if use_regen and cap > 0:
                    rear_dc = bshare * w_brake * eta_gb * eta_e
                    allowed = min(harv_cap - e_harv, p_k * dt,
                                  batt.max_charge_terminal_energy(e_max - e, dt, voc))
                    w_regen_dc = max(0.0, min(rear_dc, allowed))
                    w_regen_wheel = w_regen_dc / (eta_gb * eta_e)

        # ---------------- energy store update ----------------
        w_in = w_regen_dc + w_clip_dc + w_pt_dc
        i_b = 0.0
        v_t = voc
        loss = 0.0
        if cap > 0:
            if w_in > 0.0:
                i_c = batt.charge_current(w_in / dt, voc)
                loss = i_c * i_c * batt.r * dt
                e += voc * i_c * dt
                i_b, v_t = -i_c, voc + i_c * batt.r
            elif w_dep_dc > 0.0:
                i_d = batt.discharge_current(w_dep_dc / dt, voc)
                loss = i_d * i_d * batt.r * dt
                e -= voc * i_d * dt
                i_b, v_t = i_d, voc - i_d * batt.r
            e = min(max(e, e_min - 1e-6), e_max + 1e-6)
        e_harv += w_in
        e_dep += w_dep_dc

        # ---------------- book-keeping ----------------
        w_ice_net = w_ice - w_clip_dc / eta_e - w_pt_dc / eta_e if ers else w_ice
        acc["ice"] += w_ice
        acc["tractive"] += w_trac
        acc["brake"] += w_brake
        acc["regen_wheel"] += w_regen_wheel
        acc["regen_dc"] += w_regen_dc
        acc["clip_dc"] += w_clip_dc
        acc["pt_dc"] += w_pt_dc
        acc["deploy_dc"] += w_dep_dc
        acc["friction"] += w_brake - w_regen_wheel
        acc["drag"] += w_drag
        acc["rolling"] += w_roll
        shaft_out = w_ice_net + w_dep_dc * eta_e
        acc["gearbox"] += shaft_out * (1.0 - eta_gb) + w_regen_wheel * (1.0 - eta_gb)
        harvest_mech = w_regen_wheel * eta_gb + (w_clip_dc + w_pt_dc) / eta_e
        acc["emachine"] += w_dep_dc * (1.0 - eta_e) + (harvest_mech - w_in)
        acc["battery"] += loss

        t += dt
        v = v_new
        v_out[i + 1] = v
        t_out[i + 1] = t
        soc_out[i + 1] = e / cap if cap > 0 else 0.0
        dt_o[i] = dt
        mode_o[i] = mode
        ice_o[i] = w_ice / dt
        dep_o[i] = w_dep_dc / dt
        reg_o[i] = w_regen_dc / dt
        clip_o[i] = w_clip_dc / dt
        pt_o[i] = w_pt_dc / dt
        brk_o[i] = w_brake / dt
        fric_o[i] = (w_brake - w_regen_wheel) / dt
        trac_o[i] = w_trac / dt
        ib_o[i] = i_b
        vb_o[i] = v_t
        loss_o[i] = loss / dt
        fuel_o[i] = w_ice / dt / pu.ice_efficiency

    arr = np.asarray
    res = LapResult(
        track=track, vehicle=veh, pu=pu, strategy=strat, lap_index=lap_index,
        v=arr(v_out), t=arr(t_out), soc=arr(soc_out), dt=arr(dt_o), mode=arr(mode_o),
        p_ice=arr(ice_o), p_deploy=arr(dep_o), p_regen=arr(reg_o), p_clip=arr(clip_o),
        p_pt=arr(pt_o), p_brake=arr(brk_o), p_friction=arr(fric_o), p_tractive=arr(trac_o),
        i_batt=arr(ib_o), v_batt=arr(vb_o), p_batt_loss=arr(loss_o), p_fuel=arr(fuel_o),
    )
    res.energy = _energy_book(res, acc, e_start, e, v0)
    res.summary = _summarise(res)
    return res


def _energy_book(res: LapResult, acc: dict, e_start: float, e_end: float, v0: float) -> dict:
    veh, pu = res.vehicle, res.pu
    fuel = acc["ice"] / pu.ice_efficiency
    ke_change = 0.5 * veh.effective_mass * (res.v[-1] ** 2 - res.v[0] ** 2)
    sinks = (fuel - acc["ice"]) + acc["gearbox"] + acc["emachine"] + acc["battery"] \
        + acc["friction"] + acc["drag"] + acc["rolling"] + ke_change + (e_end - e_start)
    error = fuel - sinks
    book = dict(acc)
    book.update(
        fuel=fuel,
        ice_heat=fuel - acc["ice"],
        harvest_dc=acc["regen_dc"] + acc["clip_dc"] + acc["pt_dc"],
        deploy_mech=acc["deploy_dc"] * pu.electrical_chain_efficiency,
        ke_change=ke_change,
        es_start=e_start,
        es_end=e_end,
        balance_error=error,
    )
    return book


def _summarise(res: LapResult) -> dict:
    en, veh, track = res.energy, res.vehicle, res.track
    lap_t = res.lap_time
    dt = res.dt
    mj = 1e-6
    t_full = float(dt[res.mode == MODE_FULL].sum())
    t_part = float(dt[res.mode == MODE_PART].sum())
    t_brake = float(dt[res.mode == MODE_BRAKE].sum())
    tonne_km = veh.mass_kg / 1000.0 * track.length / 1000.0
    wh = 1.0 / 3600.0
    regen_dc = en["regen_dc"]
    brake = en["brake"]
    deploy_dc = en["deploy_dc"]
    accel = np.diff(res.v) / dt
    return {
        "peak_decel_g": float(-accel.min() / G),
        "peak_accel_g": float(accel.max() / G),
        "lap_time_s": lap_t,
        "avg_speed_kph": track.length / lap_t * 3.6,
        "top_speed_kph": float(res.v.max() * 3.6),
        "min_speed_kph": float(res.v.min() * 3.6),
        "time_full_pct": 100.0 * t_full / lap_t,
        "time_part_pct": 100.0 * t_part / lap_t,
        "time_brake_pct": 100.0 * t_brake / lap_t,
        "braking_time_s": t_brake,
        "brake_energy_MJ": brake * mj,
        "regen_MJ": regen_dc * mj,
        "clip_MJ": en["clip_dc"] * mj,
        "pt_MJ": en["pt_dc"] * mj,
        "harvest_MJ": en["harvest_dc"] * mj,
        "deploy_MJ": deploy_dc * mj,
        "friction_MJ": en["friction"] * mj,
        "recovery_pct": 100.0 * regen_dc / brake if brake > 0 else 0.0,
        "soc_start_pct": 100.0 * res.soc[0],
        "soc_end_pct": 100.0 * res.soc[-1],
        "fuel_MJ": en["fuel"] * mj,
        "fuel_kg": en["fuel"] * mj / res.pu.fuel_lhv_mj_kg,
        "ice_MJ": en["ice"] * mj,
        "drag_MJ": en["drag"] * mj,
        "rolling_MJ": en["rolling"] * mj,
        "gearbox_loss_MJ": en["gearbox"] * mj,
        "emachine_loss_MJ": en["emachine"] * mj,
        "battery_loss_MJ": en["battery"] * mj,
        "peak_brake_power_kW": float(res.p_brake.max() / 1e3),
        "peak_regen_kW": float(res.p_regen.max() / 1e3),
        "peak_deploy_kW": float(res.p_deploy.max() / 1e3),
        "peak_batt_current_A": float(np.abs(res.i_batt).max()),
        "sec_wh_per_tkm": en["tractive"] * wh / tonne_km,
        "net_sec_wh_per_tkm": (en["tractive"] - en["regen_wheel"]) * wh / tonne_km,
        "balance_error_J": en["balance_error"],
        "balance_error_pct": 100.0 * abs(en["balance_error"]) / en["fuel"] if en["fuel"] else 0.0,
    }


# ----------------------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------------------
def simulate_lap(track: Track, veh: Vehicle, pu: PowerUnit, strat: Strategy,
                 v0: float | None = None, soc0: float | None = None,
                 lap_index: int = 0) -> LapResult:
    """Simulate one flying lap.

    If ``v0`` is not given, a preliminary lap is run so that the lap starts at the
    speed the car naturally carries across the line (a true flying lap).
    """
    env = braking_envelope(track, veh)
    cap = pu.es_window_mj * 1e6
    soc = strat.soc_start if soc0 is None else soc0
    e0 = soc * cap
    if v0 is None:
        v0 = _simulate(track, veh, pu, strat, float(env[0]), e0, env).v[-1]
    return _simulate(track, veh, pu, strat, float(v0), e0, env, lap_index)


def simulate_stint(track: Track, veh: Vehicle, pu: PowerUnit, strat: Strategy,
                   n_laps: int, v0: float | None = None) -> list[LapResult]:
    """Simulate consecutive laps; speed and state of charge carry over between laps."""
    laps: list[LapResult] = []
    soc = strat.soc_start
    for k in range(n_laps):
        lap = simulate_lap(track, veh, pu, strat, v0=v0, soc0=soc, lap_index=k)
        laps.append(lap)
        v0 = float(lap.v[-1])
        soc = float(lap.soc[-1])
    return laps
