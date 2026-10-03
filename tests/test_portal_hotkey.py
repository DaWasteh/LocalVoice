"""Portal protocol tests use a fake bus; never open desktop consent dialogs in CI."""
import asyncio
import os
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
dbus = pytest.importorskip('dbus_next')
from dbus_next import MessageType, Variant
from PySide6.QtWidgets import QApplication
from localvoice.portal_hotkey import PortalHotkey, SERVICE, PATH, INTERFACE
from localvoice import integration


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def signal(portal, member, body, path=PATH, interface=INTERFACE, sender=':1.7'):
    portal.message(SimpleNamespace(message_type=MessageType.SIGNAL, sender=sender,
                                   path=path, interface=interface, member=member, body=body))


@pytest.mark.parametrize('mods,key,trigger', [(3, 32, 'CTRL+ALT+space'), (0, 120, 'F9'),
                                             (6, 68, 'CTRL+SHIFT+d'), (8, 32, 'LOGO+space')])
def test_trigger(app, mods, key, trigger):
    assert PortalHotkey(mods, key).trigger == trigger


def test_only_our_shortcut_and_sender_can_activate_and_repeats_are_ignored(app):
    portal = PortalHotkey(3, 32)
    portal.owner, portal.session = ':1.7', PATH + '/session/ours'
    body = [portal.session, portal.shortcut_id, 1, {}]
    events = []
    portal.pressed.connect(lambda: events.append('press'))
    portal.released.connect(lambda: events.append('release'))
    signal(portal, 'Activated', body, sender=':1.99')
    signal(portal, 'Activated', ['/other', portal.shortcut_id, 1, {}])
    signal(portal, 'Activated', [portal.session, 'other', 1, {}])
    signal(portal, 'Activated', body, interface='untrusted')
    signal(portal, 'Deactivated', body)
    assert events == []
    signal(portal, 'Activated', body)
    signal(portal, 'Activated', body)
    signal(portal, 'Deactivated', body)
    signal(portal, 'Deactivated', body)
    assert events == ['press', 'release']
    portal.close()
    signal(portal, 'Activated', body)
    assert events == ['press', 'release']


class Bus:
    unique_name = ':1.42'
    def __init__(self, code=0, bound=True, pending=False):
        self.code, self.bound, self.pending = code, bound, pending
        self.calls = []
        self.disconnected = False
    async def connect(self): return self
    def add_message_handler(self, handler): self.handler = handler
    async def call(self, msg):
        self.calls.append(msg)
        body = []
        if msg.member == 'GetNameOwner': body = [':1.7']
        elif msg.member in ('CreateSession', 'BindShortcuts'):
            path = PATH + '/request/1_42/' + msg.body[-1]['handle_token'].value
            body = [path]
            if msg.member == 'CreateSession':
                results = {'session_handle': Variant('s', PATH + '/session/1_42/test')}
            else:
                self.binding = msg.body
                results = {'shortcuts': Variant('a(sa{sv})', [[msg.body[1][0][0],
                    {'trigger_description': Variant('s', 'Ctrl+Alt+Space')}]] if self.bound else [])}
            if not (self.pending and msg.member == 'BindShortcuts'):
                # Response deliberately arrives before the method return.
                self.handler(SimpleNamespace(message_type=MessageType.SIGNAL, sender=':1.7', path=path,
                    interface='org.freedesktop.portal.Request', member='Response', body=[self.code, results]))
        return SimpleNamespace(message_type=MessageType.METHOD_RETURN, body=body)
    async def wait_for_disconnect(self):
        await asyncio.Future()
    def disconnect(self): self.disconnected = True


@pytest.mark.parametrize('mode', ['success', 'denied', 'empty', 'pending'])
def test_portal_requests_and_cleanup(app, monkeypatch, mode):
    from dbus_next import aio
    bus = Bus(code=1 if mode == 'denied' else 0, bound=mode != 'empty', pending=mode == 'pending')
    monkeypatch.setattr(aio, 'MessageBus', lambda: bus)
    portal = PortalHotkey(3, 32)
    status = []
    portal.status.connect(lambda *args: status.append(args))
    async def check():
        task = asyncio.create_task(portal.listen())
        if mode in ('denied', 'empty'):
            with pytest.raises(RuntimeError, match='abgebrochen|kein Tastenkürzel'):
                await asyncio.wait_for(task, 2)
        else:
            for _ in range(100):
                if status or mode == 'pending' and hasattr(bus, 'binding'):
                    break
                await asyncio.sleep(.001)
            if mode == 'success':
                assert status == [(True, 'Hotkey bereit: Ctrl+Alt+Space')]
                assert bus.binding[1][0][1]['preferred_trigger'].value == 'CTRL+ALT+space'
            else:
                assert status == []
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert bus.disconnected and not portal.pending
        if mode != 'denied':
            assert any(c.member == 'Close' and c.interface == 'org.freedesktop.portal.Session' for c in bus.calls)
        if mode == 'pending':
            assert any(c.member == 'Close' and c.interface == 'org.freedesktop.portal.Request' for c in bus.calls)
    asyncio.run(check())


def test_closed_session_releases_push_to_talk(app):
    portal = PortalHotkey(3, 32)
    portal.owner, portal.session, portal.held = ':1.7', '/session/ours', True
    events = []
    portal.task = SimpleNamespace(cancel=lambda: events.append('cancel'))
    portal.released.connect(lambda: events.append('release'))
    portal.status.connect(lambda registered, _: events.append(registered))
    signal(portal, 'Closed', [{}], path=portal.session, interface='org.freedesktop.portal.Session')
    assert events == ['cancel', 'release', False] and not portal.held


def test_registration_routes_wayland_and_ignores_late_status(app, monkeypatch):
    monkeypatch.setattr(integration, 'IS_WINDOWS', False)
    monkeypatch.setattr(integration, 'sys', SimpleNamespace(platform='linux'))
    monkeypatch.setenv('XDG_SESSION_TYPE', 'wayland')
    monkeypatch.setattr(PortalHotkey, 'start', lambda self: None)
    events = []
    hotkey = integration.Hotkey(app, lambda: events.append('press'), lambda: events.append('release'), events.append)
    hotkey.register('ctrl+alt+space')
    portal = hotkey.portal
    assert not hotkey.registered
    portal.status.emit(True, 'ready')
    assert hotkey.registered and events[-1] == 'ready'
    portal.pressed.emit()
    portal.released.emit()
    assert events[-2:] == ['press', 'release']
    hotkey.close()
    portal.status.emit(True, 'late')
    portal.pressed.emit()
    assert not hotkey.registered and hotkey.portal is None and events[-1] == 'release'
