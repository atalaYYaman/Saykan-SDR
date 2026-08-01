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
- `audio.py` — ses hızı primitifleri: `plan_demod_chain` (IQ -> IF -> ses iki
  aşamalı decimation planı), `plan_audio_decimation`, `design_dc_blocker`,
  `apply_iir`, `clip_audio`

Kanalizasyon fonksiyonları saftır: bloklar arası süreklilik gerektiren her şey
(mixer fazı, FIR gecikme hattı, decimation fazı) `ChannelizerState` olarak
parametre gelir ve geri döner. Böylece worker thread kesintisiz akış
yapabilirken testler aynı sinyali tek seferde işleyip karşılaştırabilir.

`ChannelSpec` burada durur çünkü hem `viz` (overlay kutusu) hem de demodülasyon
zinciri (filtre/decimation) aynı tanıma ihtiyaç duyar; `dsp` ikisinin de zaten
bağımlı olduğu en alt ortak katmandır.

`plan_demod_chain` toplam decimation'ı cihaz örnekleme hızından türetir ve
bant genişliğine göre iki aşamaya böler. Toplam, bol bölenli (7-smooth) bir
sayıya yuvarlanır — tam oran genelde asal çıkar (2.048 Msps / 48 kHz ≈ 43) ve
o zaman bölünecek bir şey kalmaz. Sonuç: ses hızı bant genişliğinden bağımsız
sabit kalır, kullanıcı bant genişliğini değiştirdiğinde ses akışı yeniden
açılmak zorunda kalmaz.

**Bağımlılık yönü:** DSP yalnızca numpy/scipy'ye bağımlıdır.
