# Performance Review

## Evidence snapshot

Read-only diagnostics were taken on 2026-08-01 from the audit machine. They prove runtime visibility, not end-to-end performance.

| Item | Observed |
|---|---|
| GPU | NVIDIA GeForce RTX 3070 Ti, 8,192 MiB; driver 596.36 |
| Python | 3.12.13, 64-bit |
| CTranslate2 | 4.8.1; `get_cuda_device_count()` returned 1 |
| Whisper policy | `WHISPER_MODEL_NAME = "base"`; CUDA `float16`, CPU `int8` |
| CUDA Python DLLs | cuBLAS and cuDNN directories detected under `.venv/Lib/site-packages/nvidia/.../bin` |
| FFmpeg / ffprobe | 8.1.2 Windows full build discoverable on PATH |
| Ollama service | Loopback `/api/version` returned 0.32.5; `/api/tags` returned `qwen2.5:7b`, Q4_K_M, 4.68 GB model file |
| Ollama CLI | Not discoverable on the audit PowerShell PATH even though the service endpoint worked |
| Installed package footprint | PySide6 about 634 MB; cuBLAS about 736 MB; cuDNN about 1,071 MB; CTranslate2 about 60 MB; ONNX Runtime about 39 MB |

The standalone missing-DLL probe reported DLLs missing before process registration; `detect_compute_config()` then registered packaged directories and selected CUDA. This confirms ordering matters and that freezer/installer layouts must be tested.

## Verified bottlenecks and risks

### High — model construction on every transcription

`transcribe_audio` constructs `WhisperModel` for each run. This repeats model discovery/load and can churn RAM/VRAM. It simplifies lifecycle and is acceptable for the MVP, but it will penalize one-click batches and multiple VODs.

**Recommendation:** first measure model-load versus decode time. If load exceeds 10% of repeated-job time, add a single-process model session with explicit release, device/model keying, idle timeout, and cancellation. Do not keep both Whisper and a large Ollama model resident on an 8 GB GPU without a memory budget.

### High — sequential, non-streaming AI batches

`analyze_transcript` waits for each `OllamaClient.analyze_batch` response before starting the next and emits only coarse batch progress. `/api/generate` uses `stream: false`; each batch has a 180-second timeout and there is no total deadline or cancellation. Time-to-first-candidate equals at least one full batch generation, and a late failure discards all visible progress.

**Recommendation:** add timing/response metrics and cancellation first; then stream validated batch results while final ranking remains deterministic. Avoid parallel Ollama batches on 8 GB VRAM until measured because concurrency can reduce throughput or cause paging.

### High — GPU contention is unmanaged (Future risk)

Current UI actions are serial, but BEEP does not control Ollama's model residency and faster-whisper has its own CUDA lifecycle. A 4.68 GB quantized Ollama model plus context/cache and Whisper can approach the 8 GB budget. Automatic background ingest would make overlap likely.

**Recommendation:** implement a local resource scheduler before background Twitch automation: one GPU-intensive job at a time by default, observable VRAM pressure, CPU fallback policy, and explicit Ollama keep-alive/unload behavior. Preserve user override only after warnings and measurement.

### Medium — audio extraction progress and cancellation

`extract_audio` writes a mono 16 kHz 16-bit WAV and waits for FFmpeg without a timeout or progress parsing. Disk cost is about 115 MB per hour of source, so an eight-hour VOD requires roughly 0.9 GB of temporary disk. The UI remains responsive but appears at a coarse progress value until extraction finishes.

**Recommendation:** preflight free space, parse FFmpeg progress, set a cancellation-aware process deadline, and retain `finally` cleanup. Never load the WAV fully into memory.

### Medium — full in-memory/UI transcript copies

`ProjectRepository.load_project` fetches all rows, `ProjectSnapshot` holds tuples, `SpotlightWindow._show_transcript` copies them to a list, builds one joined string, and `QPlainTextEdit` builds its own document. Long VODs therefore have several transient representations. Candidate analysis serializes each overlapping batch again.

**Recommendation:** establish a long-VOD fixture and measure peak working set. Paginate/virtualize only when limits are exceeded; avoid speculative database paging that complicates timestamp/search behavior prematurely.

### Medium — candidate merge worst case

`merge_and_rank_candidates` searches the accumulated `merged` list for every candidate, giving quadratic worst-case comparisons. Current candidate sets are small. Optimize only if a benchmark with at least 1,000 candidates misses the target.

### Medium — synchronous UI persistence

Project load and full transcript/candidate replacements occur in UI slots. Local SQLite should normally be fast, but antivirus, OneDrive-like locations, locks, or large histories can exceed the responsiveness budget. Instrument before moving the calls off-thread.

### Low — startup is appropriately lazy in one important respect

`faster_whisper` is imported inside `transcribe_audio`, so application startup does not load the inference stack/model. Ollama is contacted only when analysis begins. Preserve this behavior in packaging.

## Measurable performance goals

These are proposed acceptance targets, not measured current results. Record median and p95 across at least five runs after one warm-up, with power mode, thermal state, versions, model, source characteristics, and GPU/CPU captured.

### Reference workload

- Windows 11, NVMe SSD, 32 GB RAM, RTX 3070 Ti 8 GB, audit-equivalent driver or supported minimum.
- 60-minute 1080p H.264/AAC VOD at 30/60 fps, normal dialogue density; include separate 4-hour and damaged-media soak cases.
- faster-whisper `base`, CUDA FP16; CPU INT8 fallback separately.
- Ollama 0.32.5 minimum/current-supported lane with `qwen2.5:7b` Q4_K_M and the default BEEP batching configuration.

| Metric | Initial release goal | Escalation rule |
|---|---:|---|
| Cold process launch to responsive window | p95 ≤ 2.5 s | Block release above 4 s or if model/network work occurs during launch. |
| Warm launch to responsive window | p95 ≤ 1.5 s | Investigate >20% regression. |
| UI event-loop delay during jobs | p95 ≤ 100 ms; maximum ≤ 250 ms | Any repeatable >500 ms freeze is High. |
| Project recent-list query (10 rows) | p95 ≤ 50 ms | Move off-thread/investigate storage at >50 ms. |
| Load 10,000 transcript segments + 200 candidates | p95 ≤ 250 ms; UI blocked ≤ 50 ms | Add background load/virtualization if missed. |
| Replace 10,000 transcript segments | p95 ≤ 250 ms | Batch/transaction tune before schema expansion. |
| Replace 200 candidates | p95 ≤ 100 ms | Investigate serialization/indexing if missed. |
| GPU transcription real-time factor | p95 ≤ 0.10 (60 min in ≤ 6 min), stretch ≤ 0.05 | A >15% regression requires explanation. |
| CPU fallback real-time factor | p95 ≤ 0.75 (60 min in ≤ 45 min) | Show expectation if slower; never imply GPU speed. |
| Transcription progress update cadence | at least every 2 s during active decode | Explain model load/extraction phases separately. |
| AI time to first validated candidates (streaming target) | p95 ≤ 15 s | Display batch progress and allow cancel if missed. |
| AI total for 60-minute transcript | p95 ≤ 180 s and no single batch >45 s | Fail with actionable timeout; retain validated partials only if spec permits. |
| AI invalid candidate rate | <5% of returned items; 0 invalid items displayed/persisted | Log redacted counts, not transcript text. |
| Peak BEEP working set, 4-hour project excluding model server | ≤ 1.0 GB | Profile duplicate transcript/document representations. |
| Peak GPU memory under the supported single-job policy | ≤ 7.2 GB | Queue/fallback before allocation failure. |
| Temporary disk preflight | free space ≥ estimated WAV + output + 2 GB safety | Refuse safely with exact requirement. |

## Benchmark plan in small changes

1. **Performance harness:** add generated fixtures, timers, UI heartbeat, process RSS, and DB scenarios; no optimization.
2. **Transcription baseline:** record extraction/model-load/decode separately on CPU and supported NVIDIA hardware.
3. **AI baseline:** record health/model load, prompt size, tokens/second if available, first/total result, invalid-output count, and VRAM.
4. **Database baseline:** 1/4/8-hour synthetic projects, lock/antivirus-like delay injection, startup schema check.
5. **Targeted optimization:** approve only the bottleneck that misses a target.
6. **Regression gate:** store machine-qualified baselines; warn on >10%, fail on >20% only in stable hardware lanes.

## Performance release checklist

- [ ] Benchmarks identify versions, source properties, model, device, power, and thermal conditions.
- [ ] CPU and CUDA diagnostics shown to the user match the device actually used.
- [ ] Whisper/Ollama are not loaded at application startup.
- [ ] GPU jobs are serialized or proven safe within 8 GB VRAM.
- [ ] Every long operation is cancellable and has progress plus a total deadline.
- [ ] Long-VOD peak RAM, VRAM, temporary disk, and final data growth meet budgets.
- [ ] UI heartbeat and database p95 targets pass at 1440p while processing.
- [ ] No performance change sacrifices timestamp integrity, story boundaries, transactional persistence, or error diagnostics.
