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

## Architecture

Layered layout under `sdr_console/`:

- `hal/` — device drivers (mock, Pluto, file playback, scenarios)
- `dsp/` — numpy/scipy signal processing (dBFS spectrum frames)
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
