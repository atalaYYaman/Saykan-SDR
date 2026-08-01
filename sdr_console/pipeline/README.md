# Pipeline — Data / Buffer / IPC

HAL'den gelen ham veriyi DSP'ye taşır, işlenmiş çıktıyı viz katmanına iletir.

**Sorumluluklar:**
- `SampleQueue` — sınırlı, drop-oldest thread-safe kuyruk
- `AcquisitionWorker` — cihazdan ham IQ okuma (ayrı thread)
- `ProcessingWorker` — IQ -> DSP -> `SpectrumFrame` (ayrı thread)
- `Pipeline` — iki worker'ı başlatma / durdurma

**Bağımlılık yönü:** pipeline → hal, dsp

**Not:** Şimdilik `threading` kullanılıyor; FFT yükü arttığında
performans ölçümü sonrası `multiprocessing`'e geçilebilir.
