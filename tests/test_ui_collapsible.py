"""Tests for collapsible control panels."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QLabel, QVBoxLayout

from sdr_console.ui.collapsible import CollapsibleGroupBox

pytest.importorskip("pytestqt")


def test_collapsible_hides_body_when_collapsed(qtbot) -> None:
    box = CollapsibleGroupBox("Receiver")
    label = QLabel("body")
    QVBoxLayout(box.content_widget()).addWidget(label)
    qtbot.addWidget(box)
    box.show()

    assert box.is_expanded()
    assert box.content_widget().isVisible()

    box.set_expanded(False)
    assert not box.is_expanded()
    assert not box.content_widget().isVisible()
    assert box.maximumHeight() < 200

    box.set_expanded(True)
    assert box.content_widget().isVisible()
    assert box.maximumHeight() >= 200
