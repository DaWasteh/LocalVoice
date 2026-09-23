# Third-party components

LocalVoice's own code and logo are MIT licensed. This does **not** relicense its dependencies or downloaded model weights.

| Component | License / upstream |
|---|---|
| whisper.cpp + ggml | MIT; https://github.com/ggml-org/whisper.cpp ; pinned revision in `runtime/README.md`; `licenses/whisper.cpp-MIT.txt`. |
| OpenAI Whisper weights / converted GGML weights | Upstream model terms (Whisper: MIT); https://github.com/openai/whisper and https://huggingface.co/ggerganov/whisper.cpp. Downloaded by the user, not shipped. |
| Silero VAD | MIT; https://github.com/snakers4/silero-vad and https://huggingface.co/ggml-org/whisper-vad. Downloaded by the user, not shipped. |
| Python | PSF license; `licenses/Python-LICENSE.txt`; https://www.python.org/downloads/source/. |
| PySide6, Shiboken6, Qt (QtCore/Gui/Widgets/Network) | LGPL-3.0 (option chosen here); version 6.11.2, unmodified, dynamically linked. Source: https://code.qt.io/cgit/pyside/pyside-setup.git/ and https://download.qt.io/official_releases/QtForPython/. `licenses/LGPL-3.0.txt`, `licenses/GPL-3.0.txt`. |
| NumPy / SciPy | BSD-3-Clause, plus bundled notices for their numerical libraries. |
| sounddevice / PortAudio | MIT. |
| requests, urllib3, certifi, idna, charset-normalizer | Apache-2.0 / MIT / MPL-2.0 as declared by each package. |
| pynput | LGPL-3.0; only used for keyboard integration on Linux/macOS. Windows uses native APIs. |
| Microsoft Visual C++ runtime (`msvcp140.dll`, `vcruntime140*.dll`, `vcomp140.dll` in `runtime/`) | Redistributable files under the Microsoft Visual Studio license terms (app-local deployment). |
| PyInstaller bootloader | GPL-2.0 with an exception that allows distributing bundled applications under their own license. |

## Notes for binary distributions

- `Build.ps1` collects the license files of all installed Python distributions into `licenses/python-packages/` and the Python license into `licenses/Python-LICENSE.txt`. The release ZIP contains the complete `licenses/` folder, this file and `LICENSE`. The exact package versions of a build are listed in `requirements-windows.lock.txt`.
- Qt/PySide libraries stay as separate, replaceable DLLs in `_internal/`. Users may replace them with compatible modified versions; reverse engineering for debugging such modifications is permitted.
- The corresponding source code of the LGPL components is the unmodified upstream release of the listed version (links above). On request, the maintainer provides the exact source archives used for a release.
- Model weights are never committed or shipped; check the model cards when changing download sources.
- Releases never contain settings, logs, audio, test reports or signing credentials (`state/`, `reports/` are excluded by `scripts/package_release.py`).
