# SDR Console

Personal SDR console for real-time IQ processing and waterfall visualization.

## Quick start

```bash
pip install -e ".[dev]"
pytest
python -m sdr_console
# optional: python -m sdr_console --log-level=DEBUG
```

Click **Start** to stream mock IQ data; **Stop** to halt.

## Real hardware (ADALM-Pluto)

Pluto support is an optional extra on top of Analog Devices **libiio**.

1. Install the Windows [libiio / Pluto USB drivers](https://github.com/analogdevicesinc/libiio/releases)
   (or the Analog Devices PlutoSDR installer) so `iio` and the USB device are visible.
2. Install the Python binding:

```bash
pip install -e ".[pluto]"
```

3. Launch the console, select **ADALM-Pluto**, leave URI empty for auto-detect
   (or enter `ip:192.168.2.1` / a `usb:` URI), then **Start**.

Optional smoke check without the GUI:

```bash
python scripts/probe_pluto.py
```

**Throughput note:** Pluto is USB 2.0. Continuous streaming without drops is
typically reliable around 5–6 Msps; higher rates may drop blocks (shown in the
status bar). Prefer larger FFT sizes / `rx_buffer_size` (default 16384 in config)
when pushing sample rate.

RTL-SDR and HackRF appear in the device list as skeletons (greyed out until
their libraries and streaming paths are completed).

## Listening (audio)

Demodulated audio needs the optional audio extra:

```bash
pip install -e ".[audio]"
```

Tick **Audio → Enable**, then **Start**. The listening channel is the highlighted
box on the spectrum: click the plots or drag the box to move it, and set its
width with **Bandwidth**. Without the extra the console still runs; only the
audio checkbox stays disabled.

To hear something without hardware, pick **Mock Device (AM test, +50 kHz)**: it
transmits a 1 kHz tone on an AM carrier 50 kHz above the tuned centre frequency.
Move the listening box onto that carrier and raise **Gain** — the chain has no
AGC, so audio level follows RF level.

The demodulation chain runs beside the display chain on the same IQ stream, so a
lagging waterfall never interrupts audio. Its sample rate follows the device rate
(2.048 Msps gives 48.8 kHz audio) and the output stream is opened at exactly that
rate, which avoids resampling on our side.

## Architecture

Layered layout under `sdr_console/`:

- `hal/` — device drivers (mock, Pluto, file playback, scenarios)
- `dsp/` — numpy/scipy signal processing (dBFS spectrum frames, channelizer)
- `demod/` — demodulation modes (AM, N-FM, W-FM, USB, LSB, CW) via `Demodulator` ABC
- `audio/` — sound card output via `sounddevice`
- `pipeline/` — worker threads and drop-oldest queues
- `viz/` — pyqtgraph widgets
- `ui/` — PyQt6 main window
- `config/` — defaults and JSON persistence (`~/.sdr-console/config.json`)

See each layer's `README.md` for responsibilities.

## Tests

```bash
pytest -q
python -m tests.fixtures.generate   # regenerate IQ fixtures if needed
```
