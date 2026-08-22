"""EA / karıştırma istisna hiyerarşisi."""

from sdr_console.tx.errors import TXError


class JamError(TXError):
    """Karıştırma oturumu hataları."""


class JamNotConfirmedError(JamError):
    """Operatör onayı olmadan baraj yayını başlatılamaz."""


class JamNotAuthorizedError(JamError):
    """Yetkili test penceresi kutusu işaretlenmeden yayın yok."""


class JamPolicyError(JamError):
    """Frekans / bant / attenuation / süre tavanı ihlali."""
