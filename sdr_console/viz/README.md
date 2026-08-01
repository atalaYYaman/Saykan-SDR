# Viz — Visualization

`pyqtgraph` tabanlı waterfall ve spektrum widget'ları. Yalnızca hazır
(işlenmiş) veriyi çizer; DSP veya donanım işlemi yapmaz.

**Sorumluluklar:**
- `WaterfallWidget` — kaydırmalı 2-D waterfall (`ImageItem`); x = mutlak
  frekans (Hz), y = zaman, en yeni satır üstte
- `SpectrumWidget` — anlık tek satır spektrum, dBFS ekseni
- `SdrDisplayWidget` — queue drain + ikisini birlikte güncelleme, ortak x
  ekseni (`setXLink`) ve kanal overlay'i
- `BandOverlay` — dinlenen bandı gösteren yarı saydam kutu + merkez çizgisi
- `DisplaySettings` — colormap, vmin/vmax, refresh aralığı, eksen genişliği,
  overlay renkleri

Spektrum ve waterfall'ın grafik alanları birebir hizalı: sol eksen genişliği
`DisplaySettings.axis_label_width` ile ikisinde de sabitlenir, frekans tick
etiketleri yalnızca waterfall'ın altında çizilir.

Kullanıcı etkileşimi sadece **sinyal** olarak yukarı bildirilir; widget'lar
cihazı veya pipeline'ı hiç tanımaz:
- `frequency_selected(float)` — spektrum/waterfall üzerine sol tık
- `channel_moved(float)` — overlay kutusunun sürüklenmesi

**Bağımlılık yönü:** viz → pyqtgraph, dsp (`SpectrumFrame`, `ChannelSpec`,
`axis`), pipeline queue'sunu okur

**Henüz yok:** marker, cursor okuma, dBm kalibrasyonu.
