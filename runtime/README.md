# Whisper runtime

Place `whisper-server.exe` (Windows) or `whisper-server` (Linux/macOS), and any required shared libraries, here. Binaries are intentionally ignored by Git.

Current tested source: https://github.com/ggml-org/whisper.cpp
Commit: `307869af285d7f6f689ba100b3515e2d1b3feb05`.

The local Windows binary was built with `BUILD_SHARED_LIBS=OFF`, `GGML_VULKAN=ON`, `WHISPER_BUILD_SERVER=ON` (Visual Studio 2026, Release).

Rebuild with Python 3.14, Git, CMake, a C++ compiler and the Vulkan SDK:

```sh
python scripts/build_runtime.py --backend vulkan
```

On macOS use `--backend metal`, or `--backend cpu` for CPU-only builds. These native Linux/macOS builds still need validation on their respective platforms. See the root README for desktop integration limitations.
