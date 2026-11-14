"""Parameter sets for the vehicle, the power unit / ERS and the energy strategy.

All values are representative public-domain figures for a modern Formula 1 car.
Regulatory limits follow the FIA Formula 1 Technical Regulations:
  * 2009 KERS      : 60 kW, 400 kJ released per lap
  * 2014-2025 ERS  : MGU-K 120 kW, 2 MJ harvested / 4 MJ deployed per lap, 4 MJ ES window
  * 2026 ERS       : ERS-K 350 kW DC, 8.5 MJ harvested per lap, 4 MJ ES window,
                     speed-dependent deployment taper (Article C5.2.8)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Optional

G = 9.81  # m/s^2


@dataclass(frozen=True)
class Vehicle:
    """Chassis, aerodynamics and tyre parameters (point-mass model)."""

    name: str = "Representative F1 car"
    mass_kg: float = 800.0              # car + driver + average fuel load
    rot_inertia_factor: float = 1.04    # effective-mass factor (rotating parts)
    cda_m2: float = 1.10                # drag area  C_D*A
    cla_m2: float = 4.00                # downforce area  C_L*A
    air_density: float = 1.20           # kg/m^3
    mu_lat: float = 1.90                # lateral tyre-road adhesion coefficient
    mu_long: float = 1.80               # longitudinal adhesion coefficient
    max_decel_g: float = 5.0            # peak braking deceleration (tyre load sensitivity, driver)
    c_rr: float = 0.012                 # rolling-resistance coefficient
    rear_load_fraction: float = 0.55    # share of vertical load on driven (rear) axle
    rear_brake_share: float = 0.42      # brake balance: share of braking on rear axle
    gearbox_efficiency: float = 0.96    # wheel <-> crankshaft transmission
    v_max_kph: float = 380.0            # numerical speed cap on straights
    active_aero: bool = False           # 2026 straight-line (low-drag) mode on straights
    straight_cda_factor: float = 0.75
    straight_cla_factor: float = 0.60

    @property
    def effective_mass(self) -> float:
        return self.mass_kg * self.rot_inertia_factor

    def with_trim(self, trim: str) -> "Vehicle":
        """Return the same car in a different aerodynamic trim."""
        trims = {
            "low": dict(cda_m2=1.10, cla_m2=4.00),
            "high": dict(cda_m2=1.45, cla_m2=5.80),
        }
        return replace(self, **trims[trim])


@dataclass(frozen=True)
class PowerUnit:
    """Internal-combustion engine plus Energy Recovery System (MGU-K + energy store)."""

    name: str
    ice_power_kw: float
    ice_efficiency: float               # brake thermal efficiency of the ICE
    fuel_lhv_mj_kg: float = 43.0
    ers_enabled: bool = True
    mguk_power_kw: float = 350.0        # max electrical DC power, motoring and generating
    deploy_taper: Optional[str] = None  # "fia2026" -> speed-dependent deployment limit
    harvest_limit_mj: Optional[float] = 8.5   # per lap, DC energy out of the MGU-K inverter
    deploy_limit_mj: Optional[float] = None   # per lap, DC energy from ES to MGU-K
    es_window_mj: float = 4.0           # usable state-of-charge window of the energy store
    mguk_efficiency: float = 0.95       # electrical machine efficiency (each direction)
    inverter_efficiency: float = 0.98   # power electronics (CU-K) efficiency
    battery_voc_min_v: float = 720.0    # open-circuit voltage at bottom of window
    battery_voc_max_v: float = 860.0    # open-circuit voltage at top of window
    battery_resistance_ohm: float = 0.08
    superclip_power_kw: float = 350.0   # max harvest power while at full throttle (2026)

    @property
    def electrical_chain_efficiency(self) -> float:
        """DC bus <-> MGU-K shaft efficiency (one direction)."""
        return self.mguk_efficiency * self.inverter_efficiency

    def ice_only(self) -> "PowerUnit":
        return replace(self, name=f"{self.name} - ICE only (no ERS)", ers_enabled=False)


DEPLOY_MODES = {
    "none": "No deployment",
    "greedy": "Greedy (full power from every corner exit until the lap budget is spent)",
    "uniform": "Uniform (constant fraction of maximum power whenever at full throttle)",
    "low_speed": "Low-speed priority (deploy only below a speed threshold)",
    "high_speed": "High-speed priority (deploy only above a speed threshold)",
}


@dataclass(frozen=True)
class Strategy:
    """How the stored electrical energy is deployed and harvested.

    ``deploy_param`` depends on ``deploy_mode``:
      greedy     -> lap deployment budget in MJ
      uniform    -> fraction of maximum MGU-K power (0..1)
      low_speed  -> deploy while speed < deploy_param (km/h)
      high_speed -> deploy while speed > deploy_param (km/h)
    """

    name: str = "Low-speed priority"
    deploy_mode: str = "low_speed"
    deploy_param: float = 250.0
    soc_start: float = 0.5              # fraction of the ES window
    soc_min: float = 0.0
    soc_max: float = 1.0
    regen: bool = True
    superclip: bool = False             # harvest at full throttle above a speed (2026 practice)
    superclip_speed_kph: float = 300.0
    part_throttle_harvest: bool = False
    override: bool = False              # 2026 "Overtake / Override" deployment curve

    def with_(self, **kw) -> "Strategy":
        return replace(self, **kw)


PU_2026 = PowerUnit(
    name="2026 regulations (ICE 400 kW + MGU-K 350 kW)",
    ice_power_kw=400.0,
    ice_efficiency=0.48,
    mguk_power_kw=350.0,
    deploy_taper="fia2026",
    harvest_limit_mj=8.5,
    deploy_limit_mj=None,
    es_window_mj=4.0,
)

PU_2014_2025 = PowerUnit(
    name="2014-2025 regulations (ICE 560 kW + MGU-K 120 kW)",
    ice_power_kw=560.0,
    ice_efficiency=0.47,
    mguk_power_kw=120.0,
    deploy_taper=None,
    harvest_limit_mj=2.0,
    deploy_limit_mj=4.0,
    es_window_mj=4.0,
)

PU_KERS_2009 = PowerUnit(
    name="2009 KERS (ICE 560 kW + KERS 60 kW)",
    ice_power_kw=560.0,
    ice_efficiency=0.30,
    mguk_power_kw=60.0,
    deploy_taper=None,
    harvest_limit_mj=None,
    deploy_limit_mj=0.4,
    es_window_mj=0.6,
    battery_voc_min_v=300.0,
    battery_voc_max_v=400.0,
    battery_resistance_ohm=0.10,
)

PU_PRESETS = {
    "2026": PU_2026,
    "2014-2025": PU_2014_2025,
    "2009 KERS": PU_KERS_2009,
}

CAR_2025 = Vehicle(name="2014-2025 style car (no active aero)")
CAR_2026 = Vehicle(name="2026 style car (active aero straight mode)", active_aero=True)
DEFAULT_VEHICLE = CAR_2026


def car_for(pu: PowerUnit) -> Vehicle:
    """Chassis that matches a power-unit era (2026 cars use active aerodynamics)."""
    return CAR_2026 if pu.deploy_taper == "fia2026" else CAR_2025


def as_dict(obj) -> dict:
    return asdict(obj)
