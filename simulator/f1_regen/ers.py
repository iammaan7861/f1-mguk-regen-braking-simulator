"""Energy Recovery System models: MGU-K deployment limits and the energy store.

The energy store (ES) is an internal-resistance (Rint) equivalent circuit:

    V_t = V_oc(SOC) - I*R      (discharge, I > 0)
    V_t = V_oc(SOC) + I*R      (charge,    I > 0 into the battery)

Stored (chemical) energy changes by V_oc*I*dt; the Joule loss is I^2*R*dt.
"""
from __future__ import annotations

import math

from .config import PowerUnit


def deploy_power_limit_kw(speed_kph: float, taper: str | None, p_max_kw: float,
                          override: bool = False) -> float:
    """Maximum MGU-K propulsion power (DC) allowed at a given car speed."""
    if taper != "fia2026":
        return p_max_kw
    v = speed_kph
    if override:
        p = 7100.0 - 20.0 * v if v < 355.0 else 0.0
    elif v < 340.0:
        p = 1800.0 - 5.0 * v
    elif v < 345.0:
        p = 6900.0 - 20.0 * v
    else:
        p = 0.0
    return max(0.0, min(p_max_kw, p))


class Battery:
    """Rint model of the ERS energy store, working on the usable SOC window."""

    def __init__(self, pu: PowerUnit):
        self.capacity_j = pu.es_window_mj * 1e6
        self.v_min = pu.battery_voc_min_v
        self.v_max = pu.battery_voc_max_v
        self.r = pu.battery_resistance_ohm

    def voc(self, energy_j: float) -> float:
        soc = energy_j / self.capacity_j if self.capacity_j > 0 else 0.0
        return self.v_min + (self.v_max - self.v_min) * soc

    # --- current from terminal power -------------------------------------------------
    def discharge_current(self, p_out_w: float, voc: float) -> float:
        disc = voc * voc - 4.0 * self.r * p_out_w
        if disc < 0.0:
            disc = 0.0
        return (voc - math.sqrt(disc)) / (2.0 * self.r)

    def charge_current(self, p_in_w: float, voc: float) -> float:
        return (-voc + math.sqrt(voc * voc + 4.0 * self.r * p_in_w)) / (2.0 * self.r)

    # --- energy that keeps the store inside its window over a step dt -----------------
    def max_discharge_terminal_energy(self, chem_available_j: float, dt: float, voc: float) -> float:
        """Terminal energy deliverable if at most ``chem_available_j`` may leave the cells."""
        if chem_available_j <= 0.0 or dt <= 0.0:
            return 0.0
        # terminal power peaks at I = Voc / 2R; beyond that more current delivers less
        i = min(chem_available_j / (voc * dt), voc / (2.0 * self.r))
        return max(0.0, (voc * i - i * i * self.r) * dt)

    def max_charge_terminal_energy(self, headroom_j: float, dt: float, voc: float) -> float:
        """Terminal energy acceptable if at most ``headroom_j`` may be added to the cells."""
        if headroom_j <= 0.0 or dt <= 0.0:
            return 0.0
        i = headroom_j / (voc * dt)
        return headroom_j + i * i * self.r * dt
