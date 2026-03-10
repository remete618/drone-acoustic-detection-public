import numpy as np

DRONE_PROFILES = {
    "fpv_5inch": {
        "fundamental_hz": 280,
        "harmonics": [560, 840, 1120],
        "harmonic_amplitudes": [0.6, 0.3, 0.15],
        "noise_floor_db": -60,
        "broadband_amplitude": 0.05,
    },
    "micro_whoop": {
        "fundamental_hz": 450,
        "harmonics": [900, 1350],
        "harmonic_amplitudes": [0.4, 0.2],
        "noise_floor_db": -70,
        "broadband_amplitude": 0.03,
    },
    "dji_mini": {
        "fundamental_hz": 180,
        "harmonics": [360, 540, 720],
        "harmonic_amplitudes": [0.5, 0.25, 0.1],
        "noise_floor_db": -55,
        "broadband_amplitude": 0.04,
    },
}

ENVIRONMENT_PROFILES = {
    "open_field": {"ambient_db": 35, "wind_noise_hz": 20, "wind_amplitude": 0.01},
    "suburban": {"ambient_db": 55, "wind_noise_hz": 30, "wind_amplitude": 0.03},
    "warehouse": {"ambient_db": 45, "wind_noise_hz": 10, "wind_amplitude": 0.005},
}


def generate_drone_signal(
    drone_type: str,
    distance_m: float,
    duration_s: float,
    sample_rate: int = 48000,
    channels: int = 4,
    approaching: bool = True,
) -> np.ndarray:
    profile = DRONE_PROFILES[drone_type]
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)

    # Distance attenuation: inverse square law (amplitude ~ 1/r)
    attenuation = 1.0 / max(distance_m, 1.0)

    signal = np.zeros(len(t))

    # Fundamental frequency with slight variation (motor RPM jitter)
    rpm_jitter = 1.0 + 0.02 * np.sin(2 * np.pi * 3.0 * t)
    fund_hz = profile["fundamental_hz"] * rpm_jitter
    phase = np.cumsum(2 * np.pi * fund_hz / sample_rate)
    signal += np.sin(phase) * attenuation

    for harm_hz, harm_amp in zip(
        profile["harmonics"], profile["harmonic_amplitudes"]
    ):
        harm_freq = harm_hz * rpm_jitter
        harm_phase = np.cumsum(2 * np.pi * harm_freq / sample_rate)
        signal += np.sin(harm_phase) * harm_amp * attenuation

    # Broadband motor noise
    signal += (
        np.random.randn(len(t)) * profile["broadband_amplitude"] * attenuation
    )

    # Doppler shift for approaching drone
    if approaching:
        speed_ms = 15.0  # ~54 km/h approach
        doppler_ratio = 1.0 + (speed_ms / 343.0) * np.linspace(1, -1, len(t))
        signal *= doppler_ratio

    # Multi-channel with time-of-arrival differences (tetrahedral array, ~5cm spacing)
    mic_spacing_m = 0.05
    multichannel = np.zeros((len(t), channels))
    for ch in range(channels):
        delay_samples = int(
            (ch * mic_spacing_m / 343.0) * sample_rate * np.sin(np.pi / 4)
        )
        multichannel[:, ch] = np.roll(signal, delay_samples)

    return multichannel


def generate_ambient_noise(
    environment: str,
    duration_s: float,
    sample_rate: int = 48000,
    channels: int = 4,
) -> np.ndarray:
    env = ENVIRONMENT_PROFILES[environment]
    n_samples = int(sample_rate * duration_s)

    amplitude = 10 ** (env["ambient_db"] / 20) * 1e-4

    noise = np.random.randn(n_samples, channels) * amplitude

    # Low-frequency wind noise
    t = np.linspace(0, duration_s, n_samples, endpoint=False)
    for ch in range(channels):
        wind = np.sin(2 * np.pi * env["wind_noise_hz"] * t + ch * 0.5)
        noise[:, ch] += wind * env["wind_amplitude"]

    return noise


def generate_mock_recording(
    drone_type: str = "fpv_5inch",
    environment: str = "open_field",
    distance_m: float = 75.0,
    duration_s: float = 10.0,
    sample_rate: int = 48000,
    channels: int = 4,
    approaching: bool = True,
) -> np.ndarray:
    drone = generate_drone_signal(
        drone_type, distance_m, duration_s, sample_rate, channels, approaching
    )
    ambient = generate_ambient_noise(environment, duration_s, sample_rate, channels)
    combined = drone + ambient
    # Normalize to prevent clipping
    peak = np.max(np.abs(combined))
    if peak > 0.95:
        combined = combined * (0.95 / peak)
    return combined
