"""ET RF çıkış onay diyaloğu — yetkili test penceresi zorunlu (MASTER §4.5)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class EaConfirmDialog(QDialog):
    """Karıştırma / ET yayını: checkbox işaretlenmeden Onayla kapalı."""

    def __init__(
        self,
        *,
        freq_hz: float,
        bandwidth_hz: float,
        duration_s: float,
        attenuation_db: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("RF Çıkış Onayı")
        self.setModal(True)
        self.setObjectName("ea_confirm_dialog")

        warning = QLabel("⚠ ET modu — yalnızca yetkili test")
        warning.setWordWrap(True)
        warning.setObjectName("ea_confirm_warning")

        summary = QLabel(
            f"Frekans: {freq_hz / 1_000_000.0:.3f} MHz   "
            f"BW: {bandwidth_hz / 1_000.0:.1f} kHz\n"
            f"Süre: {duration_s:.2f} s   "
            f"Attenuation: {attenuation_db:.0f} dB"
        )
        summary.setWordWrap(True)
        summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._authorized = QCheckBox("Yetkili test penceresi içindeyim")
        self._authorized.setObjectName("ea_confirm_authorized")

        jsr = QLabel("JSR: —")
        jsr.setObjectName("ea_confirm_jsr")
        jsr.setEnabled(False)
        jsr.setToolTip("JSR metre SHELL — backend yok, sahte değer yok.")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel is not None:
            cancel.setText("İptal")
        self._ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if self._ok is not None:
            self._ok.setText("Onayla ve Başlat")
            self._ok.setEnabled(False)
            self._ok.setObjectName("ea_confirm_ok")
        self._authorized.toggled.connect(self._on_authorized_toggled)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addWidget(warning)
        layout.addWidget(summary)
        layout.addWidget(self._authorized)
        layout.addWidget(jsr)
        layout.addWidget(buttons)

    def _on_authorized_toggled(self, checked: bool) -> None:
        if self._ok is not None:
            self._ok.setEnabled(bool(checked))

    def authorized_window(self) -> bool:
        return self._authorized.isChecked()

    @classmethod
    def ask(
        cls,
        *,
        freq_hz: float,
        bandwidth_hz: float,
        duration_s: float,
        attenuation_db: float,
        parent: QWidget | None = None,
    ) -> bool:
        """Onay + yetkili pencere; ikisi de yoksa ``False``."""
        dialog = cls(
            freq_hz=freq_hz,
            bandwidth_hz=bandwidth_hz,
            duration_s=duration_s,
            attenuation_db=attenuation_db,
            parent=parent,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        return dialog.authorized_window()
