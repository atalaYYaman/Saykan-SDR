# Saykan-SDR — Tasarım Sistemi (MASTER)

> **Kaynak:** UI/UX Pro Max (`--design-system`, density 9/10) + design-system skill (3 katman token) + PyQt6/QSS çevirisi  
> **Ürün:** Teknofest 2026 Elektronik Harp operatör konsolu — Python masaüstü, PyQt6 + pyqtgraph  
> **Bu belge:** Kod turu öncesi tek doğruluk kaynağı. `sdr_console/` altında uygulama bu turda **yapılmaz**.

---

## 0. Üç katman modeli (NOW / SHELL / NEVER-NOW)

| Katman | Anlam | Bu belgede |
|--------|-------|------------|
| **NOW** | Repoda var; tema + yerleşim uygulanır | Bileşen kuralları, gerçek sinyal bağlantıları |
| **SHELL** | Şartname görevi; backend henüz yok | `dock_*` id, bölge, empty-state, yasaklar — **sahte veri yok** |
| **NEVER-NOW** | Bu sürümde ne çizilir ne token | 3D waterfall, 6'lı alıcı matrisi, glassmorphism, web/QML |

**Şartname okuma:** ED (5.1 bilgi) spektrumu boğmaz; ET (5.2 etki) görsel olarak ayrı, onaylı, kırmızı token yalnızca ET + Stop. Büyük ödül minimumu: Tespit + Parametre + DF **ve** (Karıştırma **veya** Aldatma) — DF ve EA yuvaları keşfedilebilir kalmalı.

---

## 1. Skill sentezi + PyQt çevirisi

### 1.1 UI/UX Pro Max sonuçları (doğrulandı)

| Alan | Skill önerisi | Saykan-SDR kararı |
|------|---------------|-------------------|
| Pattern | Dense dashboard / developer tool | **Kabul** — IDE benzeri docking + operatör konsolu; landing/hero/CTA **yok** |
| Style | Dark Mode (OLED), yüksek kontrast | **Kabul** — tek koyu tema |
| Density | 9/10 (8–32 px spacing) | **Kabul** — spektrum kahraman, paneller kompakt |
| Skill renkleri | `#0F172A` bg, `#1E293B` primary, `#EF4444` destructive | **Kabul** — aşağıdaki EH paleti ile hizalı |
| Skill tipografi | JetBrains Mono + IBM Plex Sans | **Uyarlandı:** UI gövde **Inter veya sistem**; frekans/parametre **monospace** (JetBrains Mono / Consolas / Cascadia Mono) |
| Skill accent | `#22C55E` run green | **Reddedildi** — Start/RX için `#06B6D4` (ED cyan); yeşil operatör anlamı karıştırır |
| Anti-pattern | Light mode default, yavaş performans | **Kabul** |

**Not:** Skill `--stack html-tailwind` çıktısı **uygulanmaz**. Aşağıdaki token tabloları doğrudan `QPalette`, `QSS` özellikleri ve `DisplaySettings` alanlarına map edilir.

### 1.2 design-system skill → PyQt token mimarisi

```
Primitive (ham hex/spacing px)
       ↓
Semantic (--color-ed-active, --space-panel)
       ↓
Component (--toolbar-btn-start-bg, --detection-row-selected-bg)
```

**PyQt uygulama sırası (kod turu):**
1. `QApplication` → Fusion stili + global QSS (`design-system` token dosyasından üretilir)
2. `QPalette` → `Window`, `Base`, `Text`, `Highlight`, `AlternateBase`
3. Bileşen QSS → `objectName` seçicileri (`#dock_tx`, `#transport_stop`)
4. pyqtgraph → `DisplaySettings` + plot pen/brush (viz katmanı; UI numpy çağırmaz)

---

## 2. Token'lar

### 2.1 Primitive — renk

| Token | Hex | Kullanım |
|-------|-----|----------|
| `--primitive-slate-950` | `#0F172A` | Ana zemin, spektrum çevresi |
| `--primitive-slate-800` | `#1E293B` | Panel, toolbar, dock başlık |
| `--primitive-slate-700` | `#334155` | Izgara, ayırıcı, input border |
| `--primitive-slate-600` | `#475569` | Disabled border, ikincil çizgi |
| `--primitive-slate-400` | `#94A3B8` | İkincil metin, placeholder |
| `--primitive-slate-100` | `#F1F5F9` | Birincil metin |
| `--primitive-cyan-500` | `#06B6D4` | ED aktif, dinleme, VFO, Start/RX |
| `--primitive-amber-500` | `#F59E0B` | Tespit, uyarı, scan vurgu |
| `--primitive-red-500` | `#EF4444` | ET, Stop, TX onaylı yayın |
| `--primitive-red-900` | `#7F1D1D` | ET panel zemin vurgusu (hafif tint) |
| `--primitive-cyan-900` | `#164E63` | ED panel vurgusu (hafif tint) |

**WCAG AA (koyu zemin):** `#F1F5F9` / `#0F172A` ≈ 15:1 ✓ · `#94A3B8` / `#1E293B` ≈ 5.8:1 ✓ · `#06B6D4` / `#0F172A` büyük metin/ikon ✓ · `#EF4444` / `#0F172A` uyarı metni ✓ — anlam **renk + ikon + metin** ile verilir.

### 2.2 Semantic — rol

| Token | Değer | Anlam |
|-------|-------|-------|
| `--color-bg-app` | `#0F172A` | Uygulama zemin |
| `--color-bg-panel` | `#1E293B` | Dock, grup kutusu, toolbar |
| `--color-bg-input` | `#0F172A` | Spinbox, combo içi |
| `--color-bg-elevated` | `#272F42` | Hover satır, sekme aktif |
| `--color-border-default` | `#334155` | Panel çerçeve |
| `--color-border-focus` | `#06B6D4` | Klavye odağı (2 px) |
| `--color-text-primary` | `#F1F5F9` | Başlık, değer |
| `--color-text-secondary` | `#94A3B8` | Etiket, birim |
| `--color-text-disabled` | `#64748B` | SHELL empty-state |
| `--color-ed-accent` | `#06B6D4` | ED alt sistem, dinleme, VFO |
| `--color-ed-surface` | `#164E63` @ 20% | ED bölge arka plan tint |
| `--color-detect-accent` | `#F59E0B` | Tespit satırı, tespit kutusu |
| `--color-et-accent` | `#EF4444` | ET alt sistem, TX, Stop |
| `--color-et-surface` | `#7F1D1D` @ 15% | ET host / sekme grubu zemin |
| `--color-grid` | `#334155` | pyqtgraph ızgara |
| `--color-success` | `#22C55E` | Yalnızca “başarılı kayıt” gibi nadir onay (ET değil) |

### 2.3 ED vs ET görsel ayrım

| Özellik | ED | ET |
|---------|----|----|
| Birincil vurgu | Cyan `#06B6D4` | Kırmızı `#EF4444` |
| Panel tint | `--color-ed-surface` | `--color-et-surface` |
| Host konumu | Sağ üst sekmeler (Tespit, DF, Konum, Parametre) | Sağ alt / ET host (TX, Karıştırma, Aldatma, GNSS) |
| Tehlike modeli | Bilgi; tek tık OK (VFO) | Onay + süre + attenuation; Space/tek tık **yasak** |
| Stop | — | Global Stop + ET stop; her ikisi `#EF4444` |

### 2.4 Tipografi

| Token | Font | Boyut | Ağırlık | Kullanım |
|-------|------|-------|---------|----------|
| `--font-ui` | Inter, Segoe UI, system-ui | 12 px | 400 | Etiket, buton, tablo |
| `--font-ui-semibold` | Inter, system-ui | 12 px | 600 | Grup başlığı, toolbar |
| `--font-mono` | JetBrains Mono, Consolas | 13 px | 500 | Frekans, BW, güç, TOA |
| `--font-mono-lg` | JetBrains Mono | 18 px | 600 | VFO büyük MHz (Receiver) |
| `--font-caption` | Inter | 11 px | 400 | Status, empty-state |
| `--font-section` | Inter | 13 px | 600 | Collapsible başlık |

**Satır yüksekliği:** UI 1.35 · mono 1.2 · tablo satırı min 22 px (dense).

### 2.5 Spacing (density 9 — 4 px taban)

| Token | px | Kullanım |
|-------|-----|----------|
| `--space-0` | 0 | — |
| `--space-1` | 4 | İkon-metin gap |
| `--space-2` | 8 | Form satırı dikey |
| `--space-3` | 12 | Panel iç padding |
| `--space-4` | 16 | Grup arası |
| `--space-5` | 20 | Toolbar yatay padding |
| `--space-6` | 24 | Ana bölge gutter (1920) |

**1366×768:** Sol dock collapse → yalnız Receiver + spektrum; sağ host 280 px min veya tamamen gizli.

### 2.6 Radius, gölge, opaklık

| Token | Değer | Not |
|-------|-------|-----|
| `--radius-sm` | 2 px | Input, chip |
| `--radius-md` | 4 px | Panel, buton |
| `--radius-none` | 0 | Spektrum kenarı — keskin |
| `--shadow-none` | — | Cam/gölge **yok**; paneller opak |
| `--opacity-disabled` | 0.45 | SHELL kontroller |
| `--opacity-overlay-detect` | 0.35 | Tespit kutusu fill |
| `--opacity-overlay-vfo` | 0.55 | Dinleme/VFO kutusu |

### 2.7 Durum token'ları

#### NOW (gerçek backend bağlanır)

| Durum | Renk | Metin örneği | Konum |
|-------|------|--------------|-------|
| `Idle` | `--color-text-secondary` | Idle | Status |
| `Connecting` | `--color-ed-accent` | Connecting… | Status + toolbar |
| `Running/RX` | `--color-ed-accent` | Running · {device} | Status + ED rozeti |
| `Detection` | `--color-detect-accent` | Detection active | Status |
| `Scan` | `--color-detect-accent` | Scan {pct}% | Status + scan panel |
| `TX armed` | `--color-et-accent` | TX armed | ET rozeti + TX panel |
| `TX on` | `--color-et-accent` + pulse border | TX ON · {s}s | Status + ET Active |

#### SHELL (backend yok — Idle görseli ile aynı “kullanılamaz”)

| Durum adı | Empty görünüm | Backend gelince |
|-----------|---------------|-----------------|
| `DF lock` | `--color-text-disabled` + “DF bağlı değil” | `dock_df` bearing |
| `Geoloc fix` | “Konum kaynağı yok” | `dock_geoloc` |
| `EA look-through` | Sekme disabled | `dock_ea_jam` look-through |
| `EA jam active` | — | `dock_ea_jam` |
| `Deceive analog` | — | `dock_ea_deceive` |
| `GNSS spoof` | “GNSS —” | `dock_ea_gnss` |

SHELL durumları **sahte geçiş animasyonu çizmez**; renk ayrımı token adında rezerve, görsel Idle ile aynı kalabilir.

---

## 3. Beş bölgeli yerleşim + overlay yuvaları

### 3.1 ASCII yerleşim (1920×1080)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [1] QToolBar — transport NOW + ED/ET/GNSS/mission clock SHELL slotları      │
├──────────┬──────────────────────────────────────────────────┬───────────────┤
│ [2] Sol  │ [3] Merkez — spektrum + waterfall + overlays     │ [4] Sağ       │
│ dock     │                                                  │ FeaturePanel  │
│ Receiver │  ┌─ Spectrum (180px @1080) ─────────────────┐   │ Host          │
│ Audio    │  └─ Waterfall (expand) ─────────────────────┘   │ ┌─ ED sekmeler│
│ Display  │                                                  │ │ Tespit NOW  │
│ (collapse│                                                  │ │ Tarama NOW  │
│  @768)   │                                                  │ │ DF SHELL    │
│          │                                                  │ │ Konum SHELL │
│          │                                                  │ │ Param SHELL │
│          │                                                  │ ├─ ET host ───│
│          │                                                  │ │ TX/Replay   │
│          │                                                  │ │ EA-Jam SHELL│
│          │                                                  │ │ EA-Dec SHELL│
│          │                                                  │ │ EA-GNSS SHELL│
├──────────┴──────────────────────────────────────────────────┴───────────────┤
│ [5] QStatusBar — Idle/Running, device, Msps, drop, VFO + SHELL slotlar      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Bölge kuralları

| # | Bölge | objectName (kök) | Min genişlik | Collapse |
|---|-------|------------------|--------------|----------|
| 1 | Üst toolbar | `toolbar_main` | 100% × 40 px | Asla |
| 2 | Sol dock | `dock_left_controls` | 320 px / scroll | 768'de yalnız Receiver veya gizle |
| 3 | Merkez display | `display_center` | Kalan alan | Hiçbir panel açık değilse max |
| 4 | Sağ host | `feature_host` | 300–440 px; 0 if hidden | Sekmeler kapalı → genişlik 0 |
| 5 | Alt status | `status_bar` | 100% × 24 px | Asla |

**Mevcut kod → hedef:** `HoverDrawer` kaldırılacak; panel seçimi görünür sekme çubuğu (`FeaturePanelHost` üstünde). Spektrum gizlenemez (teknik kontrol 5.3.1).

### 3.3 Spektrum overlay yuvaları (merkez)

| Katman | Z-order | NOW/SHELL | Görsel |
|--------|---------|-----------|--------|
| Waterfall buffer | 0 | NOW | Colormap mavi→kırmızı |
| Spectrum curve | 1 | NOW | `#F59E0B` veya `#06B6D4` (config) |
| Grid | — | NOW | `#334155` |
| VFO/dinleme kutusu | 2 | NOW | Cyan fill α55, merkez çizgi `#EF4444` |
| Tespit kutuları | 3 | NOW (yakın) | Amber kesik çerçeve |
| DF bearing LOB | 4 | SHELL | Cyan kesik radial; veri yokken çizilmez |
| ET/karıştırma bandı | 5 | SHELL | Kırmızı yarı saydam; yalnız ET Active |

---

## 4. NOW bileşen kuralları

### 4.1 Toolbar (`toolbar_main`)

| Kontrol | objectName | Stil | Davranış |
|---------|------------|------|----------|
| Cihaz combo | `transport_device` | `--color-bg-input` | Mock/Pluto/RTL/HackRF |
| URI | `transport_uri` | mono 12 px | Placeholder: `auto / ip:… / usb:` |
| Scan | `transport_scan` | secondary btn | HAL discovery → URI doldur |
| Start | `transport_start` | ED cyan filled | Connect + pipeline |
| Stop | `transport_stop` | ET red outline→filled | Global durdur |

**SHELL slotları (toolbar sağ):**
- `badge_ed_subsystem` — “ED: Offline \| Online” (Online yalnızca RX gerçek)
- `badge_et_subsystem` — “ET: Standby \| Armed \| Active”
- `badge_gnss` — “GNSS —” (veri yok)
- `label_mission_time` — lokal veya UTC; backend yokken `--`

### 4.2 Sol dock grupları

**Receiver** (`group_receiver`) — öncelik sırası: VFO büyük → mod → kazanç → RFBW → center → sample rate → FFT (gelişmiş).

**Audio** (`group_audio`) — 5.1.3 analog izleme: enable, AM/N-FM/W-FM/USB/LSB/CW, de-emp, AFBW, AGC, SQL, volume.

**Display** (`group_display`) — vmin, vmax, colormap combo (NOW'a taşınacak; şu an config-only).

**CollapsibleGroupBox:** başlık `--font-section`, border `--color-border-default`, radius `--radius-md`, **opak** arka plan.

### 4.3 Sağ host — NOW paneller

#### `dock_detection` — Sinyal Tespiti (5.1.1)

- Enable, eşik, merge distance (mevcut)
- Tablo kolonları:

| Kolon | NOW | SHELL kolon |
|-------|-----|-------------|
| Frekans (MHz) | ✓ | — |
| BW | kısmen | genişlet |
| Güç | ✓ | — |
| Gain | ✓ | — |
| Det count | ✓ | — |
| analog/sayısal | — | gizli veya “—” |
| Mod | — | “—” |
| Protokol | — | “—” |
| Çoklama | — | “—” |
| EKKT | — | “—” |
| Güven | — | “—” |
| TOA | — | “—” |

- Aksiyon yuvaları (satır/sağ tık): **Dinle** (NOW VFO), **Locate** (SHELL→DF, disabled), **Assign ET** (SHELL, disabled)
- Satır seçimi → `dock_params` inspector tetikler (NOW: VFO+BW)

#### `dock_scan` — Tarama

- Mevcut: start/end, step, mod, progress — amber vurgu scan sırasında

#### `dock_tx` — TX / Replay (NOW tohum, 5.2.3 yakın)

- ET host içinde ilk sekme
- Onay diyaloğu zorunlu; attenuation ≥ 40 dB; max ~5 s; sonsuz TX yok
- Space / tek tık TX **yasak**
- Waveform: mevcut noise/tone; Replay dosyası SHELL (`dock_ea_deceive`)

### 4.4 Ortak bileşenler

**Primary button (Start):** bg `#06B6D4`, text `#0F172A`, radius 4 px, min 72×28 px  
**Destructive (Stop, TX confirm):** bg `#EF4444`, text `#F1F5F9`  
**Secondary:** bg `#334155`, border `#475569`  
**Slider:** groove `#334155`, handle `#06B6D4`; ET bağlamında handle `#EF4444`  
**Spinbox/Combo:** bg `#0F172A`, border `#334155`, focus `#06B6D4`  
**Table:** zebra `#1E293B` / `#272F42`; seçili satır `#164E63` @ 40%  
**Status bar:** mono caption; bölümler ` · ` ile; drop sayısı amber eşik aşımında

### 4.5 TX onay diyaloğu (NOW + tüm ET SHELL)

```
┌─ RF Çıkış Onayı ─────────────────────┐
│ ⚠ ET modu — yalnızca yetkili test    │
│ Frekans: {f} MHz   BW: {bw} kHz       │
│ Süre: [≤ 5 s]  Attenuation: [≥ 40 dB]│
│ [ ] Yetkili test penceresi içindeyim  │
│ JSR: [──────── boş SHELL ────────]   │
│        [ İptal ]  [ Onayla ve Başlat ]│
└──────────────────────────────────────┘
```

JSR metre yuvası boş kalır; sahte dolu gösterge **yasak**.

---

## 5. SHELL katalogu

Her kayıt: `objectName`, bölge, empty-state, ileride bağlanacağı sinyal, **yasaklar**.

### 5.1 `dock_df` (5.1.4)

| Alan | Değer |
|------|-------|
| Bölge | Sağ host, ED sekmeleri — “Yön Bulma” |
| Empty-state | Tek satır: **“DF bağlı değil”** + tüm kontroller Disabled |
| UI yuvası | Yöntem seçimi (genlik/faz/TDOA) placeholder; bearing readout alanı; RMS° alanı |
| Overlay | Spektrum LOB çizgisi — veri yokken **çizilmez** |
| Bağlantı | `DetectionPanel` Locate; pipeline DF worker |
| **Yasak** | Sahte derece, dönen pusula, rastgele bearing |

### 5.2 `dock_geoloc` (5.1.5)

| Alan | Değer |
|------|-------|
| Bölge | Sağ host, ED — “Konum” |
| Empty-state | **“Konum kaynağı yok”** |
| UI yuvası | Mini harita frame; belirsizlik elipsi layer; yer/hava not alanı |
| Bağlantı | DF + TDOA/FDOA birleştirme (ileride) |
| **Yasak** | Sahte GPS pin, uydurma koordinat, canlı harita tile |

### 5.3 `dock_params` (5.1.2 inspector)

| Alan | Değer |
|------|-------|
| Bölge | Sağ host alt veya split inspector — “Parametre” |
| Empty-state | **“Tespit seçin”** |
| NOW alanları | VFO, BW (seçili satırdan) |
| SHELL alanları | Mod, protokol, çoklama, EKKT, güven, TOA — boş/“—” |
| **Yasak** | Sahte protokol tahmini, rastgele mod listesi |

### 5.4 `dock_ea_jam` (5.2.1 + 5.2.2)

| Alan | Değer |
|------|-------|
| Bölge | ET host — “Karıştırma” sekmesi |
| Empty-state | **“Karıştırma modülü bağlı değil”** |
| UI yuvası | Sürekli: tekli/çoklu/baraj tip seçimi; süre; start/stop; “Almaç gerekmez” notu |
| Look-through (5.2.2) | Alt bölüm: tespit↔jam zaman çizelgesi yuvası; mini spektrum; **komite penceresi kilidi** checkbox (disabled) |
| Bağlantı | `dock_detection` Assign ET; TX HAL |
| **Yasak** | Sahte jam spektrumu, “aktif jam” göstergesi backend olmadan |

### 5.5 `dock_ea_deceive` (5.2.3)

| Alan | Değer |
|------|-------|
| Bölge | ET host — “Analog Aldatma” |
| Empty-state | **“Aldatma modülü bağlı değil”** |
| UI yuvası | Ses/dalga şekli dosya yuvası; Replay ile paylaşılan parametre alanı |
| NOW ilişkisi | `dock_tx` Replay tohumu buraya genişler |
| **Yasak** | Sahte TX sayacı, otomatik oynatma |

### 5.6 `dock_ea_gnss` (5.2.4)

| Alan | Değer |
|------|-------|
| Bölge | ET host — “GNSS Aldatma” |
| Empty-state | **“GNSS aldatma bağlı değil”** |
| UI yuvası | Servis checkbox’ları: GPS L1 (min), L2/L5, GLONASS, Galileo, BDS — hepsi disabled |
| Not alanı | Karıştırma ile birlikte/sonra/bağımsız (statik metin) |
| **Yasak** | Sahte uydu sayısı, sahte SNR, “spoof active” rozeti |

### 5.7 Üst bar SHELL özet

| Slot | Empty | Dolu koşulu |
|------|-------|-------------|
| ED alt sistem | Offline | RX stream gerçek |
| ET alt sistem | Standby | Armed=onay verildi; Active=gerçek TX |
| GNSS rozeti | `GNSS —` | PVT fix backend |
| Görev saati | `--:--:--` | Opsiyonel GNSS/ sistem saati |

---

## 6. Spektrum / waterfall kromatografi + katman sırası

### 6.1 pyqtgraph palet (DisplaySettings hedef)

| Öğe | Token / değer |
|-----|---------------|
| Plot arka plan | `#0F172A` |
| Axis text | `#94A3B8` 11 px |
| Grid | `#334155`, alpha 0.6 |
| Spectrum pen | `#06B6D4` (varsayılan) veya `#F59E0B` (tespit vurgu modu) |
| Waterfall colormap | `viridis` veya `turbo` — mavi→kırmızı; **yeni shader yok** |
| vmin / vmax | Display panelinden; varsayılan −80 / 0 dBFS |
| Spectrum yüksekliği | 180 px @1080; min 120 px |
| Waterfall history | 200 satır (config) |
| Refresh | ~33 ms (mevcut pipeline) |

### 6.2 Katman çizim sırası (alttan üste)

1. Plot background + grid  
2. Waterfall `ImageItem`  
3. Spectrum curve  
4. ET jam band overlay (SHELL — yalnızca ET Active)  
5. Tespit kutuları (QGraphicsRect / BandOverlay benzeri)  
6. DF LOB lines (SHELL)  
7. VFO/dinleme BandOverlay (NOW — draggable)  
8. Crosshair / click feedback (1 frame)

### 6.3 Etkileşim

| Eylem | Sonuç |
|-------|-------|
| Sol tık spektrum/waterfall | VFO tune (`frequency_selected`) |
| Sol tık tespit satırı | VFO + params inspector |
| Sağ tık | Menü: Dinle ✓, DF (disabled), ET ata (disabled), Kaydet (disabled) |
| Sürükle tespit → ET listesi | SHELL — görsel: amber satır → kırmızı hedef listesi ghost; kod sonraki tur |
| Overlay sürükle | Kanal BW taşıma (mevcut `channel_moved`) |

---

## 7. Anti-pattern'ler

| Anti-pattern | Neden yasak | Bunun yerine |
|--------------|-------------|--------------|
| Landing page / hero / CTA | Operatör konsolu değil | Doğrudan spektrum |
| Glassmorphism / backdrop-blur | .cursorrules yasağı; okunaklılık | Opak `#1E293B` paneller |
| Ham radyo / SDR# klonu | Teknofest özgün UI | EH ED/ET ayrımı |
| Sahte C2 metrikleri | SHELL ≠ sahte canlı veri | Empty-state metni |
| Sahte JSR / GPS / bearing | Yanıltıcı operatör güveni | Boş yuva |
| Onaysız ET / Space TX | Güvenlik | Onay diyaloğu + süre tavanı |
| Spektrumu chrome ile boğma | 5.3.1 merkez spektrum | Min merkez alan; collapse |
| SHELL'i NOW gibi doldurma | Backend yokken yanlış UX | Disabled + tek satır |
| 3D waterfall / 6'lı matris | NEVER-NOW | — |
| Web/QML/React/Tailwind UI | Yığın kilidi | PyQt6 + QSS |
| Emoji ikon | Profesyonel konsol | SVG/Phosphor-style vektör |
| Renk tek başına anlam | Erişilebilirlik | İkon + metin + renk |
| Hover-only drawer | Keşfedilemez paneller | Görünür sekme çubuğu |
| `#22C55E` Start | ET/ED karışıklığı | Cyan Start, kırmızı Stop |

---

## 8. Sonraki kod turları (sıra — bu turda yapılmaz)

| Tur | Kapsam | Dosya / alan |
|-----|--------|--------------|
| **(A) QSS** | Global token QSS, `QPalette` map | `sdr_console/ui/theme/` (yeni) |
| **(B) QToolBar** | Transport + SHELL rozet slotları | `main_window.py` — `HoverDrawer` kaldır |
| **(C) Sol dock + sağ host** | Collapsible gruplar tema; SHELL sekmeler empty-state | `feature_host.py`, yeni `*_panel_shell.py` |
| **(D) pyqtgraph paleti** | `DisplaySettings` token hizalama | `viz/settings.py`, `spectrum_widget.py` |
| **(E) Tespit kolon şeması** | Gizli SHELL kolonlar rezerve | `detection_panel.py` |

**Bu turda YOK:** DSP, HAL, DF, jammer, geoloc backend, Replay dosya IO, gerçek JSR metre.

---

## 9. objectName kayıt defteri (sabit)

```
dock_detection    dock_scan         dock_tx
dock_df           dock_geoloc       dock_params
dock_ea_jam       dock_ea_deceive   dock_ea_gnss

toolbar_main      transport_device  transport_uri
transport_scan    transport_start   transport_stop
badge_ed_subsystem badge_et_subsystem badge_gnss
label_mission_time

dock_left_controls group_receiver group_audio group_display
display_center    feature_host      status_bar
group_et_host     (ET sekmeleri container)
```

Yeni panel = `feature_host` listesine widget ekle; **yerleşim şeması değişmez**.

---

## 10. PyQt QSS token örneği (referans — uygulama tur A)

```css
/* Semantic → QSS — üretimde design-system/tokens.qss olacak */
QWidget#feature_host {
  background-color: #1E293B;
  border-left: 1px solid #334155;
}
QPushButton#transport_start {
  background-color: #06B6D4;
  color: #0F172A;
  border-radius: 4px;
  min-height: 28px;
  padding: 0 12px;
}
QPushButton#transport_stop {
  background-color: transparent;
  color: #EF4444;
  border: 1px solid #EF4444;
  border-radius: 4px;
}
QWidget[shell="true"] {
  color: #64748B;
}
QWidget[shell="true"] QPushButton,
QWidget[shell="true"] QComboBox {
  opacity: 0.45;
}
/* Focus — UX skill: görünür halka */
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
  border: 2px solid #06B6D4;
}
```

---

*Belge sürümü: 1.0 · Oluşturulma: 2026-08-20 · Skill sorgusu: `dark developer tool IDE dashboard electronic warfare console` · Density: 9*
