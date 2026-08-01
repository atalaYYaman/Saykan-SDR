# HAL — Hardware Abstraction Layer

Donanımla konuşan tek katman. Her SDR türü `SDRDeviceInterface` (ABC)
üzerinden implemente edilir.

**Sorumluluklar:**
- Cihaz bağlantısı / koparma
- `DeviceCapabilities` ile donanım sınırlarını bildirme (sürekli veya ayrık)
- Merkez frekans, örnekleme hızı, kazanç / gain mode ayarı
- Ham IQ örneklerini okuma (`complex64`, tam ölçek normalizasyonu)
- `MockSDRDevice` (mutlak RF tonlar + AWGN, bant dışı gizleme)
- `PlutoSDRDevice` (pyadi-iio, lazy import, capability probe)
- `RtlSdrDevice` / `HackRfDevice` iskelet sürücüler
- `FileIQDevice`, senaryolar (`sweep` / `burst` / `noise_only`)
- `discovery.scan_devices` (libiio context tarama)
- `registry.create_device` / `device_availability` cihaz fabrikası

**Bağımlılık yönü:** HAL dışında hiçbir katman donanıma erişmez.
