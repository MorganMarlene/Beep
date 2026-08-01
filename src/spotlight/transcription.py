"""Local audio extraction and transcription."""

import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ProgressCallback = Callable[[int, str], None]
WHISPER_MODEL_NAME = "base"
CUDA_RUNTIME_DLLS = (
    "cublas64_12.dll",
    "cublasLt64_12.dll",
    "cudnn64_9.dll",
    "cudnn_ops64_9.dll",
)
CUDA_PACKAGE_COMPONENTS = ("cublas", "cudnn", "cuda_runtime")
_CUDA_DLL_DIRECTORY_HANDLES: list[object] = []
_CUDA_DLL_DIRECTORIES: tuple[Path, ...] = ()
CUDA_INSTALL_INSTRUCTIONS = (
    "Install NVIDIA CUDA Toolkit 12.8 for Windows x86_64 from "
    "https://developer.nvidia.com/cuda-12-8-0-download-archive, then install "
    "NVIDIA cuDNN 9 for CUDA 12 from https://developer.nvidia.com/cudnn-downloads. "
    "Ensure the CUDA and cuDNN bin folders are on your Windows PATH, restart "
    "Windows, and launch Spotlight again."
)


class TranscriptionError(Exception):
    """Raised when audio extraction or transcription fails."""


class CudaRuntimeUnavailableError(TranscriptionError):
    """Raised when CUDA is selected but its required DLLs cannot be loaded."""

    def __init__(self, missing_dlls: tuple[str, ...]) -> None:
        missing = ", ".join(missing_dlls)
        super().__init__(
            f"CUDA cannot start because these runtime DLLs are missing or cannot "
            f"be loaded: {missing}. {CUDA_INSTALL_INSTRUCTIONS}"
        )


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """One timestamped segment returned by faster-whisper."""

    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True, slots=True)
class ComputeConfig:
    """faster-whisper device and numeric compute configuration."""

    device: str
    compute_type: str
    library_source: str


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """A completed transcript and the runtime details that produced it."""

    segments: list[TranscriptSegment]
    compute_device: str
    model_name: str
    elapsed_seconds: float
    cuda_library_source: str


def detect_packaged_cuda_dll_directories(
    search_paths: list[Path] | None = None,
) -> tuple[Path, ...]:
    """Find CUDA DLL directories installed by NVIDIA Python packages."""
    roots = search_paths or [Path(entry) for entry in sys.path if entry]
    directories: list[Path] = []

    for root in roots:
        nvidia_root = root / "nvidia"
        for component in CUDA_PACKAGE_COMPONENTS:
            bin_directory = nvidia_root / component / "bin"
            if bin_directory.is_dir() and any(bin_directory.glob("*.dll")):
                resolved = bin_directory.resolve()
                if resolved not in directories:
                    directories.append(resolved)

    return tuple(directories)


def configure_packaged_cuda_dlls(
    directories: tuple[Path, ...] | None = None,
    add_directory: Callable[[str], object] | None = None,
    platform: str = os.name,
) -> tuple[Path, ...]:
    """Register packaged CUDA directories with Windows for this process."""
    global _CUDA_DLL_DIRECTORIES

    detected = (
        directories
        if directories is not None
        else detect_packaged_cuda_dll_directories()
    )
    if platform != "nt" or not detected:
        return detected

    if add_directory is None:
        add_directory = os.add_dll_directory

    already_registered = set(_CUDA_DLL_DIRECTORIES)
    new_directories = [path for path in detected if path not in already_registered]
    for directory in new_directories:
        _CUDA_DLL_DIRECTORY_HANDLES.append(add_directory(str(directory)))

    _CUDA_DLL_DIRECTORIES = (*_CUDA_DLL_DIRECTORIES, *new_directories)
    return detected


def detect_missing_cuda_dlls(
    loader: Callable[[str], object] | None = None,
    platform: str = os.name,
) -> tuple[str, ...]:
    """Return required CUDA DLLs that Windows cannot load."""
    if platform != "nt":
        return ()

    if loader is None:
        import ctypes

        loader = ctypes.WinDLL

    missing: list[str] = []
    for dll_name in CUDA_RUNTIME_DLLS:
        try:
            loader(dll_name)
        except OSError:
            missing.append(dll_name)
    return tuple(missing)


def detect_compute_config(force_cpu: bool = False) -> ComputeConfig:
    """Use CUDA with FP16 when CTranslate2 can see an NVIDIA GPU."""
    if force_cpu:
        return ComputeConfig(
            device="cpu",
            compute_type="int8",
            library_source="Not used (CPU)",
        )

    try:
        packaged_directories = configure_packaged_cuda_dlls()
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            missing_dlls = detect_missing_cuda_dlls()
            if missing_dlls:
                raise CudaRuntimeUnavailableError(missing_dlls)
            source = (
                "Python packages: "
                + "; ".join(str(path) for path in packaged_directories)
                if packaged_directories
                else "Windows DLL search path"
            )
            return ComputeConfig(
                device="cuda",
                compute_type="float16",
                library_source=source,
            )
    except CudaRuntimeUnavailableError:
        raise
    except (ImportError, RuntimeError):
        pass

    return ComputeConfig(
        device="cpu",
        compute_type="int8",
        library_source="Not used (CPU)",
    )


def extract_audio(video_path: Path, audio_path: Path) -> None:
    """Extract mono 16 kHz WAV audio from a video with FFmpeg."""
    command = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(audio_path),
    ]
    try:
        subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as error:
        raise TranscriptionError(
            "FFmpeg is not installed or ffmpeg is not available on PATH. "
            "Install FFmpeg from https://ffmpeg.org/download.html, ensure "
            "ffmpeg.exe is on PATH, and restart Spotlight."
        ) from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or "Audio could not be extracted."
        raise TranscriptionError(f"FFmpeg failed: {detail}") from error


def transcribe_audio(
    audio_path: Path,
    duration_seconds: float,
    progress: ProgressCallback,
    force_cpu: bool = False,
) -> tuple[list[TranscriptSegment], ComputeConfig]:
    """Transcribe WAV audio locally with faster-whisper."""
    try:
        from faster_whisper import WhisperModel  # pyright: ignore[reportMissingImports]
    except ImportError as error:
        raise TranscriptionError(
            "faster-whisper is not installed. From the Spotlight folder, run "
            "'uv sync' in PowerShell, then restart Spotlight."
        ) from error

    try:
        compute = detect_compute_config(force_cpu=force_cpu)
        progress(
            25,
            f"Loading Whisper model '{WHISPER_MODEL_NAME}' on "
            f"{compute.device.upper()}...",
        )
        try:
            model = WhisperModel(
                WHISPER_MODEL_NAME,
                device=compute.device,
                compute_type=compute.compute_type,
            )
        except RuntimeError as error:
            if compute.device != "cuda":
                raise
            error_text = str(error).lower()
            if ".dll" in error_text and (
                "not found" in error_text or "cannot be loaded" in error_text
            ):
                mentioned_dlls = tuple(
                    dll_name
                    for dll_name in CUDA_RUNTIME_DLLS
                    if dll_name.lower() in error_text
                )
                raise CudaRuntimeUnavailableError(
                    mentioned_dlls or CUDA_RUNTIME_DLLS
                ) from error
            compute = ComputeConfig(
                device="cpu",
                compute_type="int8",
                library_source="Not used (CPU fallback)",
            )
            progress(25, "CUDA unavailable; loading Whisper model on CPU...")
            model = WhisperModel(
                WHISPER_MODEL_NAME,
                device=compute.device,
                compute_type=compute.compute_type,
            )
        raw_segments, _ = model.transcribe(str(audio_path))

        segments: list[TranscriptSegment] = []
        for raw_segment in raw_segments:
            segment: Any = raw_segment
            segments.append(
                TranscriptSegment(
                    start_seconds=float(segment.start),
                    end_seconds=float(segment.end),
                    text=str(segment.text).strip(),
                )
            )
            fraction = min(float(segment.end) / max(duration_seconds, 1.0), 1.0)
            progress(25 + int(fraction * 74), "Transcribing audio...")
        return segments, compute
    except TranscriptionError:
        raise
    except Exception as error:
        raise TranscriptionError(f"Transcription failed: {error}") from error


def transcribe_video(
    video_path: Path,
    duration_seconds: float,
    progress: ProgressCallback,
    force_cpu: bool = False,
) -> TranscriptionResult:
    """Extract and transcribe audio, always removing the temporary WAV file."""
    started_at = time.perf_counter()
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="spotlight-", suffix=".wav"
    )
    os.close(file_descriptor)
    temporary_audio = Path(temporary_name)

    try:
        progress(5, "Extracting audio with FFmpeg...")
        extract_audio(video_path, temporary_audio)
        progress(20, "Audio extraction complete.")
        segments, compute = transcribe_audio(
            temporary_audio,
            duration_seconds,
            progress,
            force_cpu=force_cpu,
        )
        progress(100, "Transcription complete.")
        return TranscriptionResult(
            segments=segments,
            compute_device=compute.device,
            model_name=WHISPER_MODEL_NAME,
            elapsed_seconds=time.perf_counter() - started_at,
            cuda_library_source=compute.library_source,
        )
    finally:
        temporary_audio.unlink(missing_ok=True)
