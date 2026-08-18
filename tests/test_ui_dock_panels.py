"""Dock panel helper tests."""

from __future__ import annotations

from PyQt6.QtWidgets import QDockWidget, QLabel, QMainWindow

from sdr_console.ui.dock_panels import create_panel_dock

_FLOATABLE = QDockWidget.DockWidgetFeature.DockWidgetFloatable
_CLOSABLE = QDockWidget.DockWidgetFeature.DockWidgetClosable


def test_create_panel_dock_sets_title_and_widget(qtbot) -> None:
    host = QMainWindow()
    qtbot.addWidget(host)
    label = QLabel("panel body")
    dock = create_panel_dock(host, "Test Panel", label, "dock_test")

    assert dock.windowTitle() == "Test Panel"
    assert dock.objectName() == "dock_test"
    assert dock.widget() is label
    assert (dock.features() & _CLOSABLE) == _CLOSABLE
    assert (dock.features() & _FLOATABLE) != _FLOATABLE
