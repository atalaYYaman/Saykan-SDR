"""TX güvenlik sınırları ve varsayılanlar."""

# Mutlak taban: hiçbir TX yolu (EA jam dahil) bundan güçlü olamaz.
# TX/Test varsayılanı aşağıda MIN_TX_ATTENUATION_DB ile 40 dB kalır.
ABSOLUTE_MIN_ATTENUATION_DB = 10.0

# tx_hardwaregain_chan0 bu değerden güçlü (daha pozitif) olamaz; örn. -30 dB reddedilir.
MAX_TX_GAIN_DB = -40.0

# Minimum zorunlu attenuation: gain <= MAX_TX_GAIN_DB  =>  attenuation >= abs(MAX_TX_GAIN_DB)
MIN_TX_ATTENUATION_DB = abs(MAX_TX_GAIN_DB)

# Kullanıcı tercihi: OTA öz-dinleme için güvenlik tabanında başla (daha zayıf = görünmez).
DEFAULT_TX_ATTENUATION_DB = 40.0

# max_duration_s None verildiğinde kullanılan süre sınırı (saniye).
# Burst süresi de bu tavanı aşamaz (güvenlik).
DEFAULT_MAX_TX_DURATION_S = 5.0

# pyadi-iio Pluto TX/RX örnek ölçeği (12-bit ADC tepe).
TX_FULL_SCALE = 2048.0

# Yayın yokken TX analog kazancı (neredeyse kapalı).
TX_MUTE_ATTENUATION_DB = 89.0

# AD9363 dahili dijital loopback: TX IQ doğrudan RX yoluna.
LOOPBACK_OFF = 0
LOOPBACK_DIGITAL = 1

# Test-sinyali varsayılanları (ISM).
DEFAULT_TX_FREQ_HZ = 433_970_000.0
DEFAULT_TX_BANDWIDTH_HZ = 25_000.0
DEFAULT_BURST_DURATION_S = 3.0
DEFAULT_TX_INTERVAL_S = 3.0

# AD9363 analog RF filtresi pratik alt sınır (Hz).
PLUTO_MIN_TX_RF_BANDWIDTH_HZ = 200_000.0

# USB 2.0 üzerinde eşzamanlı RX+TX için muhafazakâr örnekleme tavanı.
PLUTO_DUPLEX_SAMPLE_RATE_HZ = 2_048_000.0


def pluto_duplex_spectrum_hint() -> str:
    """Receiver Sample rate satırında gösterilecek eşzamanlı RX+TX spektrum metni."""
    msps = PLUTO_DUPLEX_SAMPLE_RATE_HZ / 1_000_000.0
    half_mhz = PLUTO_DUPLEX_SAMPLE_RATE_HZ / 2.0 / 1_000_000.0
    return f"eşzamanlı RX+TX ≤ {msps:g} Msps / ±{half_mhz:g} MHz"

# Gürültü + CW: OTA öz-dinlemede ince çizgi görünsün diye CW baskın.
TX_TONE_AMPLITUDE = 0.85
TX_NOISE_RMS = 0.12
