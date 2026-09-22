# LocalVoice

**Deine Stimme. Dein Text. Lokal.** Eine schlanke Desktop-Diktierhilfe mit Whisper, Silero-VAD und editierbarem Transkript. Keine Cloud-Erkennung, kein Konto, keine Telemetrie.

<p align="center"><img src="assets/localvoice.svg" width="110" alt="LocalVoice logo"></p>

## Start unter Windows

**`LocalVoice.exe` doppelklicken.** Python oder Node müssen dafür nicht installiert sein. Der mitgelieferte Windows-Whisper-Build benötigt den Microsoft Visual C++ x64 Redistributable sowie den Vulkan-Loader eines aktuellen Grafiktreibers (auch bei Auswahl von CPU). Auf diesem Entwicklungsrechner sind diese Voraussetzungen vorhanden; für andere PCs muss das geprüft oder eine CPU-only-Runtime gebaut werden.

Die EXE ist ein portables **Ordnerpaket**, keine einzelne isolierte Datei. Folgende Ordner müssen daneben bleiben:

```text
LocalVoice/
  LocalVoice.exe          # eingebettetes Python 3.14
  _internal/              # Qt, Python und native Python-Abhängigkeiten
  runtime/                # whisper-server.exe, separat austauschbar
  models/                 # Whisper + Silero; niemals in Git
  licenses/               # Drittanbieter-Lizenzhinweise
  state/                  # Einstellungen/Diagnoselog; beim Start angelegt
  .git/                   # eigenständiges Quellcode-Repository
```

Der gesamte Projektordner kann verschoben werden. Es gibt keine Abhängigkeit zur übergeordneten VoiceLab-Anwendung, AutoTuner oder ComfyUI. Die Entwicklungs-`.venv` nach einem Umzug neu erstellen; die **EXE braucht sie nicht**. Aktivierten Windows-Autostart nach einem Umzug einmal aus-/einschalten, damit Windows den neuen Pfad kennt.

### Bedienung

- **`Ctrl+Alt+Space`** startet/stoppt eine Aufnahme, auch wenn LocalVoice nicht fokussiert ist.
- **Logo links oben** öffnet die Einstellungen: Mikrofon, Whisper-Variante, Sprache, GPU/CPU, Hotkey, Push-to-talk, Theme und Autostart. Die Dropdowns nutzen ab v0.2 feste Listen statt mitwandernder Menü-Popups. Scrollen über einem geschlossenen Dropdown ändert dessen Auswahl nicht mehr.
- **Am Ende schreiben:** Erst die gesamte Aufnahme, dann die Erkennung.
- **Vorschau in Abschnitten:** Ab v0.2 sind **4 Sekunden** das Standard-Ziel. Der erste Abschnitt wird bei einer Sprechpause ab 2 Sekunden freigegeben, ohne Pause spätestens nach 4 Sekunden. Weitere Abschnitte bevorzugen Pausen ab dem Ziel und warten höchstens 2 Sekunden zusätzlich. Das Modell und der Resampler werden schon parallel zur Aufnahme vorbereitet. **Die Rechenzeit kommt weiterhin hinzu** – kein echtes Token-Streaming und keine Garantie für Text nach exakt 4 Sekunden.
- Für den Satzanschluss erhält Whisper bis zu 400 Zeichen aus den vorherigen Abschnitten **derselben Aufnahme** als Kontext. Es wird kein überlappendes Audio doppelt eingefügt; vorhandene manuelle Korrekturen bleiben stehen. Die Kontextkopie enthält Erkennungstext, nicht nachträgliche Editoränderungen. Auf langsamer Hardware werden bereits wartende Abschnitte bis zu 30 Sekunden zusammengefasst, statt immer mehr kleine Inferenzaufrufe abzuarbeiten.
- **4–6 Sekunden** sind ein praktischer Kompromiss. 2 Sekunden sind auswählbar, aber experimentell: mehr Rechenaufwand und weniger Satzkontext. Für höchste Satz-/Zeichensetzungsqualität bleibt „Am Ende schreiben“ sinnvoll. Feste Zeitgrenzen können auch bei VAD mitten in ein Wort fallen.
- Das **Transkript ist editierbar**. „Kopieren“ kopiert den gesamten Inhalt.
- **„Einfügen in 3 s“:** anklicken und anschließend das gewünschte Textfeld fokussieren.
- **Haken ganz unten: „Direkt ins aktive Textfeld diktieren“.** Der Editor klappt ein, bleibt aber als Rückfallkopie verfügbar. Das Ziel-Textfeld fokussieren, dann den globalen Hotkey verwenden. Im Vorschau-Modus werden fertige Abschnitte eingefügt; im Endmodus der fertige Text.
- Bei **Push-to-talk mit Ctrl/Alt/Shift/Win** wartet das direkte Einfügen auf das Loslassen dieser Tasten. Für Einfügen schon während des Haltens eignet sich eine einzelne F-Taste, z. B. `F9`.
- **X** versteckt die App standardmäßig im Windows-Infobereich rechts unten. „Beenden“ im Tray-Menü beendet auch den eigenen Whisper-Prozess. Ohne verfügbaren Tray wird normal beendet.
- Maximale Aufnahme: **10 Minuten**. Gerätedefekte, Audioaussetzer und überfüllte Verarbeitungswarteschlangen werden angezeigt, nicht still übergangen.

### Update von v0.1

Ein gespeicherter v0.1-Standard von 8 Sekunden wird beim Laden einmalig auf 4 Sekunden migriert; Modellwahl (auch Turbo), Mikrofon, Theme usw. bleiben erhalten. Abweichende alte Zeitwerte bleiben bestehen. Wer ausdrücklich 8 Sekunden bevorzugt, kann sie in v0.2 erneut einstellen; die Versionsmarkierung verhindert eine erneute Migration. Details: [CHANGELOG.md](CHANGELOG.md).

## Modelle und Hardware

Im lokalen Projekt sind das übernommene **Whisper large-v3**, **Silero v6.2.0** sowie das kleine **Tiny-Testmodell** vorhanden. Die Dateien werden nicht ins Repository aufgenommen.

Weitere Varianten lassen sich in **Einstellungen → Audio & Modelle** auswählen und bewusst herunterladen: Tiny, Base, Small, Medium, Large v3, Large v3 Turbo und Q5-Varianten. Downloads kommen von Hugging Face, werden an eine konkrete Revision gebunden und **vor Installation mit SHA-256 und Dateigröße geprüft**. Abgebrochene Downloads hinterlassen kein scheinbar vollständiges Modell. Ohne Internet können bereits vorhandene Modelle normal verwendet werden.

Large v3 liefert hohe Qualität, braucht aber viel mehr Speicher/Rechenzeit als Tiny/Turbo. Andere lokal laufende Modelle können die GPU belegen. LocalVoice beendet keine fremden Prozesse und wechselt **nicht heimlich auf CPU**, wenn die ausgewählte GPU nicht funktioniert. In diesem Fall CPU oder ein kleineres Modell auswählen.

**GPU-IDs werden direkt aus Vulkan ermittelt.** Sie sind nicht mit CUDA/HIP/WMI-Gerätenummern austauschbar. CPU ist unabhängig davon auswählbar. Silero-VAD läuft auf CPU. Ein Mikrofon wird über Host-API + Gerätenamen gespeichert, nicht über einen instabilen Listenindex. „Systemstandard“ folgt der Standardquelle; fehlt ein explizit gewähltes Mikrofon, wird nicht unbemerkt ein anderes benutzt. Bei nachträglich angeschlossenen Geräten ggf. LocalVoice neu starten, falls PortAudio die Liste noch zwischenspeichert.

VAD und ein vorgeschalteter Digitalstille-Filter reduzieren Halluzinationen, können sie bei Geräuschen, Musik, kurzen Wörtern oder Dialekt aber nicht vollständig verhindern. Ausgabe bei wichtigen Texten gegenlesen.

## Datenschutz und Grenzen

- Audio wird im Arbeitsspeicher verarbeitet; keine Aufnahmedateien und keine dauerhafte Transkripthistorie. Der sichtbare Editor ist die Sitzungskopie und geht beim Beenden verloren.
- Native Diagnosen stehen in `state/backend.log` und werden beim nächsten Backend-Start überschrieben. Der lokale native Server bindet ausschließlich an **127.0.0.1** auf einem zufälligen Port und verwendet einen zufälligen URL-Präfix. Das ist keine Sicherheitsgrenze gegenüber anderen Prozessen desselben Benutzerkontos.
- Windows-Einfügen nutzt kurzfristig die Zwischenablage und `Ctrl+V`, unterstützt dadurch auch Umlaute, Emoji und Zeilenumbrüche. Vorherige MIME-Inhalte werden nach 750 ms wiederhergestellt, **sofern die Zwischenablage nicht inzwischen verändert wurde**. Für diesen temporären Inhalt werden Windows-Markierungen gegen Verlauf/Cloud-Synchronisierung gesetzt; fremde Clipboard-Manager können dennoch mitlesen. „Kopieren“ ist dagegen eine normale, dauerhafte Zwischenablage-Aktion.
- Die App stiehlt beim direkten Diktieren **nicht den Fokus**. Ist ein anderes Fenster aktiv, wird nicht blind dorthin geschrieben; der Text bleibt im aufklappbaren Editor. Ein Wechsel zwischen Textfeldern innerhalb desselben Fensters lässt sich nicht zuverlässig erkennen.
- Admin-/UAC-Fenster, Passwortfelder, geschützte Anwendungen und Programme mit eigenen Eingabemethoden können Einfügen blockieren. Eine Garantie für buchstäblich *jedes* Textfeld ist technisch nicht möglich. Im Zweifel Kopieren verwenden. LocalVoice nicht pauschal als Administrator starten.
- Die EXE ist derzeit **nicht codesigniert**. Windows SmartScreen kann bei einer späteren heruntergeladenen Version warnen.

## Plattformstatus

| Plattform | Stand |
|---|---|
| Windows 11 x64 | Python-3.14-EXE gebaut; echte Mikrofonaufnahme, Hotkey, Unicode-Einfügen, CPU- und Vulkan-Erkennung lokal geprüft. |
| Linux X11 | Portabler Python-Code; `xdotool`, PortAudio und ein passend gebauter whisper-server nötig. Noch kein realer Systemtest hier. |
| Linux Wayland | Aufnahme/Editor/Kopieren als Basis vorgesehen. Globale Hotkeys und automatisches Einfügen benötigen eine eigene Portal-/Compositor-Integration und sind **noch nicht unterstützt**. |
| macOS | Qt/Python-Grundlage und Metal-Runtime-Build vorgesehen. Mikrofon-, Bedienungshilfen-/Eingabeüberwachungsrechte erforderlich. Noch kein realer Systemtest, signiertes `.app` oder Installer. |

Autostart ist aktuell nur für Windows implementiert. Native Pakete müssen auf dem jeweiligen Betriebssystem gebaut werden; eine Windows-EXE ist kein macOS-/Linux-Paket.

## Entwicklung: Python 3.14, kein Node

**Getestet mit CPython 3.14.5, pip 26.2.1 und PyInstaller 6.22.3.** Kein Python-3.12-Unterbau in der Anwendung, kein Electron/Node, kein Cloud-SDK. Der native Whisper-Prozess bleibt bewusst vom Python-/GUI-Code getrennt.

```powershell
.\Setup.ps1
.venv\Scripts\python.exe main.py
.venv\Scripts\python.exe -m pytest -q
.\Build.ps1
```

`Setup.ps1` verlangt eine 3.14-Umgebung und aktualisiert deren pip. Für einen reproduzierbaren Windows-Abhängigkeitsstand alternativ `pip install -r requirements-windows.lock.txt` verwenden.

- `pyproject.toml`: Python-Mindestversion und verträgliche Abhängigkeitsbereiche.
- `requirements*.txt`: konkret getestete Versionen; Windows-Lock als vollständiger Build-Snapshot.
- `.github/workflows/tests.yml`: vorbereitete Tests für Windows/Linux/macOS mit Python 3.14; zusätzlicher **nicht blockierender 3.15-dev-Frühwarnjob**. Diese Remote-Jobs sind noch nicht gelaufen.
- Dependabot-Konfiguration für monatliche Abhängigkeits-/CI-Updates. Updates werden getestet und gelockt, nicht automatisch ungeprüft installiert.
- Python-Free-Threading-Builds (`3.14t`) werden nicht als unterstützt behauptet.

Native Runtime aus gepinntem Quellcode bauen: [runtime/README.md](runtime/README.md). Modelle und fertige Binärdateien sind absichtlich nicht Teil eines frischen Git-Clones.

### Zusätzliche lokale Prüfungen

```powershell
.venv\Scripts\python.exe scripts/check_windows_integration.py
.venv\Scripts\python.exe scripts/check_backend.py --audio <16kHz-Mono-PCM16-Testdatei.wav> --model tiny --device cpu
.\LocalVoice.exe --smoke-test
.\LocalVoice.exe --smoke-test --smoke-audio <Testdatei.wav> --smoke-model tiny
.venv\Scripts\python.exe scripts/check_portable.py --audio <Testdatei.wav>
.venv\Scripts\python.exe scripts/check_dropdown.py
.venv\Scripts\python.exe scripts/check_preview.py --audio <Testdatei.wav> --model large-v3-turbo --device cpu --language de
.venv\Scripts\python.exe scripts/check_preview_live.py --audio <Testdatei.wav> --device cpu
```

Der Windows-Integrationstest öffnet ein eigenes Wegwerf-Textfenster und nimmt etwa 0,3 Sekunden vom Standardmikrofon auf, **ohne die Samples zu speichern**. Nicht in bestehende fremde Fenster tippen lassen. Diagnoseberichte/Screenshots landen lokal in `reports/` bzw. `state/`, nicht in Git.

## Lizenz

Eigener Anwendungscode und das eigens gezeichnete, reproduzierbare Logo: **MIT**. Die Lizenzen von Whisper, Modellen, Qt/PySide, Python und weiteren Abhängigkeiten gelten unabhängig davon. Siehe [THIRD_PARTY.md](THIRD_PARTY.md). Vor einer öffentlichen Binärveröffentlichung Lizenzbeilagen, Quellcodebereitstellung/Angebote, Codesignierung und native Plattformtests abschließend prüfen.
