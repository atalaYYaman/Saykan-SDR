# UI — Control

Ana pencere, Start/Stop, cihaz seçimi, frekans/kazanç/sample rate kontrolleri.

**Sorumluluklar:**
- `MainWindow` — transport, tuning spinbox'ları, durum satırı
- Receiver: cihaz merkez frekansı + adım, VFO (dinleme frekansı), kazanç + adım,
  bant genişliği, kanal özeti
- Audio: Enable, demod modu (AM / N-FM / W-FM / USB / LSB / CW), volume slider +
  sayısal giriş
- `QTimer` — pipeline output queue'dan periyodik okuma (GUI thread'de yalnızca çizim)
- Cihaz seçimi (Mock, Mock AM test, Pluto, RTL-SDR, HackRF)
- Tema — `sdr_console/ui/theme/` (`design-system/MASTER.md` token'ları → Fusion
  `QPalette` + QSS). Spektrum kalemi Tur D'de; yerleşim Tur B/C'de.

**Bağımlılık yönü:** ui → viz, pipeline, hal, config, demod (factory). DSP'ye
doğrudan erişim yasak.

## Dock panel sistemi

Ana pencere `QMainWindow` dock düzenini kullanır:

| Bileşen | Dosya | Rol |
|---------|-------|-----|
| Merkez alan | `main_window.py` | Transport + spektrum/waterfall + status |
| Panel host | `feature_host.py` | Açık Tespit/Tarama/TX panellerini dikey böler |
| Sol toolbar | `panel_toolbar.py` | HoverDrawer içindeki görünürlük kutuları |
| Panel widget'ları | `detection_panel.py`, `scan_panel.py`, `tx_panel.py`, … | İş mantığı + Qt widget |

**Varsayılan yerleşim:**
- Sol sabit: Receiver / Audio / Display
- En sol şerit: `HoverDrawer` — üzerine gelince Tespit / Tarama / TX kutuları açılır
- Spektrumun sağı: `FeaturePanelHost` — işaretli paneller dikey splitter ile **aynı anda** görünür
- Hiçbiri işaretli değilse sağ sütun kapanır, spektrum genişler

Toolbar toggle'ları `FeaturePanelHost.set_panel_visible()` ile senkron; sekmeli dock yok.

## Yeni dock paneli ekleme (Harita, …)

Örnek: **Yön Bulma / Harita** paneli. TX / Replay aynı deseni kullanır (`tx_panel.py`, `dock_tx`).

### 1. Panel widget'ı yazın

```python
# sdr_console/ui/tx_panel.py
class TxPanel(QWidget):
    ...
```

UI katmanı kuralları: HAL/DSP'ye doğrudan erişmeyin; pipeline veya üst seviye
servisleri `MainWindow` üzerinden bağlayın.

### 2. Host'a ekleyin (`MainWindow._build_ui` / `FeaturePanelHost`)

```python
self._feature_host = FeaturePanelHost(
    [
        ("dock_detection", self._detection_panel),
        ("dock_scan", self._scan_panel),
        ("dock_tx", self._tx_panel),
        ("dock_map", self._map_panel),  # yeni
    ]
)
```

`PanelToolBar(self._feature_host)` kutuları otomatik üretir.

### 3. Toolbar kısa etiketini kaydedin

```python
# sdr_console/ui/panel_toolbar.py → DOCK_SHORT_LABELS
"dock_map": "Harita",
```

### 4. Sinyal/slot bağlantılarını `MainWindow` içinde yapın

`_wire_signals()` veya panel özel helper'ında pipeline/TX katmanına bağlayın.

### Kontrol listesi

- [ ] Panel `objectName` öneki: `dock_<ad>`
- [ ] `FeaturePanelHost` listesine ekleme
- [ ] `DOCK_SHORT_LABELS` girişi
- [ ] `tests/test_ui_dock_layout.py` — gerekirse yeni panel için yerleşim testi

## Pencere durumu (dock yerleşimi)

`AppConfig.window_state` alanı `QMainWindow.saveState()` çıktısını Base64 olarak
saklar. Uygulama kapanırken `MainWindow._persist_window_state()` çağrılır;
açılışta `_restore_window_state()` dock/toolbar konumlarını geri yükler.
`window_layout_version` uyuşmazsa (ör. eski yüzer dock düzeni) kayıt yok sayılır
ve Tespit/Tarama/TX sağa sabitlenir.

Yeni panel ekledikten sonra eski `window_state` geçersiz olabilir; Qt restore
başarısız olursa varsayılan yerleşim kullanılır.
