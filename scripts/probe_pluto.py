#!/usr/bin/env python3
"""Smoke-check ADALM-Pluto discovery, capability probe, and a short IQ capture.

Usage:
    python scripts/probe_pluto.py
    python scripts/probe_pluto.py --uri ip:192.168.2.1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running without an editable install.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np  # noqa: E402

from sdr_console.hal.discovery import scan_devices  # noqa: E402
from sdr_console.hal.errors import (  # noqa: E402
    DeviceConnectionError,
    DeviceUnavailableError,
)
from sdr_console.hal.pluto_device import PlutoSDRDevice  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe ADALM-Pluto via pyadi-iio")
    parser.add_argument("--uri", default="", help="libiio URI (empty = auto)")
    parser.add_argument("--samples", type=int, default=16_384, help="IQ samples to capture")
    parser.add_argument("--rate", type=float, default=2_048_000.0, help="Sample rate Hz")
    parser.add_argument("--freq", type=float, default=100_000_000.0, help="Center frequency Hz")
    parser.add_argument("--gain", type=float, default=40.0, help="Manual gain dB")
    args = parser.parse_args(argv)

    print("=== Discovery ===")
    found = scan_devices()
    if not found:
        print("(no libiio contexts matched Pluto — URI auto-detect may still work)")
    for device in found:
        print(f"  {device.label}  serial={device.serial!r}")

    uri = args.uri or (found[0].uri if found else "")
    print(f"\n=== Connecting (uri={(uri or 'auto')!r}) ===")
    device = PlutoSDRDevice(
        uri=uri,
        sample_rate_hz=args.rate,
        center_freq_hz=args.freq,
        gain_db=args.gain,
        rx_buffer_size=max(args.samples, 4096),
    )
    try:
        device.connect()
    except (DeviceUnavailableError, DeviceConnectionError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    caps = device.capabilities
    print("Capabilities after probe:")
    print(f"  freq:  {caps.min_freq_hz:g} … {caps.max_freq_hz:g} Hz")
    print(
        f"  rate:  {caps.min_sample_rate_hz} … {caps.max_sample_rate_hz} Hz "
        f"(presets={caps.supported_sample_rates_hz})"
    )
    print(f"  gain:  {caps.min_gain_db} … {caps.max_gain_db} dB  modes={caps.gain_modes}")

    print(f"\n=== Capturing {args.samples} samples ===")
    iq = device.read_samples(args.samples)
    device.disconnect()

    mag = np.abs(iq)
    print(f"  dtype={iq.dtype}  n={iq.size}")
    print(f"  |IQ| min={mag.min():.4f}  max={mag.max():.4f}  rms={np.sqrt(np.mean(mag**2)):.4f}")

    spectrum = np.fft.fftshift(np.fft.fft(iq * np.hanning(iq.size)))
    peak_bin = int(np.argmax(np.abs(spectrum)))
    freqs = np.fft.fftshift(np.fft.fftfreq(iq.size, d=1.0 / args.rate))
    peak_hz = float(freqs[peak_bin]) + args.freq
    print(f"  peak ≈ {peak_hz:g} Hz (offset {freqs[peak_bin]:g} Hz)")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
