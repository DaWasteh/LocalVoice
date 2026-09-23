# LocalVoice

**Deine Stimme. Dein Text. Lokal.** LocalVoice ist eine schlanke Diktier-App für Windows, eine lokale Alternative zu `Win+H`. Die Spracherkennung läuft vollständig auf deinem PC mit [whisper.cpp](https://github.com/ggml-org/whisper.cpp) und Silero-VAD. Es gibt keine Cloud-Erkennung, kein Konto und keine Telemetrie.

<p align="center"><img src="assets/localvoice.svg" width="110" alt="LocalVoice-Logo"></p>

- Globaler Hotkey (`Ctrl+Alt+Space`), wahlweise Start/Stopp oder Push-to-talk
- Direkt ins aktive Textfeld diktieren oder erst im editierbaren Transkript sammeln
- „Am Ende schreiben“ für beste Qualität oder „Vorschau in Abschnitten“ für schnellen Text
- GPU-Beschleunigung über Vulkan (NVIDIA, AMD, Intel), CPU als Alternative
- Whisper-Modelle von Tiny bis Large v3, mit SHA-256-Prüfung heruntergeladen

## Installation (Windows 10/11, 64 Bit)

1. Unter **Releases** die Datei `LocalVoice-vX.Y.Z-windows-x64.zip` herunterladen.
2. In einen **beschreibbaren Ordner** entpacken, z. B. `Dokumente\LocalVoice`, nicht nach `C:\Programme`. Einstellungen und Modelle liegen neben der EXE.
3. `LocalVoice.exe` starten.
4. Über das **Logo oben links** die Einstellungen öffnen. Unter **Audio & Modelle** ein Modell wählen und **„Ausgewähltes Modell + VAD herunterladen“** klicken.

Python muss nicht installiert sein. Die Visual-C++-Laufzeit liegt bei. Benötigt wird ein aktueller Grafiktreiber, der den **Vulkan-Loader** (`vulkan-1.dll`) mitbringt. Das ist bei aktuellen NVIDIA-, AMD- und Intel-Treibern der Fall und auch für den CPU-Modus nötig.

Die EXE ist nicht codesigniert. Windows SmartScreen kann deshalb beim ersten Start warnen („Weitere Informationen“ → „Trotzdem ausführen“).

### Welches Modell?

| Modell | Größe | Empfehlung |
|---|---:|---|
| Large v3 Turbo | ~1,6 GB | Beste Wahl mit GPU: schnell und sehr genau |
| Large v3 | ~3,1 GB | Höchste Qualität, braucht viel Speicher/Rechenzeit |
| Large v3 Turbo Q5 | ~574 MB | Wenig Grafikspeicher |
| Small / Base | 466 / 142 MB | Nur CPU oder ältere Hardware |
| Tiny | ~75 MB | Tests; deutlich ungenauer |

Beim ersten Start wählt LocalVoice automatisch eine dedizierte GPU, sonst eine integrierte, sonst die CPU. Das lässt sich unter **Rechengerät** ändern.

## Bedienung

- **`Ctrl+Alt+Space`** startet/stoppt eine Aufnahme, auch wenn LocalVoice nicht im Vordergrund ist. Hotkey und Verhalten (Start/Stopp oder Gedrückt halten) sind einstellbar.
- **Am Ende schreiben:** Erst die gesamte Aufnahme, dann die Erkennung. Das liefert die beste Satz- und Zeichensetzungsqualität.
- **Vorschau in Abschnitten:** Text erscheint abschnittsweise. Der erste Abschnitt kommt bei einer Sprechpause ab 2 Sekunden, spätestens nach 4 Sekunden (einstellbar 2–20 s). Die Rechenzeit kommt hinzu. Whisper erhält bis zu 400 Zeichen der laufenden Aufnahme als Kontext für den Satzanschluss. Feste Zeitgrenzen können mitten in ein Wort fallen.
- Das **Transkript ist editierbar**. „Kopieren“ kopiert den gesamten Inhalt; bei **„Einfügen in 3 s“** klickst du danach in das gewünschte Textfeld.
- **„Direkt ins aktive Textfeld diktieren“** (Haken unten): Textfeld anklicken, dann den Hotkey drücken. Der Text wird dort eingefügt, wo der Fokus zu Beginn war. Wechselt das Fenster zwischendurch, schreibt LocalVoice nicht blind woanders hin. Die Erkennung läuft weiter und der Text landet vollständig im aufklappbaren Transkript.
- Bei **Push-to-talk mit Ctrl/Alt/Shift/Win** wartet das Einfügen, bis diese Tasten losgelassen sind. Eine einzelne F-Taste (z. B. `F9`) fügt schon während des Haltens ein.
- **X** versteckt die App im Infobereich. „Beenden“ im Tray-Menü beendet sie samt Whisper-Prozess.
- Eine Aufnahme dauert höchstens **10 Minuten**. Danach stoppt sie automatisch und der Text wird erstellt. Kurze Audio-Aussetzer werden gemeldet, die Aufnahme läuft aber weiter.

## Datenschutz

- Audio wird nur im Arbeitsspeicher verarbeitet. Es gibt keine Aufnahmedateien und keine Transkript-Historie. Der Editorinhalt geht beim Beenden verloren.
- Internet wird nur für den bewusst ausgelösten Modell-Download von Hugging Face benötigt. Downloads sind an eine feste Revision gebunden und werden vor der Installation per SHA-256 und Dateigröße geprüft.
- Der lokale Whisper-Server lauscht nur auf **127.0.0.1** (zufälliger Port, zufälliger URL-Präfix). Das schützt vor Zugriffen aus Webseiten, ist aber keine Sicherheitsgrenze gegenüber anderen Programmen desselben Benutzers.
- Direktes Einfügen nutzt kurz die Zwischenablage und `Ctrl+V`, damit Umlaute, Emoji und Zeilenumbrüche funktionieren. Der vorherige Inhalt wird nach 2 Sekunden wiederhergestellt, außer du hast inzwischen selbst etwas kopiert. Der Diktattext wird für den Windows-Verlauf und die Cloud-Synchronisierung gesperrt. Fremde Clipboard-Manager können ihn dennoch sehen.
- Diagnosen des Whisper-Servers stehen in `state/backend.log` und werden bei jedem Start überschrieben.

## Grenzen

- Admin-/UAC-Fenster, Passwortfelder und manche geschützte Anwendungen blockieren das Einfügen. Dann bleibt der Text im Transkript zum Kopieren. LocalVoice nicht als Administrator starten.
- Ein Wechsel zwischen zwei Textfeldern **innerhalb** desselben Fensters lässt sich nicht erkennen.
- VAD und Stillefilter reduzieren Halluzinationen, verhindern sie bei Musik, Geräuschen oder sehr kurzen Äußerungen aber nicht vollständig. Wichtige Texte gegenlesen.
- LocalVoice wechselt **nicht heimlich auf die CPU**, wenn die gewählte GPU nicht funktioniert (z. B. weil ein anderes Programm den Grafikspeicher belegt). In dem Fall CPU oder ein kleineres Modell wählen.
- Nach einem Umzug des Ordners aktualisiert LocalVoice den Autostart-Eintrag beim nächsten Start selbst.

## Plattformstatus

| Plattform | Stand |
|---|---|
| Windows 10/11 x64 | Unterstützt; getestet unter Windows 11 (CPU und Vulkan). |
| Linux (X11) | Code vorbereitet (`xdotool`, PortAudio, eigener whisper-server-Build), noch nicht real getestet. |
| Linux (Wayland) | Globale Hotkeys und automatisches Einfügen noch nicht unterstützt. |
| macOS | Code und Metal-Runtime-Build vorbereitet, noch nicht real getestet; kein signiertes `.app`. |

## Entwicklung

Voraussetzungen: Windows, **Python 3.14** (64 Bit). Für die Whisper-Runtime zusätzlich Git, CMake, Visual Studio mit C++-Werkzeugen und das Vulkan SDK.

```powershell
.\Setup.ps1                                   # .venv mit Python 3.14 + Abhängigkeiten
.venv\Scripts\python.exe scripts\build_runtime.py   # whisper-server.exe aus gepinntem Quellstand
.venv\Scripts\python.exe main.py              # aus dem Quellcode starten
.venv\Scripts\python.exe -m pytest -q         # Tests
.\Build.ps1                                   # Tests, EXE und Release-ZIP in dist\
```

`Build.ps1` erzeugt `LocalVoice.exe` und `_internal\` im Projektordner und packt daraus `dist\LocalVoice-v<version>-windows-x64.zip` samt SHA-256-Datei. Modelle, Runtime-Binärdateien, EXE und Build-Ordner sind absichtlich nicht im Repository.

- `pyproject.toml`: Mindestversion und verträgliche Abhängigkeitsbereiche; `requirements*.txt`: getestete Versionen; `requirements-windows.lock.txt`: vollständiger Build-Snapshot.
- Runtime-Details: [runtime/README.md](runtime/README.md). Testumfang: [TESTING.md](TESTING.md). Änderungen: [CHANGELOG.md](CHANGELOG.md).

### Zusätzliche lokale Prüfungen

```powershell
.venv\Scripts\python.exe scripts\check_windows_integration.py
.venv\Scripts\python.exe scripts\check_backend.py --audio <16kHz-Mono-PCM16.wav> --model tiny --device cpu
.venv\Scripts\python.exe scripts\check_portable.py --audio <Testdatei.wav> --package dist\LocalVoice-v<version>-windows-x64.zip
.venv\Scripts\python.exe scripts\check_dropdown.py
.venv\Scripts\python.exe scripts\check_preview.py --audio <Testdatei.wav> --model large-v3-turbo --device cpu --language de
.venv\Scripts\python.exe scripts\check_preview_live.py --audio <Testdatei.wav> --device cpu
```

Der Integrationstest öffnet ein eigenes Wegwerf-Textfenster und nimmt etwa 0,3 Sekunden vom Standardmikrofon auf, **ohne die Samples zu speichern**. Berichte landen lokal in `reports\` bzw. `state\`, nicht in Git.

## Lizenz

LocalVoice selbst (Code und Logo) steht unter der **MIT-Lizenz**. Whisper, die Modelle, Qt/PySide, Python und weitere Komponenten haben eigene Lizenzen; siehe [THIRD_PARTY.md](THIRD_PARTY.md) und den Ordner `licenses/` im Release.
