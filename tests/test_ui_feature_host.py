"""FeaturePanelHost görünürlük ve eşit bölme testleri."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QLabel

from sdr_console.ui.feature_host import FeaturePanelHost

pytest.importorskip("pytestqt")


def test_host_equalizes_visible_panels_and_keeps_tabs_when_empty(qtbot) -> None:
    one = QLabel("one")
    two = QLabel("two")
    three = QLabel("three")
    host = FeaturePanelHost(
        [
            ("dock_detection", one),
            ("dock_scan", two),
            ("dock_tx", three),
        ]
    )
    qtbot.addWidget(host)
    host.resize(320, 600)
    host.show()
    qtbot.waitExposed(host)

    assert host.isVisible()
    assert one.isVisible()
    assert two.isVisible()
    assert three.isVisible()

    host.set_panel_visible("dock_tx", False)
    assert not three.isVisible()
    assert one.isVisible()
    assert two.isVisible()
    assert host.isVisible()

    host.set_panel_visible("dock_detection", False)
    host.set_panel_visible("dock_scan", False)
    assert host.isVisible()
    assert host.tab_bar.isVisible()
    empty = host.findChild(QLabel, "feature_host_empty")
    assert empty is not None
    assert empty.isVisible()

    host.set_panel_visible("dock_scan", True)
    assert two.isVisible()
    assert not empty.isVisible()


def test_multiple_open_panels_keep_usable_height(qtbot) -> None:
    one = QLabel("one")
    two = QLabel("two")
    three = QLabel("three")
    host = FeaturePanelHost(
        [
            ("dock_detection", one),
            ("dock_scan", two),
            ("dock_tx", three),
        ]
    )
    qtbot.addWidget(host)
    host.resize(320, 400)
    host.show()
    qtbot.waitExposed(host)

    assert one.height() >= 80
    assert two.height() >= 80
    assert three.height() >= 80

