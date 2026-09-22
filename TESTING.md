# Validation status — 2026-09-22

Development build: Windows 11 x64, CPython **3.14.5**, pip **26.2.1**, PyInstaller **6.22.3**. No Node runtime.

## Passed locally

- **27 automated LocalVoice tests**: settings persistence, input validation, model allowlist, checksum/cancel handling, microphone identity, silence filtering, PCM conversion/resampling, lossless chunking, both recording-mode queues, preservation of edits, direct-input modifier/focus guards, tray-close/quit lifecycle and autostart command generation.
- **30 existing VoiceLab tests** after changing its model references/setup/integrity checker to the migrated files. Two pre-existing FastAPI/Starlette deprecation warnings remain outside LocalVoice.
- Full SHA-256 checks of the relocated large-v3, Silero and downloaded Tiny files.
- Real Whisper **large-v3 on CPU**, public JFK speech fixture, digital silence and seeded low-level noise. Both silence/noise produced an empty transcript with VAD.
- Real Whisper **Tiny on CPU and both AMD Vulkan devices**. Correct speech transcript and no text for the tested silence/noise inputs. Large-v3 on GPU was not retested because other workloads occupied GPU memory.
- Native Windows global hotkey press/release, 0.3-second default-microphone capture (samples discarded), insertion into an isolated test window including umlauts/emoji, and restoration of the previous clipboard text.
- Native GUI launch, settings-window inspection, frozen EXE launch and shutdown.
- Frozen executable: bundled Python 3.14, SciPy resampling, real Tiny inference with Silero and clean backend shutdown.
- Relocated portable EXE in a separate directory containing spaces, **without a `.venv`**, with copied runtime/Tiny/VAD. Sibling-relative paths, GUI, resampling and inference passed.

Raw evidence is intentionally local/ignored under `reports/`, `state/` and `build-output.log`. These checks do not record or publish private microphone audio.

## Not yet certified

- Human day-to-day acceptance of dialect, very short utterances, long sessions and chunk-boundary accuracy.
- Real reboot/login test of Windows autostart (command/registration logic is implemented and unit-tested).
- Every third-party text field, elevated applications, remote desktops and accessibility tools.
- Fresh Windows machine without developer prerequisites; the Vulkan/VC++ runtime requirements must be checked.
- Native Linux/macOS execution and packaging. GitHub CI is configured but has not run remotely. Wayland global shortcut/input integration is not implemented.
- Python 3.15/free-threaded Python support. The next-Python CI lane is only an early-warning check.
- Public-release license compliance review, signing, installers and automatic app updates.
