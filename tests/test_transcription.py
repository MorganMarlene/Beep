import os
from pathlib import Path
from unittest.mock import patch

import pytest

from spotlight.app import format_elapsed_time, format_timestamp
from spotlight.transcription import (
    CudaRuntimeUnavailableError,
    TranscriptionError,
    configure_packaged_cuda_dlls,
    detect_compute_config,
    detect_missing_cuda_dlls,
    detect_packaged_cuda_dll_directories,
    transcribe_video,
)


def test_format_timestamp_preserves_milliseconds() -> None:
    assert format_timestamp(3723.456) == "01:02:03.456"


def test_format_elapsed_time() -> None:
    assert format_elapsed_time(3723.456) == "01:02:03.46"


def test_detect_compute_config_uses_cuda_when_available() -> None:
    with (
        patch(
            "spotlight.transcription.configure_packaged_cuda_dlls",
            return_value=(Path("C:/python/nvidia/cublas/bin"),),
        ),
        patch("ctranslate2.get_cuda_device_count", return_value=1),
        patch("spotlight.transcription.detect_missing_cuda_dlls", return_value=()),
    ):
        compute = detect_compute_config()

    assert compute.device == "cuda"
    assert compute.compute_type == "float16"
    assert "Python packages" in compute.library_source


def test_detect_compute_config_falls_back_to_cpu() -> None:
    with patch("ctranslate2.get_cuda_device_count", return_value=0):
        assert detect_compute_config().device == "cpu"


def test_detect_compute_config_can_be_forced_to_cpu() -> None:
    assert detect_compute_config(force_cpu=True).device == "cpu"


def test_detect_packaged_cuda_dll_directories(tmp_path: Path) -> None:
    cublas_bin = tmp_path / "nvidia" / "cublas" / "bin"
    cudnn_bin = tmp_path / "nvidia" / "cudnn" / "bin"
    cublas_bin.mkdir(parents=True)
    cudnn_bin.mkdir(parents=True)
    (cublas_bin / "cublas64_12.dll").touch()
    (cudnn_bin / "cudnn64_9.dll").touch()

    assert detect_packaged_cuda_dll_directories([tmp_path]) == (
        cublas_bin.resolve(),
        cudnn_bin.resolve(),
    )


def test_configure_packaged_cuda_dlls_registers_detected_paths(
    tmp_path: Path,
) -> None:
    registered: list[str] = []

    def register(path: str) -> object:
        registered.append(path)
        return object()

    configure_packaged_cuda_dlls(
        directories=(tmp_path,),
        add_directory=register,
        platform="nt",
    )

    assert registered == [str(tmp_path)]


def test_detect_missing_cuda_dlls_reports_load_failures() -> None:
    def load_dll(name: str) -> object:
        if name == "cublas64_12.dll":
            raise OSError
        return object()

    assert detect_missing_cuda_dlls(load_dll, platform="nt") == ("cublas64_12.dll",)


def test_detect_compute_config_explains_missing_cuda_runtime() -> None:
    with (
        patch("ctranslate2.get_cuda_device_count", return_value=1),
        patch(
            "spotlight.transcription.detect_missing_cuda_dlls",
            return_value=("cublas64_12.dll",),
        ),
        pytest.raises(CudaRuntimeUnavailableError, match="CUDA Toolkit 12.8"),
    ):
        detect_compute_config()


def test_transcribe_video_removes_temporary_audio_after_failure(
    tmp_path: Path,
) -> None:
    temporary_audio = tmp_path / "temporary.wav"
    file_descriptor = os.open(temporary_audio, os.O_CREAT | os.O_WRONLY)

    with (
        patch(
            "spotlight.transcription.tempfile.mkstemp",
            return_value=(file_descriptor, str(temporary_audio)),
        ),
        patch(
            "spotlight.transcription.extract_audio",
            side_effect=TranscriptionError("failed"),
        ),
        pytest.raises(TranscriptionError, match="failed"),
    ):
        transcribe_video(Path("video.mp4"), 10.0, lambda _value, _message: None)

    assert not temporary_audio.exists()
