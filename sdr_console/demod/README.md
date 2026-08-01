# Demod — Demodulation

Bant-temeline indirilmiş kanal bloklarını mono sese çevirir. Donanım, kuyruk
ve Qt bilmez; kendisine blok verilir, ses döndürür.

**Sorumluluklar:**
- `Demodulator` (ABC) — ortak sözleşme: `MODE`, `DEFAULT_BANDWIDTH_HZ`,
  `input_rate_hz`, `audio_rate_hz`, `reset()`, `process(block) -> float32 audio`
- `AMDemodulator` — zarf dedektörü: `|IQ|` → DC (taşıyıcı) süzme → ses hızına
  decimation

**Durum yönetimi:** Demodülatörler bilinçli olarak durumludur (filtre/faz
durumu içeride tutulur), böylece ardışık bloklar tık sesi olmadan birleşir.
`reset()` frekans veya mod değişiminde çağrılır. Buna karşılık kullandıkları
DSP fonksiyonları saf kalır (`dsp/audio.py`, `dsp/channelizer.py`).

**Yeni mod ekleme:** Yeni bir dosya + `Demodulator` alt sınıfı yeterlidir; var
olan modlara dokunulmaz (Open/Closed).

**Bağımlılık yönü:** demod → dsp (numpy/scipy). HAL, pipeline, viz, ui'ye
bağımlılık **yok**.

**Not:** AM zinciri lineerdir, AGC yoktur — çıkış seviyesi RF seviyesini takip
eder, ses yüksekliği audio katmanındaki volume kontrolüyle ayarlanır.
