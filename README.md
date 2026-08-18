# SDR Console

Kişisel kullanım için gerçek zamanlı bir **SDR konsolu**. Birden fazla kaynaktan (şimdilik mock IQ ve ADALM-Pluto) gelen karmaşık IQ örneklerini işler; spektrum / waterfall çizer, dinleme kanalını demodüle eder, spektrumdaki sinyalleri tespit eder, bir bant aralığını tarar ve (güvenlik sınırlı) OOK yakalama / replay yapabilir.

GUI thread’i asla FFT veya donanım I/O yapmaz. Ham IQ, spektrum, ses ve tespit ayrı worker thread’lerde ilerler; kuyruklar dolunca en eski blok düşer, böylece bir zincir geride kalsa bile diğerleri çalışmaya devam eder.

## Özellikler

- **Spektrum + waterfall** — mutlak frekans ekseni, ortak x-ekseni, dinleme kanalını gösteren yarı saydam kutu
- **Alıcı kontrolleri** — merkez frekans, VFO (dinleme), kazanç / gain mode, örnekleme hızı, FFT boyutu, RFBW
- **Demodülasyon** — AM, N-FM, W-FM, USB, LSB, CW
- **Ses zinciri** — AFBW, AGC (fast / slow / hang / limiter), squelch, FM de-emphasis, volume
- **Otomatik tespit** — eşik üstü tepeler, birleştirme, ardışık kare onayı, istasyon adı eşlemesi
- **Tarama** — tek tur veya ileri-geri döngü; adım en az görünür bant genişliğinin yarısı
- **TX / Replay** — OOK yakalama, darbe / bit çözümü, kayan kod uyarısı, onaylı yayın (süre ve attenuation sınırı)
- **Kalıcılık** — son oturum ayarları ve pencere yerleşimi `~/.sdr-console/` altında

## Gereksinimler

- Python **3.11+**
- Temel paketler: `numpy`, `scipy`, `PyQt6`, `pyqtgraph`
- Opsiyonel:
  - ADALM-Pluto: Analog Devices **libiio** sürücüleri + `pyadi-iio`
  - Ses çıkışı: `sounddevice` (PortAudio)

## Hızlı başlangıç

```bash
pip install -e ".[dev]"
pytest
python -m sdr_console
# veya: python -m sdr_console --log-level=DEBUG
```

Kurulum sonrası konsol açılır. **Start** mock IQ akışını başlatır, **Stop** durdurur. Donanım olmadan spektrum ve waterfall’ı denemek için **Mock Device** yeterlidir.

Ses duymak için:

```bash
pip install -e ".[audio]"
```

**Audio → Enable** işaretleyin, spektrumdaki kutuyu taşıyıcıya hizalayın. Donanımsız dinleme için **Mock Device (AM test, +50 kHz)** seçin: merkezin 50 kHz üstünde 1 kHz AM tonu üretir. Kutuyu o taşıyıcıya kaydırıp kazancı yükseltin.

## Donanım

Cihaz listesi HAL kayıt defterinden (`sdr_console/hal/registry.py`) gelir. Kurulu olmayan veya henüz yayın yolu tamamlanmamış sürücüler listede görünür ama seçilemez.

| Cihaz | Durum | Not |
|-------|--------|-----|
| Mock Device | Kullanıma hazır | Bant içi mutlak RF tonlar + AWGN |
| Mock Device (AM test, +50 kHz) | Kullanıma hazır | Dinleme zincirini donanımsız doğrulamak için |
| ADALM-Pluto | Kullanıma hazır (opsiyonel extra) | `pyadi-iio`, USB veya Ethernet URI |
| RTL-SDR | İskelet | `pyrtlsdr` yoksa / streaming henüz yok |
| HackRF One | İskelet | Binding yoksa / streaming henüz yok |

Test ve senaryo için HAL ayrıca `FileIQDevice` (`.npy` IQ döngüsü) ve sweep / burst / noise-only mock senaryoları sunar; bunlar GUI listesinde değil, testlerden kullanılır.

### ADALM-Pluto

1. Windows’ta [libiio / Pluto USB sürücülerini](https://github.com/analogdevicesinc/libiio/releases) (veya Analog Devices PlutoSDR kurucusunu) yükleyin.
2. Python bağını kurun:

```bash
pip install -e ".[pluto]"
```

3. Konsolu açın, **ADALM-Pluto** seçin. URI boş bırakılırsa otomatik arama yapılır; gerekirse `ip:192.168.2.1` veya `usb:` yazın. **Scan** ile bağlı cihazları tarayabilirsiniz. **Start**.

GUI olmadan kısa bir duman testi:

```bash
python scripts/probe_pluto.py
python scripts/probe_pluto.py --uri ip:192.168.2.1
```

Pluto USB 2.0’dır. Düşmesiz sürekli akış genelde **5–6 Msps** civarında güvenilirdir; daha yüksek hızlarda durum çubuğunda drop görülebilir. Yüksek örnekleme hızında daha büyük FFT ve `rx_buffer_size` (varsayılan 16384) tercih edin.

Pluto frekans aralığı statik olarak 70 MHz–6 GHz, kazanç −3…71 dB, kazanç kipleri `manual` / `slow_attack` / `fast_attack` / `hybrid`. Bağlandıktan sonra gerçek sınırlar donanımdan okunur.

## Arayüz

Pencere üç bölgeden oluşur:

1. **Üst şerit** — cihaz, URI, Scan / Start / Stop
2. **Sol sütun** (sabit) — Receiver, Audio, Display; her grup daraltılabilir
3. **Merkez** — spektrum (üstte) + waterfall (altta), ortak frekans ekseni
4. **En sol hover şerit** — üzerine gelince **Tespit / Tarama / TX** kutuları açılır
5. **Sağ sütun** — işaretlenen paneller dikey splitter ile aynı anda görünür; hiçbiri açık değilse spektrum genişler

Spektrum veya waterfall’a sol tıklamak VFO’yu o frekansa taşır. Dinleme kutusunu sürüklemek de aynı işi yapar. Kutu genişliği **RFBW** ile değişir.

Oturum kapanırken dock / toolbar yerleşimi kaydedilir; sonraki açılışta geri yüklenir. Eski yüzer-dock kayıtları yok sayılır.

### Receiver

| Kontrol | Anlamı |
|---------|--------|
| Center frequency | Cihazın RF merkez frekansı (tüm spektrum kayar) |
| Listen (VFO) | Dinleme kanalının merkezi; cihaz merkezini değiştirmez |
| Gain / Gain mode | RF kazancı ve cihazın kazanç kipi |
| Sample rate | Görünür bant genişliğini belirler |
| FFT size | 512 / 1024 / 2048 / 4096 |
| RFBW | Kanal filtresinin RF bant genişliği; mod değişince varsayılan dolar |

Frekans ve kazanç adımları ayrı seçilir (ör. 100 kHz, 1 dB).

### Audio

| Kontrol | Anlamı |
|---------|--------|
| Enable | Ses kartına çıkış (`sounddevice` yoksa kutu pasif kalır) |
| Mode | AM, N-FM, W-FM, USB, LSB, CW |
| De-emp | FM de-emphasis: 75 µs (US) veya 50 µs (EU). W-FM’de her zaman açık; N-FM’de isteğe bağlı |
| AFBW | Demodülasyon sonrası ses alçak geçiren kesim |
| AGC | Otomatik seviye: fast, slow, hang, limiter |
| SQL | Kanal gücü eşiğin altındayken sesi kapatır (dBFS, varsayılan histerezis 3 dB) |
| Volume | 0–100 % |

Ses örnekleme hızı cihaz hızından türetilir (ör. 2.048 Msps → ~48.8 kHz). Uygulama kesirli yeniden örnekleme yapmaz; gerekirse işletim sistemi karıştırıcısı halleder. Bant genişliği değişince ses akışının yeniden açılması gerekmez.

## Demodülasyon

Dinleme zinciri görüntüleme zincirinden **bağımsız** çalışır. Aynı ham IQ bloğu kopyalanmadan iki kuyruğa dağılır; waterfall gecikse bile ses kesilmez.

Akış: IQ → VFO kaydırma → RF kanal filtresi + decimation → squelch → demodülatör → AFBW → (FM de-emphasis) → AGC → ses kartı.

| Mod | Varsayılan RFBW | Varsayılan AFBW | AGC | Yöntem |
|-----|-----------------|-----------------|-----|--------|
| AM | 10 kHz | 4 kHz | slow | Zarf (`\|IQ\|`) |
| N-FM | 12.5 kHz | 4 kHz | limiter | Faz ayırıcı, ±5 kHz sapma |
| W-FM | 200 kHz | 15 kHz | limiter | Faz ayırıcı, ±75 kHz sapma, de-emphasis açık |
| USB / LSB | 2.7 kHz | 3 kHz | hang | `real` / `-imag` |
| CW | 500 Hz | 1 kHz | fast | 750 Hz BFO ürün dedektörü |

Yeni bir mod eklemek için `Demodulator` alt sınıfı + `factory.py` kaydı yeterlidir; mevcut modlara dokunulmaz.

## Tespit

Sağdaki **Tespit** paneli (veya hover şeritteki kutu) spektrum kareleri üzerinde eşik üstü tepeleri arar. İş, görüntülemeden ayrı bir `DetectionWorker` thread’inde yürür; panel kapalıyken ağır iş atlanır, thread yeniden başlatılmaz.

- Eşik dBFS cinsindendir (varsayılan −40 dB).
- Yakın tepeler birleştirilir; birleştirme mesafesi moda göre önerilir (ör. W-FM 200 kHz, AM 50 kHz).
- Bir frekans **üç ardışık karede** görünmeden onaylanmaz.
- Onaylanan kayıtlar sinyal kaybolsa bile listede kalır; silmek için satır seçip kaldırın veya tümünü temizleyin.
- Tablodaki frekansa tıklamak VFO’yu o noktaya taşır.

İstasyon adları `~/.sdr-console/stations.json` dosyasından okunur (±5 kHz eşleşme). Örnek biçimler:

```json
{
  "97000000": "TRT FM",
  "stations": [
    { "frequency_mhz": 101.5, "name": "Power FM" }
  ]
}
```

## Tarama

**Tarama** paneli alıcı merkezini bir aralıkta adım adım gezdirir, her adımda spektrumun oturmasını bekler ve tespit motorunu kullanır.

- **Tek tur:** başlangıç → bitiş, sonra durur.
- **Sürekli (ileri-geri):** durdurulana kadar gider-gelir.
- Adım en az `örnekleme_hızı / 2` olmalıdır (görünür bantla örtüşme). İstenen aralık tek FFT karesine sığıyorsa adım atılmaz; orta nokta kullanılır.

Tarama sırasında normal Start/Stop ve VFO kullanımı panel durumuna göre kilitlenir; **Stop** taramayı da keser.

## TX / Replay

**TX / Replay** paneli kısa OOK yakalamalarını çözer ve (onay sonrası) yeniden yayınlar. Varsayılan hedef **433.92 MHz** ISM bandıdır.

Akış:

1. **Yakala** — RX IQ birikir, zarf + eşik ile darbeler çıkarılır, bit dizisi üretilir.
2. Özet gösterilir (darbe sayısı, bitler). Birden fazla yakalama kayan kod açısından değerlendirilir.
3. **Yayın** — kullanıcı onayı olmadan gitmez. Süre dolunca TX otomatik durur (varsayılan üst sınır 5 s, sonsuz TX yok).
4. Attenuation en az **40 dB** (`tx_hardwaregain ≤ −40 dB`); varsayılan 50 dB. Daha güçlü yayın reddedilir.

TX donanımı: `MockTXDevice` (test) ve `PlutoTXDevice` (Pluto). Replay, HAL RX sürücüsünden ayrı bir `TXCapableDevice` sözleşmesi üzerindendir.

Yalnızca yasal olduğunuz bantlarda, kendi cihazlarınızla ve yerel mevzuata uygun kullanın.

## Mimari

Katmanlar tek yönlüdür: üstteki alttakini çağırır, tersi olmaz. UI numpy FFT çağırmaz; DSP Qt bilmez; HAL dışında hiçbir katman donanıma dokunmaz.

```text
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  HAL        │ IQ  │  Pipeline    │ FFT │  Viz / UI   │
│  cihaz,     │────►│  kuyruklar,  │────►│  spektrum,  │
│  mock, file │     │  worker’lar  │     │  waterfall  │
└─────────────┘     │              │     └─────────────┘
                    │              │     ┌─────────────┐
                    │              │ IF  │  Demod      │
                    │              │────►│  AM/FM/SSB  │──► Audio
                    │              │     └─────────────┘
                    │              │     ┌─────────────┐
                    │              │ dB  │  Detect     │
                    │              │────►│  Scan / TX  │
                    └──────────────┘     └─────────────┘
```

| Katman | Klasör | Sorumluluk |
|--------|--------|------------|
| HAL | `sdr_console/hal/` | Cihaz bağlantısı, capability, ham `complex64` IQ |
| DSP | `sdr_console/dsp/` | FFT, eksen, kanalizer, AFBW, AGC, squelch, de-emphasis — saf numpy/scipy |
| Demod | `sdr_console/demod/` | Bant-temeli kanal → mono ses |
| Audio | `sdr_console/audio/` | Ses kartına pull-model çıkış (`sounddevice`) |
| Pipeline | `sdr_console/pipeline/` | Thread-safe kuyruklar, acquisition / processing / demod / detection worker |
| Detect | `sdr_console/detect/` | Tepe bulma, birleştirme, tracker, istasyon veritabanı |
| Scan | `sdr_console/scan/` | Bant tarama orkestrasyonu |
| TX | `sdr_console/tx/` | OOK decode / encode, replay oturumu, Pluto/mock TX |
| Viz | `sdr_console/viz/` | pyqtgraph spektrum ve waterfall; işlem yapmaz |
| UI | `sdr_console/ui/` | Ana pencere, paneller, Start/Stop |
| Config | `sdr_console/config/` | Varsayılanlar ve JSON kalıcılık |

Her katmanın kendi `README.md` dosyası sorumluluk sınırlarını anlatır.

### Pipeline thread’leri

| Worker | Girdi | Çıktı |
|--------|-------|-------|
| `AcquisitionWorker` | Cihaz `read()` | Ham IQ kuyrukları (fan-out, kopyasız) |
| `ProcessingWorker` | Ham IQ | `SpectrumFrame` (dBFS satır + metadata) |
| `DemodWorker` | Ham IQ | Ses blokları |
| `DetectionWorker` | `SpectrumFrame` | Onaylı tespit listesi |

Kuyruklar sınırlı ve **drop-oldest**. Tüketiciler paylaşılan IQ bloğunu değiştirmemelidir.

## Yapılandırma

Ayarlar `~/.sdr-console/config.json` dosyasına yazılır (sürüm 5). Kayıtlı alanlar arasında cihaz, URI, merkez / VFO, kazanç, örnekleme, FFT, RFBW / AFBW, demod modu, AGC, squelch, de-emphasis, volume, görüntü colormap / vmin / vmax ve pencere yerleşimi vardır.

Bozuk veya eski dosyalar varsayılanlara düşer veya migrasyonla yükseltilir. İstasyon adları aynı dizindeki `stations.json` içindedir.

## Testler

Donanıma bağlı olmayan birim testleri mock IQ ve `tests/fixtures/` ile çalışır.

```bash
pytest -q
python -m tests.fixtures.generate   # IQ fixture’larını yeniden üretmek için
```

GUI testleri `pytest-qt` (PyQt6) kullanır. Pluto duman testi için `scripts/probe_pluto.py`.

## Geliştirme

```bash
pip install -e ".[dev]"
ruff check .
mypy sdr_console
pytest -q
```

Yeni bir SDR sürücüsü eklerken `SDRDeviceInterface` uygulayın ve `hal/registry.py` içine kaydedin; mevcut sürücüleri değiştirmeyin. Yeni bir UI paneli için `sdr_console/ui/README.md` içindeki kontrol listesine bakın.

## Lisans

MIT — ayrıntılar `LICENSE` dosyasında.
