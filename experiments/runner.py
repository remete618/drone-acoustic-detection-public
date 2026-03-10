import json
import time
from pathlib import Path

import click
import yaml
import numpy as np

from capture.recorder import save_wav, save_metadata
from capture.mock import generate_mock_recording, DRONE_PROFILES, ENVIRONMENT_PROFILES
from processing.spectrogram import load_audio, compute_snr, detect_peaks
from visualization.figures import plot_spectrogram, plot_snr_timeline


EXPERIMENT_CONFIGS = {
    "exp1_detection_range": {
        "name": "Acoustic Detection Range by Drone Class",
        "drone_types": ["fpv_5inch", "micro_whoop", "dji_mini"],
        "environments": ["open_field", "suburban"],
        "distances_m": [25, 50, 75, 100, 150, 200],
        "passes_per_condition": 5,
        "altitude_m": 3,
        "duration_s": 15,
    },
    "exp2_adversarial": {
        "name": "Adversarial Acoustic Modification",
        "drone_types": ["fpv_5inch"],
        "conditions": ["standard_props", "quiet_props", "low_throttle"],
        "distance_m": 75,
        "passes_per_condition": 5,
        "duration_s": 15,
    },
    "exp3_urban_noise": {
        "name": "Urban Noise Degradation",
        "drone_types": ["fpv_5inch"],
        "environments": ["open_field", "suburban", "warehouse"],
        "distance_m": 75,
        "passes_per_condition": 10,
        "duration_s": 15,
    },
    "exp4_multi_drone": {
        "name": "Multi-Drone Simultaneous Detection",
        "drone_types": ["fpv_5inch", "micro_whoop"],
        "distance_m": 50,
        "passes": 10,
        "duration_s": 20,
    },
}


def run_experiment_mock(experiment_id: str, output_dir: Path, channels: int = 4):
    config = EXPERIMENT_CONFIGS[experiment_id]
    exp_dir = output_dir / experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Experiment: {config['name']}")
    print(f"Mode: MOCK (simulated data)")
    print(f"Channels: {channels}")
    print(f"{'='*60}\n")

    results = {}

    if experiment_id == "exp1_detection_range":
        results = _run_exp1_mock(config, exp_dir, channels)
    elif experiment_id == "exp2_adversarial":
        results = _run_exp2_mock(config, exp_dir, channels)
    elif experiment_id == "exp3_urban_noise":
        results = _run_exp3_mock(config, exp_dir, channels)
    elif experiment_id == "exp4_multi_drone":
        results = _run_exp4_mock(config, exp_dir, channels)

    results_path = exp_dir / "results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved: {results_path}")

    return results


def _run_exp1_mock(config, exp_dir, channels):
    results = {}
    sr = 48000

    for drone_type in config["drone_types"]:
        results[drone_type] = {}
        for env in config["environments"]:
            snr_by_distance = {}
            for dist in config["distances_m"]:
                snrs = []
                for pass_num in range(config["passes_per_condition"]):
                    run_dir = exp_dir / drone_type / env / f"{dist}m" / f"pass_{pass_num+1}"
                    data = generate_mock_recording(
                        drone_type=drone_type,
                        environment=env,
                        distance_m=dist,
                        duration_s=config["duration_s"],
                        sample_rate=sr,
                        channels=channels,
                    )
                    save_wav(data, run_dir / "recording.wav", sr)
                    y, _ = load_audio(run_dir / "recording.wav", sr=sr)
                    snr = compute_snr(y, sr)
                    snrs.append(snr)

                snr_by_distance[dist] = {
                    "mean_snr_db": round(float(np.mean(snrs)), 2),
                    "std_snr_db": round(float(np.std(snrs)), 2),
                    "detected": float(np.mean(snrs)) > 3.0,
                }
                print(f"  {drone_type}/{env}/{dist}m: SNR={np.mean(snrs):.1f} +/- {np.std(snrs):.1f} dB")

            # Find detection range
            detection_range = 0
            for dist in config["distances_m"]:
                if snr_by_distance[dist]["detected"]:
                    detection_range = dist

            results[drone_type][env] = {
                "snr_by_distance": snr_by_distance,
                "mean_detection_m": detection_range,
                "std_detection_m": 0,
            }

    return results


def _run_exp2_mock(config, exp_dir, channels):
    results = {}
    sr = 48000
    dist = config["distance_m"]

    for condition in config["conditions"]:
        snrs = []
        all_peaks = []

        for pass_num in range(config["passes_per_condition"]):
            run_dir = exp_dir / condition / f"pass_{pass_num+1}"

            # Modify mock params based on condition
            drone = "fpv_5inch"
            distance = dist
            if condition == "quiet_props":
                distance = dist * 0.8  # Quieter props = effectively closer detection
            elif condition == "low_throttle":
                distance = dist * 1.5  # Lower throttle = lower amplitude

            data = generate_mock_recording(
                drone_type=drone,
                environment="open_field",
                distance_m=distance,
                duration_s=config["duration_s"],
                sample_rate=sr,
                channels=channels,
            )
            save_wav(data, run_dir / "recording.wav", sr)

            y, _ = load_audio(run_dir / "recording.wav", sr=sr)
            snr = compute_snr(y, sr)
            peaks = detect_peaks(y, sr)
            snrs.append(snr)
            all_peaks.append(peaks)

        # Generate comparison spectrogram for first pass
        first_wav = exp_dir / condition / "pass_1" / "recording.wav"
        y, _ = load_audio(first_wav, sr=sr)
        plot_spectrogram(
            y, sr,
            title=f"Exp 2: {condition}",
            output_path=exp_dir / f"spectrogram_{condition}.png",
        )

        results[condition] = {
            "mean_snr_db": round(float(np.mean(snrs)), 2),
            "std_snr_db": round(float(np.std(snrs)), 2),
            "peak_frequencies": all_peaks[0] if all_peaks else [],
        }
        print(f"  {condition}: SNR={np.mean(snrs):.1f} +/- {np.std(snrs):.1f} dB")

    return results


def _run_exp3_mock(config, exp_dir, channels):
    results = {}
    sr = 48000

    for env in config["environments"]:
        snrs = []
        for pass_num in range(config["passes_per_condition"]):
            run_dir = exp_dir / env / f"pass_{pass_num+1}"
            data = generate_mock_recording(
                drone_type="fpv_5inch",
                environment=env,
                distance_m=config["distance_m"],
                duration_s=config["duration_s"],
                sample_rate=sr,
                channels=channels,
            )
            save_wav(data, run_dir / "recording.wav", sr)
            y, _ = load_audio(run_dir / "recording.wav", sr=sr)
            snr = compute_snr(y, sr)
            snrs.append(snr)

        results[env] = {
            "mean_snr_db": round(float(np.mean(snrs)), 2),
            "std_snr_db": round(float(np.std(snrs)), 2),
            "ambient_db": ENVIRONMENT_PROFILES[env]["ambient_db"],
        }
        print(f"  {env}: SNR={np.mean(snrs):.1f} +/- {np.std(snrs):.1f} dB")

    return results


def _run_exp4_mock(config, exp_dir, channels):
    sr = 48000
    results = {"passes": []}

    for pass_num in range(config["passes"]):
        run_dir = exp_dir / f"pass_{pass_num+1}"

        # Two drones at different angles
        drone1 = generate_mock_recording(
            drone_type="fpv_5inch",
            environment="open_field",
            distance_m=config["distance_m"],
            duration_s=config["duration_s"],
            sample_rate=sr,
            channels=channels,
        )
        drone2 = generate_mock_recording(
            drone_type="micro_whoop",
            environment="open_field",
            distance_m=config["distance_m"],
            duration_s=config["duration_s"],
            sample_rate=sr,
            channels=channels,
        )

        combined = drone1 + drone2
        peak = np.max(np.abs(combined))
        if peak > 0.95:
            combined *= 0.95 / peak

        save_wav(combined, run_dir / "recording.wav", sr)

        y, _ = load_audio(run_dir / "recording.wav", sr=sr)
        peaks = detect_peaks(y, sr, n_peaks=10)

        # Check if both fundamental frequencies are detected
        fpv_fund = 280
        whoop_fund = 450
        tolerance = 30

        fpv_detected = any(abs(p["frequency_hz"] - fpv_fund) < tolerance for p in peaks)
        whoop_detected = any(abs(p["frequency_hz"] - whoop_fund) < tolerance for p in peaks)

        results["passes"].append({
            "pass": pass_num + 1,
            "fpv_detected": fpv_detected,
            "whoop_detected": whoop_detected,
            "both_detected": fpv_detected and whoop_detected,
            "peaks": peaks,
        })
        status = "BOTH" if fpv_detected and whoop_detected else "PARTIAL"
        print(f"  Pass {pass_num+1}: {status} (FPV={fpv_detected}, Whoop={whoop_detected})")

    both_count = sum(1 for p in results["passes"] if p["both_detected"])
    results["detection_rate"] = both_count / config["passes"]
    print(f"  Dual detection rate: {results['detection_rate']:.0%}")

    # Save annotated spectrogram of first pass
    first_wav = exp_dir / "pass_1" / "recording.wav"
    y, _ = load_audio(first_wav, sr=sr)
    plot_spectrogram(
        y, sr,
        title="Exp 4: Dual Drone Signatures (FPV 5\" + Micro Whoop)",
        output_path=exp_dir / "dual_spectrogram.png",
    )

    return results


@click.command()
@click.argument("experiment", type=click.Choice(list(EXPERIMENT_CONFIGS.keys()) + ["all"]))
@click.option("--mock", is_flag=True, help="Use mock data")
@click.option("--channels", default=4, type=click.Choice(["2", "4"]), help="Number of channels")
@click.option("--output", default="data/experiments", help="Output directory")
def main(experiment, mock, channels, output):
    channels = int(channels)
    output_dir = Path(output)

    if not mock:
        print("Live recording mode not yet implemented. Use --mock for now.")
        return

    if experiment == "all":
        for exp_id in EXPERIMENT_CONFIGS:
            run_experiment_mock(exp_id, output_dir, channels)
    else:
        run_experiment_mock(experiment, output_dir, channels)


if __name__ == "__main__":
    main()
