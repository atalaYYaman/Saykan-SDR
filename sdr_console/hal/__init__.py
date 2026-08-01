"""Hardware abstraction layer for SDR devices."""

from sdr_console.hal.capabilities import DeviceCapabilities
from sdr_console.hal.discovery import DiscoveredDevice, scan_devices
from sdr_console.hal.errors import (
    DeviceConnectionError,
    DeviceError,
    DeviceUnavailableError,
)
from sdr_console.hal.file_device import FileIQDevice
from sdr_console.hal.hackrf_device import HACKRF_CAPABILITIES, HackRfDevice
from sdr_console.hal.interface import SDRDeviceInterface
from sdr_console.hal.mock_device import (
    DEFAULT_CENTER_FREQ_HZ,
    MOCK_CAPABILITIES,
    MockSDRDevice,
    MockTone,
    default_tones,
)
from sdr_console.hal.pluto_device import (
    PLUTO_CAPABILITIES,
    PlutoSDRDevice,
    parse_available_range,
)
from sdr_console.hal.registry import (
    DEVICE_CHOICES,
    HACKRF_DEVICE_ID,
    HACKRF_DEVICE_LABEL,
    KNOWN_DEVICE_IDS,
    MOCK_DEVICE_ID,
    MOCK_DEVICE_LABEL,
    PLUTO_DEVICE_ID,
    PLUTO_DEVICE_LABEL,
    RTLSDR_DEVICE_ID,
    RTLSDR_DEVICE_LABEL,
    create_device,
    device_availability,
    is_known_device_id,
)
from sdr_console.hal.rtlsdr_device import RTLSDR_CAPABILITIES, RtlSdrDevice
from sdr_console.hal.scenarios import (
    BurstMockDevice,
    BurstToneSpec,
    SweepMockDevice,
    SweepToneSpec,
    burst_tone,
    clipping_source,
    noise_only,
    sweep_tone,
)

__all__ = [
    "BurstMockDevice",
    "BurstToneSpec",
    "DEVICE_CHOICES",
    "DEFAULT_CENTER_FREQ_HZ",
    "DeviceCapabilities",
    "DeviceConnectionError",
    "DeviceError",
    "DeviceUnavailableError",
    "DiscoveredDevice",
    "FileIQDevice",
    "HACKRF_CAPABILITIES",
    "HACKRF_DEVICE_ID",
    "HACKRF_DEVICE_LABEL",
    "HackRfDevice",
    "KNOWN_DEVICE_IDS",
    "MOCK_CAPABILITIES",
    "MOCK_DEVICE_ID",
    "MOCK_DEVICE_LABEL",
    "MockSDRDevice",
    "MockTone",
    "PLUTO_CAPABILITIES",
    "PLUTO_DEVICE_ID",
    "PLUTO_DEVICE_LABEL",
    "PlutoSDRDevice",
    "RTLSDR_CAPABILITIES",
    "RTLSDR_DEVICE_ID",
    "RTLSDR_DEVICE_LABEL",
    "RtlSdrDevice",
    "SDRDeviceInterface",
    "SweepMockDevice",
    "SweepToneSpec",
    "burst_tone",
    "clipping_source",
    "create_device",
    "default_tones",
    "device_availability",
    "is_known_device_id",
    "noise_only",
    "parse_available_range",
    "scan_devices",
    "sweep_tone",
]
