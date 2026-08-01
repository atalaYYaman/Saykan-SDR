# Audio — Ses Çıkışı

Demodüle edilmiş sesi ses kartına verir. Sinyal işlemez, sadece kuyruktan
okuyup çalar (volume dışında).

**Sorumluluklar:**
- `AudioSink` (ABC) — `start()`, `stop()`, `sample_rate_hz`, `volume`,
  `underruns`
- `QueuePullSink` — kuyruktaki blokları ses kartının istediği sabit boyutlu
  çerçevelere çevirir; üretici yetişemezse sessizlikle doldurur ve `underruns`
  sayacını artırır
- `SoundDeviceAudioSink` — PortAudio/`sounddevice` ile gerçek çalma
- `NullAudioSink` — test ikizi; donanıma dokunmadan `pull(frames)` ile
  ses kartını taklit eder

**Pull modeli:** Ses kartının kendi saati akışı sürükler; bize "şu kadar örnek
ver" der. Bu yüzden sink push edilmez, kuyruktan çeker. Callback PortAudio
thread'inde çalışır: asla bloklamaz, asla exception sızdırmaz.

**Opsiyonel bağımlılık:** `sounddevice` `import` işlemi tembel yapılır; kurulu
değilse uygulama çalışmaya devam eder, sadece ses açılamaz
(`AudioUnavailableError`). Durum kontrolü: `sounddevice_available()`.

**Örnekleme hızı:** Akış, demodülatörün ürettiği hızda açılır (ör. 48761.9 Hz) —
bizim tarafta kesirli yeniden örnekleme yapılmaz, gerekiyorsa işletim sistemi
karıştırıcısı halleder.

**Bağımlılık yönü:** audio hiçbir katmana bağımlı **değil**. Kuyruğu
`AudioBlockSource` protokolü üzerinden görür (`try_get()` yeter), böylece
pipeline ↔ audio döngüsü oluşmaz; bağlantıyı `pipeline/audio_chain.py` kurar.
