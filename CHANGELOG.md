# Changelog

## v0.3.0 — 2026-09-23

Erste öffentliche Version. Schwerpunkt: Kein diktierter Text und kein aufgenommenes Audio geht mehr still verloren.

### Fehlerbehebungen
- **10-Minuten-Limit:** Die Aufnahme stoppt jetzt automatisch und wird transkribiert. Bisher wurde im Modus „Am Ende schreiben“ die gesamte Aufnahme verworfen.
- **Audio-Aussetzer:** Ein einzelner Puffer-Überlauf bricht die Aufnahme nicht mehr ab und verwirft nichts mehr. Es erscheint nur ein Hinweis, die Stelle zu prüfen.
- **Direktes Diktieren:** Scheitert das Einfügen (z. B. weil das Fenster gewechselt wurde), läuft Aufnahme und Erkennung weiter. Der Text landet vollständig im Transkript. Bisher endete die Aufnahme und das restliche Audio ging verloren.
- **Zwischenablage:** Zwei Einfügungen kurz hintereinander überschreiben die ursprüngliche Zwischenablage nicht mehr mit dem ersten Diktatabschnitt. Die Wiederherstellung wartet 2 statt 0,75 Sekunden, damit langsame Zielprogramme (z. B. Remote Desktop) nicht den alten Inhalt einfügen.
- **Whisper-Prozess:** Stürzt LocalVoice ab oder wird es im Task-Manager beendet, endet `whisper-server.exe` jetzt mit (Windows-Job-Objekt) und belegt keinen RAM/VRAM mehr.
- **Modell-Download:** Ein Fehler ohne Meldungstext (z. B. Datei nicht mehr auf Hugging Face) wurde als „Download vollständig“ angezeigt.
- Fehler in der Audioverarbeitung werden gemeldet, statt die Aufnahme stumm hängen zu lassen.

### Verbesserungen
- Erster Start wählt automatisch eine dedizierte GPU, sonst eine integrierte, sonst die CPU (bisher fest „Vulkan 0“).
- CPU-Threads richten sich nach dem Prozessor (2–8) statt fest 8.
- Hotkeys aus Shift + Buchstabe/Leertaste werden abgelehnt, weil sie normales Tippen blockieren würden.
- Taskleiste und Desktop werden nie als Diktierziel gemerkt.
- Autostart-Eintrag wird nach einem Umzug des Ordners beim nächsten Start automatisch aktualisiert.
- Einstellungsdialoge werden nach dem Schließen freigegeben.

### Release
- `Build.ps1` erzeugt zusätzlich `dist/LocalVoice-v<version>-windows-x64.zip` mit SHA-256-Datei. Die Visual-C++-Laufzeit für `whisper-server.exe` liegt bei, eine separate VC++-Installation ist nicht mehr nötig.
- `scripts/check_portable.py --package` prüft das fertige ZIP in einem frischen Ordner mit echter Erkennung.
- README, Tests und Drittanbieter-Hinweise für die Veröffentlichung überarbeitet.

## v0.2.0 — 2026-09-22

### Bedienung
- Stabile Listen-Popups statt Qt-Menü-Popups: keine Positionierung relativ zum ausgewählten Eintrag, kein automatisches Randscrollen beim Darüberfahren.
- Explizite Zeilenhöhen/Viewport-Mindesthöhe verhindern abgeschnittene oder verschobene Maus-Trefferbereiche; alle Dropdowns verwenden denselben Fix.
- Mausrad über einer geschlossenen Auswahl ändert nicht mehr versehentlich Diktiermodus, Mikrofon oder Modell. Tastatursteuerung und Scrollen der offenen Liste bleiben möglich.
- Versionsnummer im Fenstertitel, Footer und EXE-Diagnosebericht.

### Schnellere erste Vorschau
- Standard-Ziel **4 statt 8 Sekunden**. Erster Abschnitt an einer Pause ab 2 Sekunden oder spätestens nach 4 Sekunden; spätere Abschnitte an einer Pause ab Zielzeit oder spätestens Ziel + 2 Sekunden.
- Modell/Audio-Resampler werden parallel zur Aufnahme geladen, nicht erst beim ersten fertigen Abschnitt.
- Bis zu 400 Zeichen Erkennungskontext ausschließlich aus der aktuellen Aufnahme helfen beim Satzanschluss. VAD und Digitalstille-Sperre bleiben aktiv.
- Bereits wartende Audioblöcke werden auf langsamer Hardware verlustfrei zusammengefasst (maximal 30 Sekunden pro zusammengefasstem Vorschauauftrag). Keine doppelten Audiosamples/Text-Einfügungen durch Audioüberlappung.
- Einstellbarer Bereich 2–20 Sekunden; 4–6 Sekunden empfohlen, 2 Sekunden experimentell. Rechenzeit kommt zur Pufferdauer hinzu; vollständige Sätze sind bei kurzen Ausschnitten nicht garantiert.
- Ein alter gespeicherter Standardwert von 8 Sekunden wird auf 4 migriert. Andere Zeitwerte und alle übrigen Einstellungen bleiben erhalten. Bewusst in v0.2 gespeicherte 8 Sekunden bleiben erhalten.

### Prüfungen
- Zusätzliche Regressionstests für Maus-Hitboxen, Popup-Position, Tastatur/Mausrad, Einstellungs-Migration, Audioerhaltung, Kontextbegrenzung und Zusammenfassung wartender Abschnitte.
- Native Dropdown-Prüfung bei normaler und 150%-Skalierung.
- Turbo-Vergleich mit englischen/deutschen Sprachproben sowie eine zeitgetreu eingespeiste deutsche Aufnahme durch GUI → Recorder → Whisper → Editor. Details und Grenzen in `TESTING.md`.

## v0.1.0 — 2026-09-22

Erste Windows-Version auf Python 3.14: Whisper/Silero, Aufnahme, globaler Hotkey/PTT, finales und segmentiertes Diktat, editierbares Transkript, direktes Einfügen, Tray/Autostart, Themes, Modell-/CPU-/GPU-/Mikrofonauswahl, geprüftes Herunterladen, Logo und portable EXE.
