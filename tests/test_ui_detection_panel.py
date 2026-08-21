"""UI tests for DetectionPanel table usability and pop-out."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSizePolicy

from sdr_console.detect.identified import IdentifiedPeak
from sdr_console.ui.detection_panel import (
    COL_BANDWIDTH,
    COL_COUNT,
    COL_MOD,
    COL_PROTOCOL,
    DETECTION_COLUMN_COUNT,
    DETECTION_HEADERS,
    SHELL_COLUMN_INDEXES,
    DetectionPanel,
)

pytest.importorskip("pytestqt")


def _peak(
    *,
    name: str,
    frequency_hz: float,
    power_db: float,
    detection_count: int,
) -> IdentifiedPeak:
    return IdentifiedPeak(
        name=name,
        frequency_hz=frequency_hz,
        power_db=power_db,
        capture_gain_db=20.0,
        detection_count=detection_count,
    )


@pytest.fixture
def panel(qtbot) -> DetectionPanel:
    widget = DetectionPanel()
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_empty_placeholder_visible_when_no_peaks(panel: DetectionPanel) -> None:
    assert panel._table_stack.currentWidget() is panel._placeholder
    assert "Henüz sinyal tespit edilmedi" in panel._placeholder.text()


def test_table_preserves_detection_order(panel: DetectionPanel) -> None:
    assert panel.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert panel._table.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding

    panel.update_peaks(
        [
            _peak(name="B", frequency_hz=100e6, power_db=-10.0, detection_count=2),
            _peak(name="A", frequency_hz=90e6, power_db=-5.0, detection_count=1),
        ]
    )
    assert panel._table_stack.currentWidget() is panel._table
    assert not panel._table.isSortingEnabled()
    assert panel._table.item(0, 0).text() == "100.000"
    assert panel._table.item(1, 0).text() == "90.000"
    assert panel._table.item(0, 4).text() == "2"
    assert panel._table.item(1, 4).text() == "1"


def test_popout_moves_table_and_restores(panel: DetectionPanel, qtbot) -> None:
    panel.update_peaks(
        [_peak(name="A", frequency_hz=97e6, power_db=-20.0, detection_count=1)]
    )
    qtbot.mouseClick(panel._popout_button, Qt.MouseButton.LeftButton)
    assert panel._popout is not None
    assert panel._popout.isVisible()
    assert panel._dock_placeholder.isVisible()
    assert panel._table_stack.parentWidget() is panel._popout
    assert panel._table_stack.currentWidget() is panel._table
    assert panel._table.isVisible()
    assert panel._table.item(0, 0).text() == "97.000"
    assert panel._popout_button.text() == "Geri Al"

    panel._popout.close()
    qtbot.waitUntil(lambda: panel._popout is None)
    assert panel._table_stack.parentWidget() is panel._list_host
    assert panel._table_stack.currentWidget() is panel._table
    assert not panel._dock_placeholder.isVisible()
    assert panel._popout_button.text() == "Büyüt"


def test_frequency_cell_emits_tune_signal(panel: DetectionPanel, qtbot) -> None:
    panel.update_peaks(
        [_peak(name="A", frequency_hz=97_000_000.0, power_db=-20.0, detection_count=1)]
    )

    with qtbot.waitSignal(panel.frequency_selected, timeout=1000) as blocker:
        panel._table.cellClicked.emit(0, 0)

    assert blocker.args == [97_000_000.0]


def test_update_peaks_skips_redundant_rebuild(panel: DetectionPanel) -> None:
    peaks = [_peak(name="A", frequency_hz=97e6, power_db=-20.0, detection_count=1)]
    panel.update_peaks(peaks)
    first_item = panel._table.item(0, 0)
    panel.update_peaks(peaks)
    assert panel._table.item(0, 0) is first_item


def test_popout_shows_empty_placeholder(panel: DetectionPanel, qtbot) -> None:
    qtbot.mouseClick(panel._popout_button, Qt.MouseButton.LeftButton)
    assert panel._popout is not None
    assert panel._table_stack.currentWidget() is panel._placeholder
    assert panel._placeholder.isVisible()
    assert "Henüz sinyal tespit edilmedi" in panel._placeholder.text()
    panel._popout.close()


def test_detection_controls_have_explanatory_tooltips(panel: DetectionPanel) -> None:
    threshold_tip = panel._threshold_spin.toolTip()
    merge_tip = panel._merge_bandwidth_spin.toolTip()
    assert "aday sinyal" in threshold_tip
    assert "birle" in merge_tip.casefold()
    hint = panel._controls_hint.text()
    assert "Eşik" in hint or "Esik" in hint
    assert "Birleştirme mesafesi" in hint or "Birlestirme mesafesi" in hint


def test_table_reserves_shell_columns_hidden_with_placeholder(panel: DetectionPanel) -> None:
    panel.update_peaks(
        [_peak(name="A", frequency_hz=97e6, power_db=-20.0, detection_count=1)]
    )
    assert panel._table.columnCount() == DETECTION_COLUMN_COUNT
    headers = [
        panel._table.horizontalHeaderItem(index).text()
        for index in range(DETECTION_COLUMN_COUNT)
    ]
    assert headers == list(DETECTION_HEADERS)
    for column in SHELL_COLUMN_INDEXES:
        assert panel._table.isColumnHidden(column)
    assert not panel._table.isColumnHidden(COL_BANDWIDTH)
    assert not panel._table.isColumnHidden(COL_COUNT)
    assert panel._table.item(0, COL_BANDWIDTH).text() == "—"
    assert panel._table.item(0, COL_MOD).text() == "—"
    assert panel._table.item(0, COL_PROTOCOL).text() == "—"


def test_row_context_menu_listen_enabled_shell_actions_disabled(
    panel: DetectionPanel,
) -> None:
    panel.update_peaks(
        [_peak(name="A", frequency_hz=97e6, power_db=-20.0, detection_count=1)]
    )
    menu = panel._row_context_menu()
    labels = {action.text(): action for action in menu.actions()}
    assert labels["Dinle"].isEnabled()
    assert not labels["Locate"].isEnabled()
    assert not labels["Assign ET"].isEnabled()
    assert panel._table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
