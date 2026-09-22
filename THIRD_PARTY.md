# Third-party components

LocalVoice's own code/logo are MIT licensed. This does **not** relicense its dependencies or downloaded model weights.

| Component | License / upstream |
|---|---|
| whisper.cpp + ggml | MIT; https://github.com/ggml-org/whisper.cpp ; pinned revision in `runtime/README.md`; included `licenses/whisper.cpp-MIT.txt`. |
| OpenAI Whisper weights / converted GGML weights | Upstream model terms (Whisper MIT); https://github.com/openai/whisper and https://huggingface.co/ggerganov/whisper.cpp. Downloaded separately, excluded from Git. |
| Silero VAD | MIT upstream; https://github.com/snakers4/silero-vad and https://huggingface.co/ggml-org/whisper-vad. Downloaded separately. |
| Python | PSF license and bundled notices; https://www.python.org/downloads/source/. |
| PySide6, Shiboken, Qt modules used here | LGPLv3 option; QtCore/Gui/Widgets/Network are dynamically bundled, unmodified. https://code.qt.io/cgit/pyside/pyside-setup.git/ and https://code.qt.io/cgit/qt/qtbase.git/. Version: 6.11.2. |
| NumPy / SciPy | BSD-style licenses, plus bundled numerical-library notices. |
| sounddevice / PortAudio | MIT; binaries include PortAudio notices. |
| requests and dependencies | Apache-2.0/BSD/MIT/MPL as declared by the respective packages. |
| pynput | LGPLv3; only needed for non-Windows keyboard integration. Windows uses native APIs. |
| PyInstaller | GPL with bootloader exception allowing distribution of bundled applications under other licenses. |

`Build.ps1` collects available installed distribution license files into `licenses/python-packages/` and the Python license into `licenses/Python-LICENSE.txt`. These generated notices are excluded from source control but must accompany binary distributions. The complete installed package/version snapshot is `requirements-windows.lock.txt`. LGPL-3.0 and its incorporated GPL-3.0 terms are also included explicitly.

## Public-release checklist

- Include this file, MIT license and the entire `licenses/` folder.
- Preserve Qt/PySide's dynamic libraries in `_internal/`: users must be able to replace/relink compatible LGPL components. No ban on reverse engineering for debugging modifications to those libraries.
- Supply/offer the corresponding source for the exact LGPL components as required; retain exact upstream source versions/build details. Upstream source links alone are **not a claim that all distribution obligations have already been fulfilled**.
- Audit all transitive native notices (Qt, numerical libraries, Vulkan/OpenMP/MSVC runtime) for the actual release build. The current local build has not undergone a final legal/distribution review.
- Model licenses/model-card conditions must be checked independently when changing download sources. Do not commit model weights into this repository.
- Do not include private settings, logs, audio, test reports or signing credentials in releases.

The project is a local development build, not yet a signed, publicly distributed release.
