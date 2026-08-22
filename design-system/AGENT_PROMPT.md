# Agent prompt — SDR Console UI design system (pass 1)

Yeni bir Agent sohbetine **bu dosyanın “PROMPT” bölümünü** olduğu gibi yapıştır.
Bu turda `sdr_console/` altında kod yazılmaz. Çıktı: `design-system/MASTER.md`.

Kaynak: TEKNOFEST 2026 Elektronik Harp Şartnamesi v1.0 (14.02.2026), özellikle
Bölüm 5 (ED/ET görevleri), 5.3.1 (teknik kontrol / kullanıcı arayüzü), 7
(En İyi Kullanıcı Arayüz Yazılımı).

---

## Önceki düzeltmenin eksği

İlk sıkı prompt, olmayan özellikleri **çalışır widget** gibi çizdirmeyi doğru
kesti; ama şartname görevleri için **kalıcı yer / dock kimliği / durum token’ı**
ayırmayı da kesti. Sonuç: her yeni ED/ET yeteneğinde UI’yi yeniden kırmak.

Bu sürüm üç katmanı ayırır:

| Katman | Anlamı | Bu tur |
|--------|--------|--------|
| **NOW** | Repoda var; tema + yerleşim buna uygulanır | Tasarlanır, sonraki kod turunda doldurulur |
| **SHELL** | Şartname görevi; DSP/HAL henüz yok | Yer, `dock_*` id, boş/disabled hali, token — sahte canlı veri yok |
| **NEVER-NOW** | Bu turda ne çizilir ne token şişirilir | 3D waterfall, 6 paralel alıcı matrisi, glassmorphism, web |

SHELL ≠ sahte C2. Boş panel “Yön bulma — henüz bağlı değil” der; uydurma pusula
derecesi veya sahte GPS noktası göstermez.

---

## PROMPT

```text
UI/UX Pro Max skill'ini kullan (@.cursor/skills/ui-ux-pro-max/SKILL.md).
Önce tasarım sistemi üret. Bu turda sdr_console/ altında kod, QSS veya widget rewrite YAZMA.
Çıktıyı design-system/MASTER.md olarak kaydet. Bitince kısa özet ver.

Amaç: mevcut SDR konsolu Teknofest 2026 EH operatör arayüzüne taşımak —
şimdi çalışan yüzeyleri yerleştirmek VE şartname görevleri için yeniden
tasarım gerektirmeyecek SHELL (yer + id + boş hal + token) bırakmak.
SHELL panellerine sahte canlı veri, sahte JSR, sahte koordinat KOYMA.

## Ürün

Saykan-SDR: Python masaüstü SDR konsolu. Görsel dil: koyu, yoğun, ED/ET
operatör konsolu (şartname §5 + “En İyi Kullanıcı Arayüz Yazılımı”).
Hazır ticari SDR GUI kopyası değil; mevcut katmanlı motorun yüzeyi.

Şartname görevleri UI’de iki sütun gibi okunur: ED (bilgi) sol/sağ-üst,
ET (etki, tehlikeli) ayrı ve onaylı. Büyük ödül için her iki görev de gerekir;
ödül sıralaması minimumu: Tespit + Parametre + DF ve Karıştırma’dan bir +
Aldatma’dan bir. Yerleşim bunu unutmasın (DF ve EA yuvaları görünür/keşfedilir).

## NOW — var, yerleştir

- Üst: cihaz, URI, cihaz-Scan, Start, Stop
- Sol: Receiver (center, VFO, gain, gain mode, sample rate, FFT, RFBW)
- Sol: Audio / dinleme (enable, AM/N-FM/W-FM/USB/LSB/CW, de-emp, AFBW, AGC, SQL, volume)
  → şartname 5.1.3 analog izleme/dinleme (sayısal telsiz ileride, aynı panel)
- Sol: Display (vmin/vmax, colormap)
- Merkez: pyqtgraph spektrum + waterfall, tıkla-VFO, dinleme kutusu
  → 5.1.1 tespit görseli + teknik kontrol “ED arayüzde spektrum”
- Sağ: Tespit (5.1.1), Tarama, TX/Replay (OOK yakala/onaylı kısa yayın)
- Alt: Idle/Running, cihaz, Msps, drop, VFO

TX/Replay NOW: onay, attenuation ≥ 40 dB, max ~5 s, sonsuz TX yok.
Bu, 5.2.3 aldatma/replay’in tohumudur; “jam istasyonu” değildir.
Space/tek tıkla yayın YASAK. ET SHELL’leri de aynı onay modelini kullanır.

## SHELL — yer ayır, doldurma (şartname §5)

Her SHELL için MASTER.md’de: dock objectName, varsayılan bölge, collapsed
boş hali (tek satır açıklama + Disabled), hangi NOW sinyaline ileride bağlanacağı.
Sahte metrik / rastgele tablo satırı / çalışan pusula çizme.

ED (5.1) — bilgi; spektrumu boğmasın:
- dock_detection (NOW): sütun SHELL’leri şimdiden ayır, veri yoksa kolon gizlenir
  veya “—”. Hedef kolonlar 5.1.2: frekans, BW, güç, analog/sayısal, mod (tercihen),
  protokol, çoklama (TDMA/FDMA/CDMA/OFDM), EKKT (FHSS/DSSS), güven, TOA.
  Aksiyon yuvaları: Dinle (NOW VFO), Locate (SHELL→DF), Assign ET (SHELL).
- dock_df (5.1.4): genlik / faz / TDOA yöntem seçimi yeri; bearing readout yeri;
  spektrumda LOB overlay yuvası. RMS derece alanı. Boş: “DF bağlı değil”.
- dock_geoloc (5.1.5): mini harita yuvası, belirsizlik elipsi yuvası, yer/hava
  hedef notu. TDOA/FDOA birleştirme ileride. Boş: “Konum kaynağı yok”.
- Parametre readout: Tespit satırı seçilince sağ veya alt inspector SHELL
  (dock_params). NOW’da VFO + BW yeter; ekstra alanlar boş.

ET (5.2) — ayrı tehlikeli bölge; ED’den görsel olarak ayrıl (kırmızı token yalnızca burada + Stop):
- dock_tx (NOW Replay) ET host içinde sekme/bölüm olarak kalsın; yanına:
  - Karıştırma (`dock_ea_jam`) baraj NOW-tohumu: bant gürültüsü, onay +
    yetkili pencere, att ≥ 10 dB, süre ≤ 15 s. Tekli/çoklu/look-through SHELL.
  - Analog aldatma (5.2.3): Replay/NOW ile akraba; ses/dalga şekli yuvası.
  - GNSS aldatma (5.2.4): en az GPS L1 geçer; L2/L5, GLONASS, Galileo, BDS ilave.
    Servis checkbox SHELL. Karıştırma ile birlikte/sonra/bağımsız notu.
- Güvenlik SHELL (tüm ET): onay diyaloğu, süre tavanı, attenuation/ERP, “yalnızca
  yetkili test penceresi”. JSR metre yuvası (değer yokken boş). Sahte dolu metre yok.

Üst bar SHELL (uydurma canlı rozet yok; yer + boş ikon):
- ED alt sistem: Online yalnızca RX gerçekten çalışıyorsa (NOW).
- ET alt sistem: Standby / Armed (onay) / Active — Active ancak gerçek TX iken.
- Görev saati (lokal veya UTC, milisaniye şart değil). GNSS kilit rozeti SHELL:
  veri yoksa “GNSS —”.

Spektrum overlay yuvaları (çizim motoru aynı pyqtgraph; yeni 3D yok):
- Tespit kutuları (NOW’a yakın)
- DF bearing çizgisi (SHELL)
- ET/karıştırma bölgesi (SHELL, kırmızı, yalnızca ET aktifken)
- VFO/dinleme kutusu (NOW)

Açıkça bu turda YOK (SHELL bile değil): 3D waterfall, 6’lı alıcı matrisi,
glassmorphism, web/QML, dokunmatik 44px zorunluluğu, 60 fps zorunluluğu,
pil/PSU/termik widget’ları (ileride status’a tek satır eklenebilir; şimdi yuva yeter).

## Yığın kilidi (.cursorrules)

- Python 3.11+, PyQt6 widget + QPalette/QSS, pyqtgraph
- QML, PySide6, HTML/React/Tailwind, Avalonia, backdrop-blur YASAK
- HAL/DSP/pipeline/demod bu turda değişmez
- Yeni yetenek gelince: önce katman (hal/dsp/detect/tx), sonra reserved dock’u doldur.
  UI numpy FFT çağırmaz.
- Skill HTML+Tailwind üretirse Qt token’ına çevir; uygulama iskeleti yazma.

Ürün tipi (skill): developer tool / dense dark dashboard / mission-critical
desktop console. Landing/hero/CTA yok. Pattern: docking IDE + operatör konsolu.

## Görsel yön

Renk (skill ile doğrula, metin WCAG AA):
- Zemin #0F172A, panel #1E293B
- ED aktif / dinleme / işaret: #06B6D4
- Tespit / uyarı: #F59E0B
- ET / Stop / onaylı yayın: #EF4444
- Metin #F1F5F9 / #94A3B8, ızgara #334155
- Heatmap: pyqtgraph colormap notu (mavi→kırmızı); yeni shader yok

Tipografi: UI Inter veya sistem; frekans/parametre monospace.
Yoğunluk: spektrum kahraman. Cam efekt yok. Radius 2–4 px. Paneller opak.
Koyu tema tek.

Durum token’ları (şimdi map + SHELL isim):
NOW: Idle, Connecting, Running/RX, Detection, Scan, TX armed, TX on
SHELL isim (renk ayır, sahte geçiş çizme): DF lock, Geoloc fix, EA look-through,
EA jam active, Deceive analog, GNSS spoof — hepsi gerçek backend gelene kadar Idle
ile aynı “kullanılamaz” görselinde kalabilir.

## Bilgi mimarisi (1920×1080; 1366×768’de dock collapse)

1. Üst QToolBar: transport NOW + ED/ET durum yuvaları SHELL (boş gizlenebilir).
2. Sol dock: Receiver + Audio + Display. VFO büyük MHz, mod, kazanç, RFBW önde.
   FFT / gain mode / de-emp gelişmiş.
3. Merkez: spektrum + waterfall + overlay yuvaları.
4. Sağ FeaturePanelHost (hover drawer kalkacak — sonraki kod): görünür sekmeler
   NOW: Tespit, Tarama, TX/Replay
   SHELL (sekme var, içerik empty-state): DF, Konum, Parametre, ET-Karıştırma
   (TX host’u ET altında toplayabilirsin; id’ler sabit kalsın).
   Hiçbiri açık değilse spektrum genişler.
5. Alt status: NOW metin + SHELL slot’lar (GNSS —, ET penceresi kilitli).

Sabit id’ler (kod turunda objectName; MASTER.md’de aynen yaz):
dock_detection, dock_scan, dock_tx, dock_df, dock_geoloc, dock_params,
dock_ea_jam, dock_ea_deceive, dock_ea_gnss.
İleride panel eklemek = host listesine widget; yerleşim şeması değişmez.

Etkileşim:
- Sol tık spektrum/waterfall / tespit satırı = VFO (NOW)
- Sağ tık menü YUVALARI: Dinle, DF, ET ata, Kaydet — disabled if SHELL
- Sürükle-bırak Tespit → ET hedef listesi: SHELL, görsel kuralı yaz, kod yok
- ET asla tek tık/Space; onay + süre + attenuation
- Renk tek başına anlam değil (ikon + metin)
- Teknik kontrol (5.3.1): ED spektrumu operatörün gördüğü merkez; ET çıkış
  aynı UI’den start/stop — bu iki yüzey gizlenemez

## Deliverable (yalnızca bu tur)

design-system/MASTER.md:
1. Skill design-system + PyQt çeviri
2. Token’lar (renk, tip, spacing, radius, durum, ED vs ET)
3. 5 bölgeli yerleşim + overlay yuvaları
4. NOW bileşen kuralları: toolbar, dock, Start/Stop, tespit tablosu, slider,
   spinbox, status, TX onay
5. SHELL katalogu: her dock_* için bölge, empty-state metni, yasak (sahte veri)
6. Spektrum/waterfall krom + overlay katman sırası
7. Anti-pattern: landing, glass, ham-radyo, sahte C2 metrikleri, onaysız ET,
   spektrumu chrome ile boğmak, SHELL’i NOW gibi doldurmak
8. Sonraki kod turları (yapma, sırala):
   (A) QSS (B) QToolBar (C) sol dock + sağ host; SHELL sekmeler empty-state
   (D) pyqtgraph paleti (E) tespit kolon şeması rezervi
   DSP/HAL/DF/jammer bu prompt’ta YOK

Windows: python .cursor/skills/ui-ux-pro-max/scripts/search.py
"dark developer tool IDE dashboard electronic warfare console" --design-system -p "SDR Console"
--stack html-tailwind uygulama koduna çevrilmez; Qt token notu yaz.
```
