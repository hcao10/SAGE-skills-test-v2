from __future__ import annotations

import numpy as np
import pandas as pd


def generate_synthetic_vibration(
    duration_sec: float = 2.0,
    sample_rate_hz: int = 2048,
    base_fault_hz: float = 81.0,
    base_amplitude: float = 6.5,
    noise_level: float = 0.8,
    harmonic_enabled: bool = True,
    harmonic_multiplier: float = 2.0,
    harmonic_scale: float = 0.35,
) -> pd.DataFrame:
    n = int(duration_sec * sample_rate_hz)
    t = np.arange(n) / sample_rate_hz

    signal = base_amplitude * np.sin(2 * np.pi * base_fault_hz * t)

    if harmonic_enabled:
        harmonic_hz = base_fault_hz * harmonic_multiplier
        signal += (base_amplitude * harmonic_scale) * np.sin(2 * np.pi * harmonic_hz * t)

    noise = np.random.normal(loc=0.0, scale=noise_level, size=n)
    amplitude = signal + noise

    return pd.DataFrame({"time": t, "amplitude": amplitude})
