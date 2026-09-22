# Validation status — v0.2.0 — 2026-09-22

Development build: Windows 11 x64, CPython **3.14.5**, pip **26.2.1**, PyInstaller **6.22.3**. No Node runtime.

## Passed locally

- **37 automated LocalVoice tests**: v0.1 coverage plus stable dropdown geometry/hitboxes, mouse/keyboard/wheel behavior, v0.1 settings migration, faster first-chunk timing without lost samples, bounded per-recording prompt context, warmup failures, and lossless backlog coalescing.
- **30 existing VoiceLab tests** after changing its model references/setup/integrity checker to the migrated files. Two pre-existing FastAPI/Starlette deprecation warnings remain outside LocalVoice.
- Full SHA-256 checks of the relocated large-v3, Silero and downloaded Tiny files.
- Real Whisper **large-v3 on CPU**, public JFK speech fixture, digital silence and seeded low-level noise. Both silence/noise produced an empty transcript with VAD.
- Real Whisper **Tiny on CPU and both AMD Vulkan devices**. Correct speech transcript and no text for the tested silence/noise inputs. Large-v3 on GPU was not retested because other workloads occupied GPU memory.
- Native Windows global hotkey press/release, 0.3-second default-microphone capture (samples discarded), insertion into an isolated test window including umlauts/emoji, and restoration of the previous clipboard text.
- Native GUI launch, settings-window inspection, frozen EXE launch and shutdown.
- Frozen executable: bundled Python 3.14, SciPy resampling, real Tiny inference with Silero and clean backend shutdown.
- Relocated portable EXE in a separate directory containing spaces, **without a `.venv`**, with copied runtime/Tiny/VAD. Sibling-relative paths, GUI, resampling and inference passed.

Raw evidence is intentionally local/ignored under `reports/`, `state/` and `build-output.log`. These checks do not record or publish private microphone audio.

## v0.2 preview measurements

Real local `large-v3-turbo`, same 21.168-second German fixture, VAD enabled. No live microphone audio was collected for these measurements.

| Check | v0.1 buffering | v0.2 buffering | v0.2 actual first text |
|---|---:|---:|---:|
| RX 9070 XT, Vulkan 0 | 8.75 s | 4.00 s | **4.20 s** |
| CPU | 8.75 s | 4.00 s | **10.715 s** |

The actual values come from real-time pacing of the fixture through GUI → Recorder → Whisper → editor (`scripts/check_preview_live.py`), including model preparation. A separate non-real-time comparison measured ~0.17 s first-chunk GPU inference versus ~6.6 s CPU inference. Thus four-second buffering does **not** imply a four-second CPU result. The v0.1 cold first-result estimate for the same GPU fixture was 10.723 s; it is a model-load/inference scheduling estimate, not a separately paced old-GUI run.

Backlog coalescing kept the CPU run to 31.084 s total for 21.168 s audio rather than paying a separate full encoder pass for every small queued tail. The GPU run finished at 21.452 s. These are local smoke measurements, not controlled hardware benchmarks or general latency promises.

Both English and German comparisons retained speech content in this small sample; short chunks can still change punctuation/case or lose words at forced boundaries. Comparison scripts report differences against full-clip ASR, **not human-labelled word-error rate**. The source fixtures and transcript reports are not committed.

Native dropdown checks passed with both initial selections, up/down pointer movements and normal/150% scale. Explicit viewport-size assertions also cover the padding-related clipping regression found during testing.

## Not yet certified

- Human day-to-day acceptance of dialect, very short utterances, long sessions and chunk-boundary accuracy.
- Real reboot/login test of Windows autostart (command/registration logic is implemented and unit-tested).
- Every third-party text field, elevated applications, remote desktops and accessibility tools.
- Fresh Windows machine without developer prerequisites; the Vulkan/VC++ runtime requirements must be checked.
- Native Linux/macOS execution and packaging. GitHub CI is configured but has not run remotely. Wayland global shortcut/input integration is not implemented.
- Python 3.15/free-threaded Python support. The next-Python CI lane is only an early-warning check.
- Public-release license compliance review, signing, installers and automatic app updates.
