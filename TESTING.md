# Validation status — v0.3.2

Release toolchain: CPython **3.14**, PyInstaller **6.22.3**, whisper.cpp at the revision pinned in `runtime/README.md` (unchanged from v0.3.1).

Local regression run on Ubuntu/Wayland: **67 passed, 2 Windows-only tests skipped**. Linux autostart entries are validated and actually launched via GLib, including spaces, Unicode, percent signs, quotes, backslashes and control characters. This simulates the desktop launch, not a logout/login cycle.

The release is gated on the nine stable CI combinations below and a Windows ZIP build/start smoke test. Existing hardware measurements below are from the earlier Windows reference build, not new v0.3.2 hardware runs.

## Automated tests (`pytest`)

69 test cases (platform-specific skips), run by `Build.ps1` before every build; the GitHub Actions workflow runs them on Windows, Linux and macOS with Python 3.12, 3.13 and 3.14:

- Settings persistence, corruption handling and v0.1 → v0.2 migration.
- Lossless preview chunking, early first chunk, bounded prompt context, backlog coalescing without duplicate samples.
- Recording never discards captured audio: the 10-minute limit stops and transcribes; audio glitches only warn; consumer failures are reported.
- Direct dictation: waits for released modifier keys, never types into a changed window, and a failed insertion keeps recording and transcribing into the editor.
- Clipboard paste: overlapping pastes restore the user's original content; a newer user copy always wins; the restore delay covers slow targets. The taskbar is never a dictation target.
- Checksum-verified, revision-pinned downloads; cancelled/corrupt/missing files are never installed or reported as success.
- Whisper server lifecycle: warm-up errors surface, and on Windows the server process dies with LocalVoice even after a hard kill (job object).
- Dropdown popup geometry/hitboxes, wheel protection, hotkey parsing (e.g. `shift+a` is rejected), first-run GPU selection.
- Autostart: unchanged Windows registry command for frozen/source launches; Linux XDG config selection and real desktop execution; macOS plist contents and native `plutil` validation; repeated enable/disable, moved folders, atomic replacement failures and UI rollback.
- Settings remain saveable with an unchanged, unavailable hotkey (Wayland).

## Manual / hardware checks (Windows 11)

- Real Whisper **large-v3** and **tiny** on CPU; **tiny** and **large-v3-turbo** on AMD Vulkan GPUs. Public JFK speech sample transcribed correctly; digital silence and seeded low-level noise produced no text.
- Native global hotkey press/release, short default-microphone capture (samples discarded), Unicode insertion (umlauts, emoji) into an isolated test window and clipboard restoration (`scripts/check_windows_integration.py`).
- Release ZIP extracted to a new folder with spaces, without Python or a venv: GUI start, SciPy resampling and real inference with Silero VAD (`scripts/check_portable.py --package`).
- Dropdowns at 100 % and 150 % display scaling (`scripts/check_dropdown.py`).

## Preview latency (v0.2 measurement)

`large-v3-turbo`, 21.2-second German speech sample paced in real time through GUI → recorder → Whisper → editor (`scripts/check_preview_live.py`), VAD enabled, including model preparation:

| Device | Buffering before first chunk | First text on screen |
|---|---:|---:|
| RX 9070 XT, Vulkan | 4.00 s | **4.20 s** |
| CPU | 4.00 s | **10.7 s** |

Four seconds of buffering do not imply a four-second result on CPU. Backlog coalescing kept the CPU run at 31.1 s total for 21.2 s of audio. These are local smoke measurements, not controlled benchmarks. Short chunks can change punctuation/case or lose words at forced boundaries; the comparison scripts report differences against full-clip recognition, not a human-labelled word error rate.

## Not yet covered

- Long-term everyday use with dialects, very short utterances and long sessions.
- A real reboot/login test of autostart on Windows, Linux or macOS (registration is automated-tested; the Linux desktop command is actually launched).
- Every third-party text field, elevated applications, remote desktops and accessibility tools.
- A clean Windows 10 installation and NVIDIA/Intel GPUs.
- Complete Linux/macOS hardware/inference/package validation; Wayland hotkeys/insertion are not implemented.
- Python 3.15 and free-threaded Python (the CI lane for 3.15 is an early warning only).
