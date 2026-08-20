"""Global QSS generated from MASTER tokens. Layout and pyqtgraph pens stay unchanged."""

from __future__ import annotations

import sdr_console.ui.theme.tokens as t


def build_stylesheet() -> str:
    """Application-wide stylesheet. Widget objectNames come from MASTER §9."""
    return f"""
QMainWindow, QDialog, QMessageBox {{
  background-color: {t.COLOR_BG_APP};
  color: {t.COLOR_TEXT_PRIMARY};
  font-family: {t.FONT_UI};
  font-size: {t.FONT_UI_PX}px;
}}
QLabel {{
  color: {t.COLOR_TEXT_PRIMARY};
}}
QWidget#toolbar_main {{
  background-color: {t.COLOR_BG_PANEL};
  border-bottom: 1px solid {t.COLOR_BORDER};
}}
QWidget#feature_host {{
  background-color: {t.COLOR_BG_PANEL};
  border-left: 1px solid {t.COLOR_BORDER};
}}
QWidget#dock_left_controls,
QWidget#controls_column {{
  background-color: {t.COLOR_BG_APP};
}}
QScrollArea#controls_scroll {{
  background-color: {t.COLOR_BG_APP};
  border: none;
}}
QLabel#status_bar {{
  color: {t.COLOR_TEXT_PRIMARY};
  background-color: {t.COLOR_BG_PANEL};
  border-top: 1px solid {t.COLOR_BORDER};
  padding: {t.SPACE_2_PX}px {t.SPACE_2_PX}px;
  font-family: {t.FONT_MONO};
  font-size: {t.FONT_CAPTION_PX}px;
  font-weight: 600;
  min-height: {t.STATUS_MIN_HEIGHT_PX}px;
}}
QFrame#hover_drawer_rail {{
  background-color: {t.COLOR_BORDER};
  border-right: 1px solid {t.COLOR_BG_APP};
}}
QPushButton {{
  background-color: {t.SLATE_700};
  color: {t.COLOR_TEXT_PRIMARY};
  border: 1px solid {t.SLATE_600};
  border-radius: {t.RADIUS_MD_PX}px;
  min-height: {t.BUTTON_MIN_HEIGHT_PX}px;
  padding: 0 {t.SPACE_3_PX}px;
}}
QPushButton:hover {{
  background-color: {t.COLOR_BG_ELEVATED};
}}
QPushButton:disabled {{
  color: {t.COLOR_TEXT_DISABLED};
  background-color: {t.COLOR_BG_PANEL};
  border-color: {t.COLOR_BORDER};
}}
QPushButton#transport_start {{
  background-color: {t.COLOR_ED_ACCENT};
  color: {t.COLOR_BG_APP};
  border: 1px solid {t.COLOR_ED_ACCENT};
  font-weight: 600;
}}
QPushButton#transport_start:hover {{
  background-color: {t.CYAN_500};
}}
QPushButton#transport_start:disabled {{
  background-color: {t.CYAN_900};
  color: {t.COLOR_TEXT_DISABLED};
  border-color: {t.COLOR_BORDER};
}}
QPushButton#transport_stop {{
  background-color: transparent;
  color: {t.COLOR_ET_ACCENT};
  border: 1px solid {t.COLOR_ET_ACCENT};
  font-weight: 600;
}}
QPushButton#transport_stop:hover {{
  background-color: {t.RED_900};
}}
QPushButton#transport_stop:disabled {{
  color: {t.COLOR_TEXT_DISABLED};
  border-color: {t.COLOR_BORDER};
  background-color: transparent;
}}
QPushButton#transport_scan {{
  background-color: {t.SLATE_700};
  color: {t.COLOR_TEXT_PRIMARY};
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QAbstractSpinBox {{
  background-color: {t.COLOR_BG_INPUT};
  color: {t.COLOR_TEXT_PRIMARY};
  border: 1px solid {t.COLOR_BORDER};
  border-radius: {t.RADIUS_SM_PX}px;
  padding: 2px {t.SPACE_2_PX}px;
  min-height: {t.BUTTON_MIN_HEIGHT_PX}px;
  selection-background-color: {t.COLOR_ED_ACCENT};
  selection-color: {t.COLOR_BG_APP};
}}
QLineEdit#transport_uri {{
  font-family: {t.FONT_MONO};
  font-size: {t.FONT_CAPTION_PX}px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QAbstractSpinBox:focus {{
  border: {t.FOCUS_BORDER_PX}px solid {t.COLOR_BORDER_FOCUS};
}}
QComboBox::drop-down {{
  border: none;
  width: 18px;
}}
QComboBox QAbstractItemView {{
  background-color: {t.COLOR_BG_PANEL};
  color: {t.COLOR_TEXT_PRIMARY};
  selection-background-color: {t.COLOR_ED_ACCENT};
  selection-color: {t.COLOR_BG_APP};
  border: 1px solid {t.COLOR_BORDER};
}}
QCheckBox {{
  color: {t.COLOR_TEXT_PRIMARY};
  spacing: {t.SPACE_1_PX}px;
}}
QSlider::groove:horizontal {{
  background: {t.COLOR_BORDER};
  height: 6px;
  border-radius: 3px;
}}
QSlider::handle:horizontal {{
  background: {t.COLOR_ED_ACCENT};
  width: 14px;
  margin: -5px 0;
  border-radius: 7px;
}}
QGroupBox, CollapsibleGroupBox {{
  background-color: {t.COLOR_BG_PANEL};
  border: 1px solid {t.COLOR_BORDER};
  border-radius: {t.RADIUS_MD_PX}px;
  margin-top: 14px;
  padding-top: 4px;
  color: {t.COLOR_TEXT_PRIMARY};
  font-size: {t.FONT_SECTION_PX}px;
  font-weight: 600;
}}
QGroupBox::title, CollapsibleGroupBox::title {{
  subcontrol-origin: margin;
  subcontrol-position: top left;
  left: 10px;
  padding: 0 6px;
  color: {t.COLOR_TEXT_PRIMARY};
}}
QHeaderView::section {{
  background-color: {t.COLOR_BG_PANEL};
  color: {t.COLOR_TEXT_SECONDARY};
  border: none;
  border-bottom: 1px solid {t.COLOR_BORDER};
  padding: 4px;
}}
QTableView, QTableWidget {{
  background-color: {t.COLOR_BG_PANEL};
  alternate-background-color: {t.COLOR_BG_ELEVATED};
  color: {t.COLOR_TEXT_PRIMARY};
  gridline-color: {t.COLOR_BORDER};
  selection-background-color: {t.CYAN_900};
  selection-color: {t.COLOR_TEXT_PRIMARY};
  border: 1px solid {t.COLOR_BORDER};
}}
QScrollBar:vertical {{
  background: {t.COLOR_BG_APP};
  width: 10px;
  margin: 0;
}}
QScrollBar::handle:vertical {{
  background: {t.SLATE_600};
  min-height: 24px;
  border-radius: 4px;
}}
QScrollBar:horizontal {{
  background: {t.COLOR_BG_APP};
  height: 10px;
}}
QScrollBar::handle:horizontal {{
  background: {t.SLATE_600};
  min-width: 24px;
  border-radius: 4px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
  width: 0;
  height: 0;
}}
QToolTip {{
  background-color: {t.COLOR_BG_PANEL};
  color: {t.COLOR_TEXT_PRIMARY};
  border: 1px solid {t.COLOR_BORDER};
}}
QMenu {{
  background-color: {t.COLOR_BG_PANEL};
  color: {t.COLOR_TEXT_PRIMARY};
  border: 1px solid {t.COLOR_BORDER};
}}
QMenu::item:selected {{
  background-color: {t.CYAN_900};
}}
QWidget[shell="true"] {{
  color: {t.COLOR_TEXT_DISABLED};
}}
""".strip()
