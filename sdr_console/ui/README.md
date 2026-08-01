# UI — Control

Ana pencere, Start/Stop, cihaz seçimi, frekans/kazanç/sample rate kontrolleri.

**Sorumluluklar:**
- `MainWindow` — transport, tuning spinbox'ları, durum satırı
- `QTimer` — pipeline output queue'dan periyodik okuma (GUI thread'de yalnızca çizim)
- Cihaz seçimi (şimdilik yalnızca Mock Device)

**Bağımlılık yönü:** ui → viz, pipeline, hal, config (DSP'ye doğrudan erişim yasak)
