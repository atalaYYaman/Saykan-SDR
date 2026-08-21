"""Sidebar controls and table for automatic signal detection."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sdr_console.detect.identified import IdentifiedPeak
from sdr_console.detect.peaks import (
    DEFAULT_MERGE_BANDWIDTH_HZ,
    MAX_MERGE_DISTANCE_HZ,
    MIN_MERGE_DISTANCE_HZ,
)
from sdr_console.ui.theme.tokens import COLOR_DETECT_ACCENT, COLOR_TEXT_DISABLED

DEFAULT_DETECTION_THRESHOLD_DB = -40.0
DEFAULT_DETECTION_MERGE_BANDWIDTH_HZ = DEFAULT_MERGE_BANDWIDTH_HZ

_FREQUENCY_ROLE = Qt.ItemDataRole.UserRole
_BANDWIDTH_ROLE = Qt.ItemDataRole.UserRole + 2
_SORT_ROLE = Qt.ItemDataRole.UserRole + 1

_EMPTY_PLACEHOLDER_TEXT = "Henüz sinyal tespit edilmedi"
_POPOUT_PLACEHOLDER_TEXT = "Liste ayrı pencerede açık"
_FREQUENCY_LINK_COLOR = QColor(COLOR_DETECT_ACCENT)
_SHELL_PLACEHOLDER = "—"
_SHELL_TOOLTIP = "SHELL — bağlı değil"

# MASTER §4.3 — NOW then reserved SHELL columns (hidden).
COL_FREQUENCY = 0
COL_BANDWIDTH = 1
COL_POWER = 2
COL_GAIN = 3
COL_COUNT = 4
COL_ANALOG_DIGITAL = 5
COL_MOD = 6
COL_PROTOCOL = 7
COL_MULTIPLEX = 8
COL_EKKT = 9
COL_CONFIDENCE = 10
COL_TOA = 11
DETECTION_COLUMN_COUNT = 12
SHELL_COLUMN_INDEXES: tuple[int, ...] = (
    COL_ANALOG_DIGITAL,
    COL_MOD,
    COL_PROTOCOL,
    COL_MULTIPLEX,
    COL_EKKT,
    COL_CONFIDENCE,
    COL_TOA,
)
DETECTION_HEADERS: tuple[str, ...] = (
    "Frekans (MHz)",
    "BW",
    "Güç (dB)",
    "Gain (dB)",
    "Tekrar",
    "A/D",
    "Mod",
    "Protokol",
    "Çoklama",
    "EKKT",
    "Güven",
    "TOA",
)


def _peaks_snapshot(peaks: list[IdentifiedPeak]) -> tuple[tuple[float, float, float, int], ...]:
    return tuple(
        (
            peak.frequency_hz,
            round(peak.power_db, 1),
            round(peak.capture_gain_db, 1),
            peak.detection_count,
        )
        for peak in peaks
    )


class _SortableTableItem(QTableWidgetItem):
    """Table item that sorts by a numeric/string key instead of display text."""

    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(_SORT_ROLE)
        right = other.data(_SORT_ROLE)
        if left is not None and right is not None:
            try:
                return left < right
            except TypeError:
                return str(left) < str(right)
        return super().__lt__(other)


def _shell_cell() -> _SortableTableItem:
    item = _SortableTableItem(_SHELL_PLACEHOLDER)
    item.setData(_SORT_ROLE, "")
    item.setForeground(QColor(COLOR_TEXT_DISABLED))
    item.setToolTip(_SHELL_TOOLTIP)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item


class DetectionPanel(QGroupBox):
    """Detection toggle, threshold control, and confirmed-signal table."""

    toggled = pyqtSignal(bool)
    threshold_changed = pyqtSignal(float)
    merge_bandwidth_changed = pyqtSignal(float)
    frequency_selected = pyqtSignal(float)
    row_selected = pyqtSignal(float, float)
    clear_all_requested = pyqtSignal()
    remove_selected_requested = pyqtSignal(list)

    def __init__(
        self,
        *,
        threshold_db: float = DEFAULT_DETECTION_THRESHOLD_DB,
        merge_bandwidth_hz: float = DEFAULT_DETECTION_MERGE_BANDWIDTH_HZ,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Sinyal Tespiti", parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._columns_auto_sized = False
        self._peak_count = 0
        self._displayed_peaks_key: tuple[tuple[float, float, float, int], ...] = ()
        self._popout: QDialog | None = None

        self._enabled_check = QCheckBox("Etkin")
        self._enabled_check.setToolTip(
            "Görünen bant içindeki kalıcı sinyalleri otomatik listele"
        )

        self._threshold_spin = QDoubleSpinBox()
        self._threshold_spin.setSuffix(" dB")
        self._threshold_spin.setDecimals(1)
        self._threshold_spin.setRange(-120.0, 0.0)
        self._threshold_spin.setSingleStep(1.0)
        self._threshold_spin.setValue(threshold_db)
        self._threshold_spin.setToolTip(
            "Spektrum gücünde bu eşiğin üzerindeki tepeler aday sinyal sayılır. "
            "Daha düşük değer daha fazla, daha yüksek değer daha az sinyal listeler."
        )

        self._merge_bandwidth_spin = QDoubleSpinBox()
        self._merge_bandwidth_spin.setSuffix(" MHz")
        self._merge_bandwidth_spin.setDecimals(3)
        self._merge_bandwidth_spin.setRange(
            MIN_MERGE_DISTANCE_HZ / 1_000_000.0,
            MAX_MERGE_DISTANCE_HZ / 1_000_000.0,
        )
        self._merge_bandwidth_spin.setSingleStep(0.025)
        self._merge_bandwidth_spin.setValue(merge_bandwidth_hz / 1_000_000.0)
        self._merge_bandwidth_spin.setToolTip(
            "İki frekans arasındaki fark bu değerden küçükse bunları birleştirip "
            "tek sinyal sayılır "
            f"({MIN_MERGE_DISTANCE_HZ / 1_000.0:g}–{MAX_MERGE_DISTANCE_HZ / 1_000.0:g} kHz). "
            "Geniş yayınlar (W-FM) için 0.15–0.2 MHz önerilir."
        )

        threshold_label = QLabel("dB eşiği")
        threshold_label.setToolTip(self._threshold_spin.toolTip())
        merge_label = QLabel("Birleştirme mesafesi")
        merge_label.setToolTip(self._merge_bandwidth_spin.toolTip())

        self._controls_hint = QLabel(
            "Eşik: aday sinyal gücü · Birleştirme mesafesi: "
            "aynı yayının yan loblarını tek satırda toplar"
        )
        self._controls_hint.setWordWrap(True)
        self._controls_hint.setStyleSheet("color: palette(mid);")

        controls = QFormLayout()
        controls.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        controls.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        controls.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(6)
        controls.addRow(self._enabled_check)
        controls.addRow(threshold_label, self._threshold_spin)
        controls.addRow(merge_label, self._merge_bandwidth_spin)

        self._table = QTableWidget(0, DETECTION_COLUMN_COUNT)
        self._table.setObjectName("detection_table")
        self._table.setHorizontalHeaderLabels(list(DETECTION_HEADERS))
        self._table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        header = self._table.horizontalHeader()
        header.setSectionsMovable(False)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_FREQUENCY, QHeaderView.ResizeMode.Stretch)
        for column in SHELL_COLUMN_INDEXES:
            self._table.setColumnHidden(column, True)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self._placeholder = QLabel(_EMPTY_PLACEHOLDER_TEXT)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._placeholder.setMinimumHeight(120)
        self._placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._placeholder.setStyleSheet(
            "QLabel {"
            " color: palette(mid);"
            " border: 1px dashed palette(mid);"
            " border-radius: 4px;"
            " padding: 16px;"
            " background: palette(base);"
            "}"
        )

        self._table_stack = QStackedWidget()
        self._table_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._table_stack.addWidget(self._placeholder)  # index 0
        self._table_stack.addWidget(self._table)  # index 1

        self._dock_placeholder = QLabel(_POPOUT_PLACEHOLDER_TEXT)
        self._dock_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dock_placeholder.setWordWrap(True)
        self._dock_placeholder.setMinimumHeight(120)
        self._dock_placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._dock_placeholder.setStyleSheet(self._placeholder.styleSheet())
        self._dock_placeholder.hide()

        self._list_host = QWidget()
        self._list_host.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        list_host_layout = QVBoxLayout(self._list_host)
        list_host_layout.setContentsMargins(0, 0, 0, 0)
        list_host_layout.addWidget(self._table_stack, stretch=1)
        list_host_layout.addWidget(self._dock_placeholder, stretch=1)

        self._clear_all_button = QPushButton("Tümünü Sil")
        self._remove_selected_button = QPushButton("Seçilenleri Sil")
        self._popout_button = QPushButton("Büyüt")
        self._popout_button.setToolTip("Listeyi ayrı, yeniden boyutlandırılabilir pencerede aç")
        button_grid = QGridLayout()
        button_grid.setContentsMargins(0, 4, 0, 0)
        button_grid.setHorizontalSpacing(8)
        button_grid.setVerticalSpacing(8)
        for button in (
            self._clear_all_button,
            self._remove_selected_button,
            self._popout_button,
        ):
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            button.setMinimumHeight(28)
        button_grid.addWidget(self._clear_all_button, 0, 0)
        button_grid.addWidget(self._remove_selected_button, 0, 1)
        button_grid.addWidget(self._popout_button, 1, 0, 1, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)
        layout.addLayout(controls)
        layout.addWidget(self._controls_hint)
        layout.addWidget(self._list_host, stretch=1)
        layout.addLayout(button_grid)

        self._enabled_check.toggled.connect(self.toggled)
        self._threshold_spin.valueChanged.connect(self.threshold_changed)
        self._merge_bandwidth_spin.valueChanged.connect(self._emit_merge_bandwidth_changed)
        self._clear_all_button.clicked.connect(self.clear_all_requested.emit)
        self._remove_selected_button.clicked.connect(self._emit_remove_selected)
        self._popout_button.clicked.connect(self._toggle_popout)
        self._table.cellClicked.connect(self._on_frequency_cell_clicked)
        self._table.customContextMenuRequested.connect(self._on_table_context_menu)
        self._table.itemSelectionChanged.connect(self._emit_row_selection)
        self._refresh_table_view()

    def is_detection_enabled(self) -> bool:
        return self._enabled_check.isChecked()

    def threshold_db(self) -> float:
        return float(self._threshold_spin.value())

    def merge_bandwidth_hz(self) -> float:
        return float(self._merge_bandwidth_spin.value()) * 1_000_000.0

    def set_threshold_db(self, threshold_db: float) -> None:
        self._threshold_spin.blockSignals(True)
        self._threshold_spin.setValue(threshold_db)
        self._threshold_spin.blockSignals(False)

    def set_merge_bandwidth_hz(self, merge_bandwidth_hz: float) -> None:
        self._merge_bandwidth_spin.blockSignals(True)
        clamped_mhz = min(
            max(merge_bandwidth_hz / 1_000_000.0, self._merge_bandwidth_spin.minimum()),
            self._merge_bandwidth_spin.maximum(),
        )
        self._merge_bandwidth_spin.setValue(clamped_mhz)
        self._merge_bandwidth_spin.blockSignals(False)

    def selected_frequencies_hz(self) -> list[float]:
        rows = {index.row() for index in self._table.selectedIndexes()}
        frequencies_hz: list[float] = []
        for row in sorted(rows):
            item = self._table.item(row, COL_FREQUENCY)
            if item is None:
                continue
            frequency_hz = item.data(_FREQUENCY_ROLE)
            if frequency_hz is None:
                continue
            frequencies_hz.append(float(frequency_hz))
        return frequencies_hz

    def update_peaks(self, peaks: list[IdentifiedPeak]) -> None:
        snapshot = _peaks_snapshot(peaks)
        if snapshot == self._displayed_peaks_key:
            return

        self._displayed_peaks_key = snapshot
        self._table.setRowCount(len(peaks))
        for row, peak in enumerate(peaks):
            freq_mhz = peak.frequency_hz / 1_000_000.0
            freq_item = _SortableTableItem(f"{freq_mhz:.3f}")
            freq_item.setData(_FREQUENCY_ROLE, peak.frequency_hz)
            freq_item.setData(_SORT_ROLE, float(peak.frequency_hz))
            freq_item.setForeground(_FREQUENCY_LINK_COLOR)
            freq_item.setToolTip("Bu frekansa git (Dinle)")

            bw_item = _SortableTableItem(_SHELL_PLACEHOLDER)
            bw_item.setData(_SORT_ROLE, 0.0)
            bw_item.setData(_BANDWIDTH_ROLE, 0.0)
            bw_item.setToolTip("BW henüz ölçülmedi")
            bw_item.setForeground(QColor(COLOR_TEXT_DISABLED))
            bw_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            power_item = _SortableTableItem(f"{peak.power_db:.1f}")
            power_item.setData(_SORT_ROLE, float(peak.power_db))

            gain_item = _SortableTableItem(f"{peak.capture_gain_db:.1f}")
            gain_item.setData(_SORT_ROLE, float(peak.capture_gain_db))

            count_item = _SortableTableItem(str(peak.detection_count))
            count_item.setData(_SORT_ROLE, int(peak.detection_count))

            for numeric_item in (power_item, gain_item, count_item):
                numeric_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            self._table.setItem(row, COL_FREQUENCY, freq_item)
            self._table.setItem(row, COL_BANDWIDTH, bw_item)
            self._table.setItem(row, COL_POWER, power_item)
            self._table.setItem(row, COL_GAIN, gain_item)
            self._table.setItem(row, COL_COUNT, count_item)
            for column in SHELL_COLUMN_INDEXES:
                self._table.setItem(row, column, _shell_cell())

        self._peak_count = len(peaks)
        if peaks and not self._columns_auto_sized:
            self._table.resizeColumnsToContents()
            self._columns_auto_sized = True
        self._refresh_table_view()

    def clear(self) -> None:
        self._displayed_peaks_key = ()
        self._table.setRowCount(0)
        self._peak_count = 0
        self._refresh_table_view()

    def _on_frequency_cell_clicked(self, row: int, column: int) -> None:
        if column != COL_FREQUENCY:
            return
        item = self._table.item(row, COL_FREQUENCY)
        if item is None:
            return
        frequency_hz = item.data(_FREQUENCY_ROLE)
        if frequency_hz is None:
            return
        self.frequency_selected.emit(float(frequency_hz))

    def _emit_row_selection(self) -> None:
        row = self._table.currentRow()
        if row < 0 or self._table.item(row, COL_FREQUENCY) is None:
            self.row_selected.emit(0.0, 0.0)
            return
        freq_item = self._table.item(row, COL_FREQUENCY)
        bw_item = self._table.item(row, COL_BANDWIDTH)
        frequency_hz = float(freq_item.data(_FREQUENCY_ROLE) or 0.0)
        bandwidth_hz = 0.0
        if bw_item is not None:
            stored = bw_item.data(_BANDWIDTH_ROLE)
            if stored is not None:
                bandwidth_hz = float(stored)
        self.row_selected.emit(frequency_hz, bandwidth_hz)

    def _on_table_context_menu(self, pos) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        menu = self._row_context_menu()
        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen is not None and chosen.text() == "Dinle":
            item = self._table.item(row, COL_FREQUENCY)
            if item is None:
                return
            frequency_hz = item.data(_FREQUENCY_ROLE)
            if frequency_hz is not None:
                self.frequency_selected.emit(float(frequency_hz))

    def _row_context_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Dinle")
        locate = menu.addAction("Locate")
        locate.setEnabled(False)
        locate.setToolTip("DF bağlı değil")
        assign = menu.addAction("Assign ET")
        assign.setEnabled(False)
        assign.setToolTip("ET atama bağlı değil")
        return menu

    def _emit_remove_selected(self) -> None:
        frequencies_hz = self.selected_frequencies_hz()
        if frequencies_hz:
            self.remove_selected_requested.emit(frequencies_hz)

    def _emit_merge_bandwidth_changed(self, value_mhz: float) -> None:
        self.merge_bandwidth_changed.emit(float(value_mhz) * 1_000_000.0)

    def _toggle_popout(self) -> None:
        if self._popout is not None:
            self._popout.close()
            return
        self._open_popout()

    def _open_popout(self) -> None:
        if self._popout is not None:
            self._popout.raise_()
            self._popout.activateWindow()
            return

        dialog = QDialog(self.window())
        dialog.setWindowTitle("Sinyal Tespiti")
        dialog.setModal(False)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.resize(720, 480)
        dialog.setMinimumSize(420, 280)

        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(8, 8, 8, 8)
        # Move the whole stack so empty-state placeholder and table stay visible.
        dialog_layout.addWidget(self._table_stack)

        dialog.finished.connect(self._on_popout_finished)
        self._popout = dialog
        self._popout_button.setText("Geri Al")
        self._dock_placeholder.show()
        self._refresh_table_view()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _on_popout_finished(self, _result: int = 0) -> None:
        self._popout = None
        self._popout_button.setText("Büyüt")
        self._dock_placeholder.hide()
        host_layout = self._list_host.layout()
        assert host_layout is not None
        if self._table_stack.parent() is not self._list_host:
            host_layout.insertWidget(0, self._table_stack, stretch=1)
        self._refresh_table_view()

    def _refresh_table_view(self) -> None:
        if self._peak_count == 0:
            self._placeholder.setText(_EMPTY_PLACEHOLDER_TEXT)
            self._table_stack.setCurrentWidget(self._placeholder)
            self._placeholder.show()
            return

        self._table_stack.setCurrentWidget(self._table)
        # QStackedWidget keeps non-current pages hidden; force visible after reparent.
        self._table.show()
        self._table.setVisible(True)
