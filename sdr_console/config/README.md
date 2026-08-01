# Config — Persistence

Uygulama ayarlarının varsayılanları ve JSON kalıcılığı.

**Sorumluluklar:**
- `AppDefaults` — kod içi sabit varsayılanlar
- `AppConfig` — oturumlar arası saklanan kullanıcı ayarları
- `load_config` / `save_config` — `~/.sdr-console/config.json`

**Saklanan alanlar:** cihaz id, merkez frekans, gain, sample rate, FFT boyutu,
display colormap/vmin/vmax ve ilgili görselleştirme ayarları.

**Bağımlılık yönü:** config bağımsız; ui ve diğer katmanlar config'i okur.
