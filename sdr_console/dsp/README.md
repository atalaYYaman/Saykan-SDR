# DSP — Signal Processing

Saf sayısal işleme fonksiyonları. Sadece `numpy` ve `scipy` kullanır;
GUI ve donanımdan tamamen bağımsızdır.

**Sorumluluklar:**
- `apply_window`, `compute_fft`, `to_db` — saf işleme adımları
- `SpectrumFrame` — waterfall'a giden metadata'lı satır
- `compute_spectrum_frame` — uçtan uca IQ -> dB pipeline
- `axis.py` — bin <-> Hz dönüşümleri, bant kenarları (`frequency_axis_hz`,
  `freq_to_bin`, `band_edges_hz`, `clamp_freq_to_band`)
- `channel.py` — `ChannelSpec`: dinlenen bandın merkez frekansı + genişliği
- `channelizer.py` — kanalı ayıklama: `frequency_shift` (mixer),
  `design_channel_filter` (FIR alçak geçiren), `filter_and_decimate`,
  `plan_channelizer` (decimation + filtre birlikte) ve `channelize`

Kanalizasyon fonksiyonları saftır: bloklar arası süreklilik gerektiren her şey
(mixer fazı, FIR gecikme hattı, decimation fazı) `ChannelizerState` olarak
parametre gelir ve geri döner. Böylece worker thread kesintisiz akış
yapabilirken testler aynı sinyali tek seferde işleyip karşılaştırabilir.

`ChannelSpec` burada durur çünkü hem `viz` (overlay kutusu) hem de ileride
demodülasyon zinciri (filtre/decimation) aynı tanıma ihtiyaç duyar; `dsp`
ikisinin de zaten bağımlı olduğu en alt ortak katmandır.

**Bağımlılık yönü:** DSP yalnızca numpy/scipy'ye bağımlıdır.
