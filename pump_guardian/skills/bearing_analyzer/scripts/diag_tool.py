from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def _validate_input(data: pd.DataFrame) -> None:
    required_cols = {"time", "amplitude"}
    if not required_cols.issubset(set(data.columns)):
        missing = required_cols.difference(set(data.columns))
        raise ValueError(f"CSV missing required column(s): {', '.join(sorted(missing))}")
    if len(data) < 16:
        raise ValueError("At least 16 rows are required for FFT analysis.")


def _infer_fault_type(peak_frequency: float) -> str:
    if 75.0 <= peak_frequency <= 90.0:
        return "Bearing outer-race fault signature (approx 81 Hz)"
    if peak_frequency < 20.0:
        return "Potential misalignment or looseness"
    if 20.0 <= peak_frequency <= 60.0:
        return "Possible imbalance-driven vibration"
    return "Broadband or high-frequency bearing activity"


def analyze_signal(data: pd.DataFrame) -> Dict[str, object]:
    _validate_input(data)

    t = data["time"].to_numpy(dtype=float)
    x = data["amplitude"].to_numpy(dtype=float)

    rms = float(np.sqrt(np.mean(np.square(x))))

    dt = float(np.mean(np.diff(t)))
    if dt <= 0:
        raise ValueError("Time values must be strictly increasing.")

    n = len(x)
    freqs = np.fft.rfftfreq(n, d=dt)
    spectrum = np.fft.rfft(x)
    amps = (2.0 / n) * np.abs(spectrum)

    if len(amps) > 0:
        amps[0] = 0.0

    peak_idx = int(np.argmax(amps))
    peak_frequency = float(freqs[peak_idx])
    peak_amplitude = float(amps[peak_idx])
    fault_type = _infer_fault_type(peak_frequency)

    return {
        "rms": rms,
        "frequencies": freqs.tolist(),
        "amplitudes": amps.tolist(),
        "peak_frequency": peak_frequency,
        "peak_amplitude": peak_amplitude,
        "fault_type": fault_type,
    }
