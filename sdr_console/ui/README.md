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

**Bağımlılık yönü:** ui → viz, pipeline, hal, config, demod (factory). DSP'ye
doğrudan erişim yasak.
