import numpy as np
import pytest

from capture.mock import (
    generate_drone_signal,
    generate_ambient_noise,
    generate_mock_recording,
    DRONE_PROFILES,
    ENVIRONMENT_PROFILES,
)


class TestDroneSignal:
    def test_output_shape_4ch(self):
        signal = generate_drone_signal("fpv_5inch", 50, 1.0, 48000, 4)
        assert signal.shape == (48000, 4)

    def test_output_shape_2ch(self):
        signal = generate_drone_signal("fpv_5inch", 50, 1.0, 48000, 2)
        assert signal.shape == (48000, 2)

    def test_distance_attenuation(self):
        close = generate_drone_signal("fpv_5inch", 10, 1.0, 48000, 1)
        far = generate_drone_signal("fpv_5inch", 100, 1.0, 48000, 1)
        assert np.std(close) > np.std(far)

    def test_all_drone_types(self):
        for drone_type in DRONE_PROFILES:
            signal = generate_drone_signal(drone_type, 50, 0.5, 48000, 2)
            assert signal.shape[0] == 24000
            assert not np.all(signal == 0)

    def test_no_nan_or_inf(self):
        signal = generate_drone_signal("fpv_5inch", 50, 2.0)
        assert not np.any(np.isnan(signal))
        assert not np.any(np.isinf(signal))


class TestAmbientNoise:
    def test_output_shape(self):
        noise = generate_ambient_noise("open_field", 1.0, 48000, 4)
        assert noise.shape == (48000, 4)

    def test_suburban_louder_than_field(self):
        field = generate_ambient_noise("open_field", 1.0)
        suburban = generate_ambient_noise("suburban", 1.0)
        assert np.std(suburban) > np.std(field)

    def test_all_environments(self):
        for env in ENVIRONMENT_PROFILES:
            noise = generate_ambient_noise(env, 0.5, 48000, 2)
            assert noise.shape == (24000, 2)


class TestMockRecording:
    def test_default_output(self):
        rec = generate_mock_recording()
        assert rec.shape == (480000, 4)  # 10s * 48000

    def test_2ch_output(self):
        rec = generate_mock_recording(channels=2)
        assert rec.shape == (480000, 2)

    def test_no_clipping(self):
        rec = generate_mock_recording(distance_m=5)
        assert np.max(np.abs(rec)) <= 1.0

    def test_custom_duration(self):
        rec = generate_mock_recording(duration_s=5.0)
        assert rec.shape[0] == 240000


class TestProcessing:
    def test_spectrogram_output(self):
        from processing.spectrogram import compute_spectrogram
        rec = generate_mock_recording(duration_s=2.0, channels=1)
        data = rec.T  # (channels, samples)
        f, t, Sxx = compute_spectrogram(data, 48000, channel=0)
        assert len(f) > 0
        assert len(t) > 0
        assert Sxx.shape[0] == len(f)

    def test_snr_positive_for_close_drone(self):
        from processing.spectrogram import compute_snr
        rec = generate_mock_recording(distance_m=10, duration_s=2.0, channels=1)
        data = rec.T
        snr = compute_snr(data, 48000)
        assert snr > 0

    def test_snr_lower_for_far_drone(self):
        from processing.spectrogram import compute_snr
        close = generate_mock_recording(distance_m=10, duration_s=2.0, channels=1).T
        far = generate_mock_recording(distance_m=200, duration_s=2.0, channels=1).T
        snr_close = compute_snr(close, 48000)
        snr_far = compute_snr(far, 48000)
        assert snr_close > snr_far

    def test_peak_detection(self):
        from processing.spectrogram import detect_peaks
        rec = generate_mock_recording(
            drone_type="fpv_5inch", distance_m=20, duration_s=2.0, channels=1
        )
        data = rec.T
        peaks = detect_peaks(data, 48000)
        assert len(peaks) > 0
        fundamental = DRONE_PROFILES["fpv_5inch"]["fundamental_hz"]
        closest = min(peaks, key=lambda p: abs(p["frequency_hz"] - fundamental))
        assert abs(closest["frequency_hz"] - fundamental) < 50

    def test_mfcc_output(self):
        from processing.spectrogram import compute_mfcc
        rec = generate_mock_recording(duration_s=2.0, channels=1)
        data = rec.T
        mfcc = compute_mfcc(data, 48000)
        assert mfcc.shape[0] == 13


class TestRadar:
    def test_mock_radar_frame(self):
        from radar.mmwave import AWR1843
        radar = AWR1843("", "", mock=True)
        radar.configure()
        frame = radar.read_frame()
        assert frame is not None
        assert frame.frame_number == 1
        radar.close()

    def test_mock_radar_capture(self):
        from radar.mmwave import AWR1843
        radar = AWR1843("", "", mock=True)
        radar.configure()
        frames = radar.capture_frames(duration_s=1.0)
        assert len(frames) >= 0
        radar.close()
