# Changelog

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
- Turbo-Vergleich mit lokalen englischen/deutschen Sprachfixtures sowie eine zeitgetreu eingespeiste deutsche Aufnahme durch GUI → Recorder → Whisper → Editor. Details und Grenzen in `TESTING.md`.

## v0.1.0 — 2026-09-22

Erste Windows-Version auf Python 3.14: Whisper/Silero, Aufnahme, globaler Hotkey/PTT, finales und segmentiertes Diktat, editierbares Transkript, direktes Einfügen, Tray/Autostart, Themes, Modell-/CPU-/GPU-/Mikrofonauswahl, geprüftes Herunterladen, Logo, eigenständiges Git-Repository und portable EXE.

Der Ausgangsstand bleibt über den lokalen annotierten Tag **`v0.1`** erreichbar. Keine Veröffentlichung/kein Push durch die Versionsmarkierungen.
