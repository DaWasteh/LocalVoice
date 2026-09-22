import io
import json
import threading
import wave
from dataclasses import replace
import numpy as np
import pytest
from localvoice.config import Settings
from localvoice.audio import Chunker, resolve_microphone, Recorder
from localvoice.backend import Whisper, wav_bytes, clean_text
from localvoice.integration import parse_hotkey
from localvoice.models import model_path, download


def test_settings_roundtrip_and_corruption(tmp_path):
    settings = Settings(microphone='WASAPI|RODE', direct=True, theme='light')
    settings.save(tmp_path)
    assert Settings.load(tmp_path) == settings
    (tmp_path / 'state/settings.json').write_text('{broken', encoding='utf-8')
    assert Settings.load(tmp_path) == Settings()


def test_settings_wrong_types_are_ignored(tmp_path):
    (tmp_path / 'state').mkdir()
    (tmp_path / 'state/settings.json').write_text(json.dumps({'direct': 'false', 'chunk_seconds': 999, 'theme': 'invalid'}))
    loaded = Settings.load(tmp_path)
    assert loaded.direct is False and loaded.chunk_seconds == 20 and loaded.theme == 'system'


def test_chunker_lossless_and_forced_boundary():
    chunker = Chunker(seconds=4, rate=100)
    chunks = []
    original = np.ones(1750, dtype=np.float32)
    for block in np.array_split(original, 35):
        result = chunker.feed(block)
        if result is not None:
            chunks.append(result)
    chunks.append(chunker.flush())
    assert [len(x) for x in chunks] == [400, 600, 600, 150]
    np.testing.assert_array_equal(np.concatenate(chunks), original)
    assert chunker.flush() is None


def test_chunker_uses_pause():
    chunker = Chunker(seconds=4, rate=100)
    assert chunker.feed(np.ones(380)) is None
    chunk = chunker.feed(np.zeros(40))
    assert len(chunk) == 420


def test_short_first_chunk_and_early_pause_are_lossless():
    chunker = Chunker(seconds=4, rate=100)
    voice, pause = np.ones(200), np.zeros(40)
    assert chunker.feed(voice) is None
    chunk = chunker.feed(pause)
    np.testing.assert_array_equal(chunk, np.concatenate([voice, pause]))
    assert not chunker.first
    assert chunker.feed(np.ones(550)) is None
    assert len(chunker.feed(np.ones(50))) == 600


def test_silent_chunks_do_not_consume_quick_first_result():
    chunker = Chunker(seconds=4, rate=100)
    assert len(chunker.feed(np.zeros(200))) == 200
    assert chunker.first
    assert chunker.feed(np.ones(350)) is None
    assert len(chunker.feed(np.ones(50))) == 400
    assert chunker.feed(np.array([])) is None


def test_v01_default_migration_preserves_other_preferences(tmp_path):
    path = tmp_path / 'state/settings.json'
    path.parent.mkdir()
    path.write_text(json.dumps({'model': 'large-v3-turbo', 'microphone': 'WASAPI|RODE', 'chunk_seconds': 8}))
    settings = Settings.load(tmp_path)
    assert settings.chunk_seconds == 4 and settings.config_version == 2
    assert settings.model == 'large-v3-turbo' and settings.microphone == 'WASAPI|RODE'
    settings.chunk_seconds = 8
    settings.save(tmp_path)
    assert Settings.load(tmp_path).chunk_seconds == 8  # deliberate v0.2 value
    path.write_text(json.dumps({'chunk_seconds': 6}))
    assert Settings.load(tmp_path).chunk_seconds == 6  # custom v0.1 value


def test_pcm_wav():
    data = wav_bytes(np.array([-2, -.5, 0, .5, 2], dtype=np.float32))
    with wave.open(io.BytesIO(data)) as wav:
        assert wav.getframerate() == 16000 and wav.getnchannels() == 1
        samples = np.frombuffer(wav.readframes(5), dtype='<i2')
        assert list(samples) == [-32767, -16383, 0, 16383, 32767]


def test_silence_does_not_start_model(tmp_path, monkeypatch):
    engine = Whisper(tmp_path)
    def forbidden(_):
        pytest.fail('Digital silence must not load Whisper')
    monkeypatch.setattr(engine, 'start', forbidden)
    for audio in (np.zeros(16000), np.zeros(500), np.full(16000, np.nan)):
        assert engine.transcribe(audio, Settings()) == ''
    engine.close()


def test_backend_missing_files_actionable(tmp_path):
    with pytest.raises(FileNotFoundError, match='Runtime'):
        Whisper(tmp_path).start(Settings())


def test_model_path_allowlist(tmp_path):
    assert model_path(tmp_path, 'large-v3').name == 'ggml-large-v3.bin'
    with pytest.raises(ValueError):
        model_path(tmp_path, '../escape')
    with pytest.raises(ValueError):
        download(tmp_path, '../escape', lambda *_: None, threading.Event())


def test_hotkeys():
    assert parse_hotkey('ctrl+alt+space') == (3, 32)
    assert parse_hotkey('F9') == (0, 120)
    assert parse_hotkey('ctrl+shift+d') == (6, 68)
    for value in ('x', 'ctrl', 'ctrl+a+b', 'ctrl+F25', 'ctrl+🐢'):
        with pytest.raises(ValueError):
            parse_hotkey(value)


def test_backend_only_forwards_bounded_preview_prompt(tmp_path, monkeypatch):
    engine = Whisper(tmp_path)
    engine.url = 'http://127.0.0.1/not-used'
    monkeypatch.setattr(engine, 'start', lambda *_: None)
    calls = []
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'text': 'Hallo'}
    def post(*args, **kwargs):
        calls.append(kwargs['data'])
        return Response()
    monkeypatch.setattr(engine.session, 'post', post)
    audio = np.ones(16000, np.float32)
    engine.transcribe(audio, Settings(mode='preview'), prompt='x' * 900)
    engine.transcribe(audio, Settings(mode='final'), prompt='must not be used')
    assert calls[0]['prompt'] == 'x' * 400 and calls[0]['vad'] == 'true'
    assert calls[1]['prompt'] == ''
    engine.close()


def test_cleaning_does_not_blacklist_real_words():
    assert clean_text('[BLANK_AUDIO] [_BEG_] Hallo  Welt!') == 'Hallo Welt!'
    assert clean_text('Vielen Dank fürs Zuschauen.') == 'Vielen Dank fürs Zuschauen.'


def test_missing_microphone_does_not_silently_fallback(monkeypatch):
    monkeypatch.setattr('localvoice.audio.microphones', lambda: [('host|mic', 'Mic', 2)])
    assert resolve_microphone('host|mic') == 2
    assert resolve_microphone('') is None
    with pytest.raises(RuntimeError, match='Mikrofon'):
        resolve_microphone('disconnected')


def test_resampling_duration_and_finiteness():
    rec = Recorder(Settings(), lambda _: None, lambda _: None, lambda _: None)
    rec.rate = 48000
    audio = np.sin(np.arange(48000) * 2 * np.pi * 440 / 48000).astype(np.float32)
    output = rec._resample(audio)
    assert len(output) == 16000 and np.isfinite(output).all()


def test_changed_target_refuses_injection(monkeypatch):
    import localvoice.integration as integration
    monkeypatch.setattr(integration, 'foreground', lambda: 456)
    with pytest.raises(RuntimeError, match='Zielfenster'):
        integration.send_text('do not type', 123)
