"""Desktop entry point. Models/runtime/settings resolve beside the executable."""
import argparse
import json
import sys
from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox
from localvoice.config import root_dir
from localvoice import __version__


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tray', action='store_true')
    parser.add_argument('--smoke-test', action='store_true', help='Show UI, write diagnostics/screenshot and exit without recording')
    parser.add_argument('--smoke-audio', help='Optional 16 kHz mono PCM16 WAV for real CPU inference during smoke test')
    parser.add_argument('--smoke-model', default='tiny')
    args = parser.parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName('LocalVoice')
    app.setOrganizationName('LocalVoice')
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    root = root_dir()
    state = root / 'state'
    try:
        state.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(state / 'app.lock'))
        lock.setStaleLockTime(0)
        import hashlib
        server_name = 'localvoice-' + hashlib.sha256(str(root).lower().encode()).hexdigest()[:20]
        if not lock.tryLock(100):
            socket = QLocalSocket()
            socket.connectToServer(server_name)
            if not socket.waitForConnected(1000):
                QMessageBox.information(None, 'LocalVoice', 'LocalVoice läuft bereits. Bitte das Symbol im Infobereich öffnen.')
            else:
                socket.write(b'show')
                socket.waitForBytesWritten(1000)
            return 0
    except OSError as exc:
        QMessageBox.critical(None, 'LocalVoice', f'Der Programmordner muss beschreibbar sein:\n{exc}')
        return 1
    from localvoice.ui import Window
    window = Window(root, args.tray)
    server = QLocalServer()
    QLocalServer.removeServer(server_name)
    server.listen(server_name)
    def connected():
        connection = server.nextPendingConnection()
        window.show_window()
        connection.disconnectFromServer()
        connection.deleteLater()
    server.newConnection.connect(connected)
    if args.smoke_test:
        def run_smoke():
            from localvoice.audio import microphones
            from localvoice.devices import gpu_devices
            window.show_window()
            window.grab().save(str(state / 'smoke-ui.png'))
            import numpy as np
            from localvoice.audio import Recorder
            from localvoice.config import Settings
            recorder = Recorder(Settings(), lambda _: None, lambda _: None, lambda _: None)
            recorder.rate = 48000
            report = {'version': __version__, 'python': sys.version, 'gpus': gpu_devices(), 'microphones': microphones(), 'root': str(root),
                      'model_exists': (root / 'models/ggml-large-v3.bin').is_file(),
                      'hotkey_registered': window.hotkey.registered, 'window_size': [window.width(), window.height()],
                      'resample_samples': len(recorder._resample(np.zeros(48000, np.float32)))}
            if args.smoke_audio:
                import wave
                with wave.open(args.smoke_audio) as wav:
                    assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
                    audio = np.frombuffer(wav.readframes(wav.getnframes()), '<i2').astype(np.float32) / 32768
                report['transcript'] = window.engine.transcribe(audio, Settings(model=args.smoke_model, device='cpu', language='en'))
            (state / 'smoke-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
            window.quit()
        def finish_smoke():
            try:
                run_smoke()
            except Exception:
                import traceback
                (state / 'smoke-error.log').write_text(traceback.format_exc(), encoding='utf-8')
                window.quit()
                app.exit(1)
        QTimer.singleShot(1500, finish_smoke)
    result = app.exec()
    server.close()
    lock.unlock()
    return result


if __name__ == '__main__':
    raise SystemExit(main())
