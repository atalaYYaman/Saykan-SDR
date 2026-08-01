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

`ChannelSpec` burada durur çünkü hem `viz` (overlay kutusu) hem de ileride
demodülasyon zinciri (filtre/decimation) aynı tanıma ihtiyaç duyar; `dsp`
ikisinin de zaten bağımlı olduğu en alt ortak katmandır.

**Bağımlılık yönü:** DSP yalnızca numpy/scipy'ye bağımlıdır.
