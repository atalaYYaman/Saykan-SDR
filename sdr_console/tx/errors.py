"""TX katmanı istisna hiyerarşisi."""


class TXError(Exception):
    """TX işlemlerinde temel hata sınıfı."""


class TXAttenuationLimitError(TXError):
    """İstenen TX gücü kodda tanımlı güvenlik üst sınırını aştığında."""


class ReplayNotConfirmedError(TXError):
    """TX replay başlamadan önce kullanıcı onayı verilmediğinde."""
