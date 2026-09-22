import hashlib
import threading
import pytest
from localvoice.models import download, VAD_FILE


class Response:
    def __init__(self, meta=None, content=b''):
        self.meta, self.content = meta, content
    def raise_for_status(self): pass
    def json(self): return self.meta
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def iter_content(self, _): yield self.content


class Session:
    def __init__(self, expected=None):
        self.content = b'a small model fixture'
        self.expected = expected or hashlib.sha256(self.content).hexdigest()
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def get(self, url, **kwargs):
        self.calls.append(url)
        if '/api/' in url:
            return Response({'sha': 'fixed-revision', 'siblings': [{'rfilename': VAD_FILE,
                'size': len(self.content), 'lfs': {'sha256': self.expected}}]})
        return Response(content=self.content)


def test_download_pinned_revision_checksum_and_vad_repo(tmp_path, monkeypatch):
    session = Session()
    monkeypatch.setattr('localvoice.models.requests.Session', lambda: session)
    download(tmp_path, VAD_FILE, lambda *_: None, threading.Event())
    assert (tmp_path / 'models' / VAD_FILE).read_bytes() == session.content
    assert 'ggml-org/whisper-vad/resolve/fixed-revision/' in session.calls[-1]
    assert not list(tmp_path.rglob('*.part'))


def test_corrupt_download_never_installed(tmp_path, monkeypatch):
    monkeypatch.setattr('localvoice.models.requests.Session', lambda: Session('0' * 64))
    with pytest.raises(ValueError, match='Prüfsumme'):
        download(tmp_path, VAD_FILE, lambda *_: None, threading.Event())
    assert not (tmp_path / 'models' / VAD_FILE).exists()
    assert not list(tmp_path.rglob('*.part'))


def test_cancel_removes_partial(tmp_path, monkeypatch):
    monkeypatch.setattr('localvoice.models.requests.Session', Session)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(InterruptedError):
        download(tmp_path, VAD_FILE, lambda *_: None, cancel)
    assert not list(tmp_path.rglob('*.part'))
