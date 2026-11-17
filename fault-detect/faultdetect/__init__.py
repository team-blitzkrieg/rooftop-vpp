"""Fault and settings detection, version 0. Two rules. See ../README.md."""

from .settings_check import Finding, check_settings, load_reference
from .underperformance import daily_ratio, flag_underperformance, peer_ratio

__all__ = [
    "Finding",
    "check_settings",
    "load_reference",
    "daily_ratio",
    "flag_underperformance",
    "peer_ratio",
]
