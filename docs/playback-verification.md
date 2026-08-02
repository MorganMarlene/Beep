# Embedded Playback Verification

## Supported Version 1 baseline

- Primary OS: Windows 10/11
- Containers: MP4 and MOV
- Verified fixture codecs: H.264 video with AAC audio
- Playback engine: PySide6 Qt Multimedia using the backend selected by Qt
- Source handling: streamed from the original local path; no full-file or Python
  decoded-frame buffering

Hardware video decoding is controlled by Qt, its multimedia backend, Windows,
and the installed driver. BEEP does not claim CUDA or NVDEC use unless a future
backend exposes reliable evidence. This is independent of faster-whisper's
CTranslate2 CUDA configuration.

## Automated verification

Run the complete suite:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
openspec validate embedded-video-workspace --strict
```

Run the optional real-backend fixture tests:

```powershell
$env:BEEP_RUN_PLAYBACK_INTEGRATION = "1"
uv run pytest tests/test_playback_integration.py -q -s
```

The integration tests generate small H.264/AAC MP4 and MOV files inside pytest's
temporary directory. No media fixture is stored in Git.

On 2026-08-01, the local Windows test environment successfully loaded both
generated containers. Five paused decoded-frame seeks in the generated 640x360
MP4 measured 33.7 milliseconds at p95. This is a small synthetic reference, not
a guarantee for long-GOP, damaged, network-mounted, variable-frame-rate, 4K, or
unusual-codec media.

## Manual acceptance checklist

1. Launch BEEP at 2560x1440 and create or open a project.
2. Open a representative local H.264/AAC MP4, confirm the player reports ready,
   and verify visible and audible play/pause behavior.
3. Repeat with a representative H.264/AAC MOV.
4. Drag and click the timeline repeatedly near the beginning, middle, and end;
   confirm the UI remains interactive and the seeking indicator clears.
5. Activate transcript timestamps and clip candidates; confirm playback moves to
   their exact stored start times and does not alter text, timestamps, ranking, or
   candidate details.
6. Search the transcript during playback; confirm search matches, current match,
   selection, and active playback indication remain distinguishable.
7. Switch between projects during playback, then close BEEP; confirm the old
   source is released and no project automatically reopens on restart.
8. Open a project whose VOD was moved or deleted; confirm saved transcript and
   candidates remain reviewable and playback explains the missing path.
9. Open an MKV or AVI; confirm transcription remains available while embedded
   playback clearly reports that Version 1 supports MP4 and MOV only.
10. Repeat the layout check at 1920x1080, 2560x1440, and 3840x2160 with applicable
    Windows scaling values of 100%, 125%, 150%, and 200%. Confirm the video is the
    dominant 1440p region and every required control remains reachable.
11. Navigate play/pause, timeline, transcript timestamps, and candidates using
    only the keyboard. Verify visible focus and inspect names, roles, values, and
    status text with Windows Narrator.
12. During playback, run CUDA transcription and local Ollama analysis separately
    and together. Record responsiveness, VRAM use, decoder errors, and any
    software fallback without assuming playback uses the GPU.

## Known limitations

- Qt Multimedia seeks by source time and may present the nearest decodable frame;
  Version 1 is not frame-accurate.
- Codec support depends on the Qt multimedia backend and installed Windows
  runtime/driver support. Only the H.264/AAC MP4/MOV baseline is verified.
- The 250-millisecond decoded-frame target applies to documented local reference
  fixtures. Long GOPs, 4K media, slow disks, damaged files, and unusual encodings
  may take longer while the UI remains responsive and shows a seeking state.
- Concurrent video decode, CUDA transcription, and Ollama can compete for the
  RTX 3070 Ti's 8 GB VRAM. Version 1 reports failures but does not introduce a
  resource scheduler.
- macOS and Linux are not acceptance-tested in this change, although the
  application-facing playback boundary does not expose Windows backend types.
