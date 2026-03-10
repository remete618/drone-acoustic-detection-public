import json
from pathlib import Path

import click
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

from processing.spectrogram import load_audio, compute_spectrogram, compute_mfcc, compute_snr


def plot_spectrogram(
    y: np.ndarray,
    sr: int,
    channel: int = 0,
    title: str = "Spectrogram",
    output_path: Path | None = None,
    max_freq: float = 4000,
):
    f, t, Sxx_db = compute_spectrogram(y, sr, channel=channel)
    freq_mask = f <= max_freq

    fig, ax = plt.subplots(figsize=(12, 5))
    im = ax.pcolormesh(t, f[freq_mask], Sxx_db[freq_mask], shading="gouraud", cmap="magma")
    ax.set_ylabel("Frequency [Hz]")
    ax.set_xlabel("Time [s]")
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label="Power [dB]")
    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        print(f"Saved: {output_path}")
    plt.close(fig)
    return fig


def plot_mfcc(
    y: np.ndarray,
    sr: int,
    channel: int = 0,
    title: str = "MFCC",
    output_path: Path | None = None,
):
    mfcc = compute_mfcc(y, sr, channel=channel)

    fig, ax = plt.subplots(figsize=(12, 4))
    im = ax.imshow(mfcc, aspect="auto", origin="lower", cmap="coolwarm")
    ax.set_ylabel("MFCC Coefficient")
    ax.set_xlabel("Frame")
    ax.set_title(title)
    fig.colorbar(im, ax=ax)
    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        print(f"Saved: {output_path}")
    plt.close(fig)
    return fig


def plot_snr_timeline(
    snr_data: list[dict],
    title: str = "SNR Over Time",
    threshold: float = 3.0,
    output_path: Path | None = None,
):
    times = [d["time_s"] for d in snr_data]
    snrs = [d["snr_db"] for d in snr_data]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(times, snrs, "b-", linewidth=1.5, label="SNR")
    ax.axhline(y=threshold, color="r", linestyle="--", label=f"Threshold ({threshold} dB)")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("SNR [dB]")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        print(f"Saved: {output_path}")
    plt.close(fig)
    return fig


def plot_detection_range_comparison(
    results: dict[str, dict],
    title: str = "Detection Range by Drone Class",
    output_path: Path | None = None,
):
    fig, ax = plt.subplots(figsize=(10, 6))

    drone_types = list(results.keys())
    environments = list(next(iter(results.values())).keys())
    x = np.arange(len(drone_types))
    width = 0.35

    for i, env in enumerate(environments):
        ranges = [results[dt][env]["mean_detection_m"] for dt in drone_types]
        errors = [results[dt][env]["std_detection_m"] for dt in drone_types]
        ax.bar(x + i * width, ranges, width, yerr=errors, label=env, capsize=5)

    ax.set_ylabel("Detection Range [m]")
    ax.set_title(title)
    ax.set_xticks(x + width / 2)
    ax.set_xticklabels(drone_types)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        print(f"Saved: {output_path}")
    plt.close(fig)
    return fig


def plot_channel_comparison(
    y: np.ndarray,
    sr: int,
    title: str = "2ch vs 4ch Spectrogram Comparison",
    output_path: Path | None = None,
    max_freq: float = 4000,
):
    n_channels = y.shape[0] if y.ndim > 1 else 1
    fig, axes = plt.subplots(n_channels, 1, figsize=(12, 3 * n_channels), sharex=True)
    if n_channels == 1:
        axes = [axes]

    for ch in range(n_channels):
        f, t, Sxx_db = compute_spectrogram(y, sr, channel=ch)
        freq_mask = f <= max_freq
        im = axes[ch].pcolormesh(t, f[freq_mask], Sxx_db[freq_mask], shading="gouraud", cmap="magma")
        axes[ch].set_ylabel(f"Ch {ch+1}\nFreq [Hz]")
        fig.colorbar(im, ax=axes[ch], label="dB")

    axes[-1].set_xlabel("Time [s]")
    fig.suptitle(title, y=1.02)
    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        print(f"Saved: {output_path}")
    plt.close(fig)
    return fig


@click.command()
@click.argument("data_dir", type=click.Path(exists=True))
@click.option("--channel", default=0, help="Primary channel to plot")
def main(data_dir, channel):
    data_dir = Path(data_dir)
    wav_path = data_dir / "recording.wav"

    if not wav_path.exists():
        print(f"No recording.wav found in {data_dir}")
        return

    y, sr = load_audio(wav_path)
    n_channels = y.shape[0]

    print(f"Generating figures for {wav_path} ({n_channels}ch)...")

    figures_dir = data_dir / "figures"
    figures_dir.mkdir(exist_ok=True)

    plot_spectrogram(y, sr, channel=channel, output_path=figures_dir / "spectrogram.png")
    plot_mfcc(y, sr, channel=channel, output_path=figures_dir / "mfcc.png")

    if n_channels > 1:
        plot_channel_comparison(y, sr, output_path=figures_dir / "channel_comparison.png")

    snr = compute_snr(y, sr, channel=channel)
    print(f"SNR: {snr:.1f} dB")
    print(f"Figures saved to: {figures_dir}")


if __name__ == "__main__":
    main()
