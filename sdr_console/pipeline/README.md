# Pipeline — Data / Buffer / IPC

HAL'den gelen ham veriyi DSP'ye taşır, işlenmiş çıktıyı viz ve audio
katmanlarına iletir.

**Sorumluluklar:**
- `SampleQueue` — sınırlı, drop-oldest thread-safe kuyruk
- `AcquisitionWorker` — cihazdan ham IQ okuma (ayrı thread) ve blokları
  kayıtlı tüm tüketici kuyruklarına dağıtma (fan-out)
- `ProcessingWorker` — IQ -> DSP -> `SpectrumFrame` (ayrı thread)
- `DemodWorker` — IQ -> kanal filtresi -> demodülatör -> ses kuyruğu
  (ayrı thread)
- `AudioChain` — demod worker + ses kuyruğu + sink'i tek başlatılabilir birim
  haline getirir
- `Pipeline` — görüntüleme worker'larını başlatma / durdurma,
  `add_raw_consumer()` ile ikinci zincire aynı IQ'yu verme

**İki paralel zincir:** Görüntüleme ve dinleme aynı ham IQ'yu ayrı
kuyruklardan okur; biri geri kalırsa diğerini bekletmez. Bloklar kopyalanmadan
paylaşılır, bu yüzden tüketiciler bloğu **değiştirmemelidir**.

**Bağımlılık yönü:** pipeline → hal, dsp, demod, audio

**Not:** Şimdilik `threading` kullanılıyor; FFT yükü arttığında
performans ölçümü sonrası `multiprocessing`'e geçilebilir.
