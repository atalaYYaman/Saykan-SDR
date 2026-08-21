"""Stable feature-panel ids and short tab labels (MASTER §9)."""

from __future__ import annotations

ED_PANEL_NAMES: tuple[str, ...] = (
    "dock_detection",
    "dock_scan",
    "dock_df",
    "dock_geoloc",
    "dock_params",
)
ET_PANEL_NAMES: tuple[str, ...] = (
    "dock_tx",
    "dock_ea_jam",
    "dock_ea_deceive",
    "dock_ea_gnss",
)
NOW_PANEL_NAMES: frozenset[str] = frozenset(
    {"dock_detection", "dock_scan", "dock_tx"}
)

DOCK_SHORT_LABELS: dict[str, str] = {
    "dock_detection": "Tespit",
    "dock_scan": "Tarama",
    "dock_df": "DF",
    "dock_geoloc": "Konum",
    "dock_params": "Parametre",
    "dock_tx": "TX",
    "dock_ea_jam": "Karıştırma",
    "dock_ea_deceive": "Aldatma",
    "dock_ea_gnss": "GNSS",
}
