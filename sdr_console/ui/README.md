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
  `QPalette` + QSS). Spektrum kalemi Tur D'de.
- Transport — `TransportToolBar` (`QToolBar#toolbar_main`): cihaz, URI, Scan,
  Start, Stop ve ED/ET/GNSS/saat rozetleri.
- Sağ host — `FeaturePanelHost` üstünde ED/ET sekme şeridi; NOW paneller
  (Tespit/Tarama/TX) açık, SHELL paneller empty-state ve varsayılan gizli.

**Bağımlılık yönü:** ui → viz, pipeline, hal, config, demod (factory). DSP'ye
doğrudan erişim yasak.

## Dock panel sistemi

Ana pencere `QMainWindow` dock düzenini kullanır:

| Bileşen | Dosya | Rol |
|---------|-------|-----|
| Merkez alan | `main_window.py` | Spektrum/waterfall + status |
| Transport | `transport_toolbar.py` | `QToolBar`: cihaz / Start-Stop / SHELL rozetler |
| Panel host | `feature_host.py` | ED/ET sekmeler (her zaman görünür) + kaydırılabilir paneller |
| Sekme şeridi | `panel_toolbar.py` | Tespit/Tarama/DF/… görünür toggle |
| SHELL | `shell_panel.py` | Şartname yuvaları, sahte veri yok |
| Panel widget'ları | `detection_panel.py`, `scan_panel.py`, `tx_panel.py`, … | İş mantığı + Qt widget |

**Varsayılan yerleşim:**
- Sol sabit: Receiver / Audio / Display
- Spektrumun sağı: `FeaturePanelHost` — üstte ED/ET sekmeleri, altta açık paneller
- NOW (Tespit, Tarama, TX) varsayılan açık; SHELL sekmeler kapalı ama keşfedilebilir
- İçerik panelleri kapanınca sağ sütun kalır; ED/ET sekmelerinden yeniden açılır

Sekme toggle'ları `FeaturePanelHost.set_panel_visible()` ile senkron.

## Yeni dock paneli ekleme (Harita, …)

Örnek: **Yön Bulma / Harita** paneli. TX / Replay aynı deseni kullanır (`tx_panel.py`, `dock_tx`).

### 1. Panel widget'ı yazın

```python
# sdr_console/ui/tx_panel.py
class TxPanel(QWidget):
    ...
```

UI katmanı kuralları: HAL/DSP'ye doğrudan erişmeyin; pipeline veya üst seviye
servisleri `MainWindow` üzerinden bağlayın. Backend yoksa `shell_panel.py`
empty-state kullanın.

### 2. Host'a ekleyin (`MainWindow._build_ui` / `FeaturePanelHost`)

```python
self._feature_host = FeaturePanelHost(
    [
        ("dock_detection", self._detection_panel, True),
        ("dock_scan", self._scan_panel, True),
        ("dock_tx", self._tx_panel, True),
        ("dock_map", self._map_panel, False),  # SHELL / yeni
    ]
)
```

`panel_ids.DOCK_SHORT_LABELS` ve `ED_PANEL_NAMES` / `ET_PANEL_NAMES` güncelleyin.
`FeaturePanelHost` sekme şeridini otomatik üretir.

### 3. Kısa etiketi kaydedin

```python
# sdr_console/ui/panel_ids.py → DOCK_SHORT_LABELS
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
