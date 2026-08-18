"""TX güvenlik sınırları ve varsayılanlar."""

# tx_hardwaregain_chan0 bu değerden güçlü (daha pozitif) olamaz; örn. -30 dB reddedilir.
MAX_TX_GAIN_DB = -40.0

# Minimum zorunlu attenuation: gain <= MAX_TX_GAIN_DB  =>  attenuation >= abs(MAX_TX_GAIN_DB)
MIN_TX_ATTENUATION_DB = abs(MAX_TX_GAIN_DB)

# Kullanıcı tercihi: başlangıç varsayılanı neredeyse minimum güç.
DEFAULT_TX_ATTENUATION_DB = 50.0

# max_duration_s None verildiğinde kullanılan süre sınırı (saniye).
DEFAULT_MAX_TX_DURATION_S = 5.0

# pyadi-iio Pluto TX/RX örnek ölçeği (12-bit ADC tepe).
TX_FULL_SCALE = 2048.0
