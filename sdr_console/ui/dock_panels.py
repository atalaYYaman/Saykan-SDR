"""QDockWidget yardımcıları — özellik panelleri için ortak oluşturma.

Yerleşim notları (QMainWindow dock sistemi):
- Sol: Receiver/Audio/Display sabit sütun; Tespit/Tarama/TX toggle'ları HoverDrawer.
- Sağ özellik panelleri (Sinyal Tespiti/Tarama/TX) sağda sabit, yüzer pop-up yok.
  Açık olanlar dikey bölünür (`splitDockWidget`); sekmeli değil.
- Tüm dock'lar kapatıldığında merkez spektrum alanı genişler.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDockWidget, QWidget


def create_panel_dock(
    parent: QWidget,
    title: str,
    panel: QWidget,
    object_name: str,
    *,
    floatable: bool = False,
) -> QDockWidget:
    """Kapatılabilir panel dock'u oluştur; varsayılan olarak yüzer pencere olamaz."""
    dock = QDockWidget(title, parent)
    dock.setObjectName(object_name)
    dock.setWidget(panel)
    features = (
        QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QDockWidget.DockWidgetFeature.DockWidgetClosable
    )
    if floatable:
        features |= QDockWidget.DockWidgetFeature.DockWidgetFloatable
    dock.setFeatures(features)
    return dock


# Yeni özellik paneli eklerken object_name önekini koruyun: dock_<kısa_ad>
# Ayrıntılı adımlar: sdr_console/ui/README.md → "Yeni dock paneli ekleme"
