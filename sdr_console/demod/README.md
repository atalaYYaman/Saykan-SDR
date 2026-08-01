# Demod — Demodulation

Bant-temeline indirilmiş kanal bloklarını mono sese çevirir. Donanım, kuyruk
ve Qt bilmez; kendisine blok verilir, ses döndürür.

**Sorumluluklar:**
- `Demodulator` (ABC) — ortak sözleşme: `MODE`, `DEFAULT_BANDWIDTH_HZ`,
  `input_rate_hz`, `audio_rate_hz`, `reset()`, `process(block) -> float32 audio`
- `AMDemodulator` — zarf dedektörü: `|IQ|` → DC süzme → ses hızına decimation
- `NFMDemodulator` / `WFMDemodulator` — faz ayırıcı:
  `angle(x[n]*conj(x[n-1]))` → DC süzme → decimation (bant genişliği kanal
  filtresinde seçilir)
- `USBDemodulator` / `LSBDemodulator` — tek yan bant: `real(IQ)` veya
  `-imag(IQ)` → DC süzme → decimation
- `CWDemodulator` — BFO ürün dedektörü: sabit ofsetli osilatörle karıştırma →
  DC süzme → decimation (taşıyıcı sıfır frekansta iken BFO tonu duyulur)
- `factory.py` — mod etiketlerini sınıflara bağlar (`create_demodulator`,
  `demodulator_factory`, `default_bandwidth_hz`)

**Durum yönetimi:** Demodülatörler bilinçli olarak durumludur (filtre/faz
durumu içeride tutulur), böylece ardışık bloklar tık sesi olmadan birleşir.
`reset()` frekans veya mod değişiminde çağrılır.

**Yeni mod ekleme:** Yeni bir dosya + `Demodulator` alt sınıfı + `factory.py`
kaydı yeterlidir; var olan modlara dokunulmaz (Open/Closed).

**Bağımlılık yönü:** demod → dsp (numpy/scipy). HAL, pipeline, viz, ui'ye
bağımlılık **yok**.

**Not:** Zincirler lineerdir, AGC yoktur — çıkış seviyesi RF seviyesini takip
eder, ses yüksekliği audio katmanındaki volume kontrolüyle ayarlanır.
