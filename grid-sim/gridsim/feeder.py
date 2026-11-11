"""One low-voltage neighbourhood in pandapower: a transformer and 50 homes.

Layout: one 11/0.4 kV transformer feeding two overhead lines. Each line has
13 poles 40 m apart with 25 homes spread along it. The model is balanced
three-phase. Real homes are mostly single-phase, so real voltages are less
even than this model shows. All values are assumptions until the utility
gives us real ones (see ASSUMPTIONS).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandapower as pp

V_UPPER_PU = 1.06  # statutory 230 V +6%. Also the CEB 10-minute inverter limit.
V_LOWER_PU = 0.94  # statutory 230 V -6%


@dataclass(frozen=True)
class FeederConfig:
    n_homes: int = 50
    n_lines: int = 2
    span_m: float = 40.0
    transformer_kva: float = 100.0
    mv_kv: float = 11.0
    lv_kv: float = 0.4
    source_voltage_pu: float = 1.02  # MV side, so homes sit a little above 230 V with no solar
    trafo_vk_percent: float = 4.0
    trafo_vkr_percent: float = 1.75
    trafo_pfe_kw: float = 0.26
    trafo_i0_percent: float = 0.5
    line_r_ohm_per_km: float = 0.443  # 70 mm2 aluminium bundled conductor
    line_x_ohm_per_km: float = 0.083
    line_max_i_ka: float = 0.18
    power_factor: float = 0.95

    def describe(self) -> dict:
        return asdict(self) | {
            "model": "balanced three-phase power flow (pandapower)",
            "not_modelled": "single-phase connections and phase imbalance, service cables, "
            "inverters tripping at high voltage, tap changes, neighbouring feeders",
        }


class Feeder:
    """Build once, then call ``solve`` for each hour."""

    def __init__(self, config: FeederConfig | None = None):
        self.config = cfg = config or FeederConfig()
        net = pp.create_empty_network(sn_mva=1.0)
        mv = pp.create_bus(net, cfg.mv_kv, name="MV")
        lv = pp.create_bus(net, cfg.lv_kv, name="LV busbar")
        pp.create_ext_grid(net, mv, vm_pu=cfg.source_voltage_pu)
        pp.create_transformer_from_parameters(
            net, mv, lv,
            sn_mva=cfg.transformer_kva / 1000.0,
            vn_hv_kv=cfg.mv_kv, vn_lv_kv=cfg.lv_kv,
            vk_percent=cfg.trafo_vk_percent, vkr_percent=cfg.trafo_vkr_percent,
            pfe_kw=cfg.trafo_pfe_kw, i0_percent=cfg.trafo_i0_percent,
        )
        per_line = int(np.ceil(cfg.n_homes / cfg.n_lines))
        poles_per_line = int(np.ceil(per_line / 2))
        home_bus: list[int] = []
        for line in range(cfg.n_lines):
            previous = lv
            for pole in range(poles_per_line):
                bus = pp.create_bus(net, cfg.lv_kv, name=f"L{line + 1} pole {pole + 1}")
                pp.create_line_from_parameters(
                    net, previous, bus, length_km=cfg.span_m / 1000.0,
                    r_ohm_per_km=cfg.line_r_ohm_per_km, x_ohm_per_km=cfg.line_x_ohm_per_km,
                    c_nf_per_km=0.0, max_i_ka=cfg.line_max_i_ka,
                )
                previous = bus
                for _ in range(2):
                    if len(home_bus) < min(cfg.n_homes, (line + 1) * per_line):
                        home_bus.append(bus)
        self.home_bus = np.array(home_bus)
        self.tan_phi = float(np.tan(np.arccos(cfg.power_factor)))
        for home, bus in enumerate(self.home_bus):
            pp.create_load(net, bus, p_mw=0.0, q_mvar=0.0, name=f"home {home + 1}")
            pp.create_sgen(net, bus, p_mw=0.0, q_mvar=0.0, name=f"pv {home + 1}")
        self.net = net

    def solve(self, load_kw: np.ndarray, pv_kw: np.ndarray) -> dict:
        """Run one power flow. Inputs are per home, in kW. PV runs at unity power factor."""
        net = self.net
        net.load["p_mw"] = load_kw / 1000.0
        net.load["q_mvar"] = load_kw * self.tan_phi / 1000.0
        net.sgen["p_mw"] = pv_kw / 1000.0
        pp.runpp(net, numba=False)
        home_v = net.res_bus.vm_pu.to_numpy()[self.home_bus]
        return {
            "home_v_pu": home_v,
            "v_max_pu": float(home_v.max()),
            "v_min_pu": float(home_v.min()),
            "trafo_loading_pct": float(net.res_trafo.loading_percent.iloc[0]),
            # positive = power flowing from the grid into the neighbourhood
            "trafo_p_kw": float(net.res_trafo.p_hv_mw.iloc[0] * 1000.0),
            "line_loading_max_pct": float(net.res_line.loading_percent.max()),
        }
