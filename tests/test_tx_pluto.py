"""PlutoTXDevice paylaşılan IIO handle (RX ile aynı context)."""

from __future__ import annotations

import numpy as np
import pytest

from sdr_console.hal.pluto_device import PlutoSDRDevice
from sdr_console.tx.pluto_tx import PlutoTXDevice
from tests.test_hal_pluto import _install_fake_adi


def test_shared_tx_uses_rx_handle_and_does_not_destroy_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_adi(monkeypatch)
    rx = PlutoSDRDevice(sample_rate_hz=2_048_000.0, center_freq_hz=100_000_000.0)
    rx.connect()
    fake = rx._sdr
    assert fake is not None

    tx = PlutoTXDevice(
        tx_freq_hz=433_970_000.0,
        sample_rate_hz=1_000_000.0,
        shared_sdr=rx.iio_backend,
        shared_lock=rx.iio_lock,
        bandwidth_hz=100_000.0,
    )
    assert tx.is_connected
    assert not tx.owns_sdr
    assert tx.sample_rate_hz == pytest.approx(2_048_000.0)
    assert fake.tx_lo == 433_970_000
    assert fake.tx_enabled_channels == [0]

    iq = np.ones(64, dtype=np.complex64)
    tx.transmit(iq, cyclic=True, max_duration_s=0.05)
    assert fake._tx_calls == 1
    tx.disconnect()

    assert rx._sdr is fake
    assert rx.is_connected
    samples = rx.read_samples(128)
    assert samples.shape == (128,)
    rx.disconnect()
