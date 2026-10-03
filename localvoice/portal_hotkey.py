"""Wayland global shortcuts via the desktop's permission-aware XDG portal."""
import asyncio
import threading
import uuid

from PySide6.QtCore import QObject, Signal

SERVICE = 'org.freedesktop.portal.Desktop'
PATH = '/org/freedesktop/portal/desktop'
INTERFACE = 'org.freedesktop.portal.GlobalShortcuts'


class PortalHotkey(QObject):
    pressed = Signal()
    released = Signal()
    status = Signal(bool, str)

    def __init__(self, mods, key):
        super().__init__()
        trigger = '+'.join(name for bit, name in ((2, 'CTRL'), (1, 'ALT'), (4, 'SHIFT'), (8, 'LOGO')) if mods & bit)
        key_name = 'space' if key == 32 else f'F{key - 0x70 + 1}' if key >= 0x70 else chr(key).lower()
        self.trigger = trigger + ('+' if trigger else '') + key_name
        # A changed preference is a new action, not a silently reused old portal binding.
        self.shortcut_id = f'record-{mods}-{key}'
        self.closed = self.held = False
        self.loop = self.task = self.bus = None
        self.session = self.owner = ''
        self.pending = {}
        self.thread = threading.Thread(target=self.run, name='localvoice-hotkey', daemon=True)

    def start(self):
        self.thread.start()

    def run(self):
        try:
            asyncio.run(self.listen())
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if not self.closed:
                self.status.emit(False, f'Wayland-Hotkey nicht verfügbar: {str(exc) or type(exc).__name__}. Aufnahme-Button verfügbar.')

    async def call(self, member, signature='', body=None, path=PATH, interface=INTERFACE, destination=SERVICE):
        from dbus_next import Message, MessageType
        reply = await asyncio.wait_for(self.bus.call(Message(destination=destination, path=path,
            interface=interface, member=member, signature=signature, body=body or [])), 5)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(reply.body[0] if reply.body else reply.error_name)
        return reply.body

    async def request(self, member, signature, body):
        from dbus_next import Variant
        token = 'lv' + uuid.uuid4().hex
        path = f'{PATH}/request/{self.bus.unique_name[1:].replace(".", "_")}/{token}'
        body[-1]['handle_token'] = Variant('s', token)
        response = self.loop.create_future()
        self.pending[path] = response
        try:
            reply = await self.call(member, signature, body)
            if reply != [path]:
                raise RuntimeError('Unerwarteter Portal-Antwortpfad')
            code, results = await asyncio.wait_for(response, 120)
            if code != 0:
                raise RuntimeError('Tastenkürzel-Freigabe abgebrochen oder abgelehnt')
            return results
        finally:
            self.pending.pop(path, None)
            if response.cancelled():
                try:
                    await self.call('Close', path=path, interface='org.freedesktop.portal.Request')
                except Exception:
                    pass  # request may already have been closed by the desktop

    def message(self, msg):
        from dbus_next import MessageType
        if self.closed or msg.message_type != MessageType.SIGNAL or msg.sender != self.owner:
            return
        if msg.interface == 'org.freedesktop.portal.Request' and msg.member == 'Response':
            future = self.pending.get(msg.path)
            if future is not None and not future.done():
                future.set_result(msg.body)
        elif (msg.path == PATH and msg.interface == INTERFACE and len(msg.body) >= 2
              and msg.body[:2] == [self.session, self.shortcut_id]):
            if msg.member == 'Activated' and not self.held:
                self.held = True
                self.pressed.emit()
            elif msg.member == 'Deactivated' and self.held:
                self.held = False
                self.released.emit()
        elif msg.path == self.session and msg.interface == 'org.freedesktop.portal.Session' and msg.member == 'Closed':
            self.task.cancel()
            if self.held:
                self.held = False
                self.released.emit()
            self.status.emit(False, 'Wayland-Hotkey vom Desktop beendet. Bitte LocalVoice neu starten.')

    async def listen(self):
        from dbus_next import Variant
        from dbus_next.aio import MessageBus
        self.loop, self.task = asyncio.get_running_loop(), asyncio.current_task()
        if self.closed:
            return
        self.bus = MessageBus()
        try:
            await asyncio.wait_for(self.bus.connect(), 5)
            # Activate the service before resolving the unique sender; never trust forged signals.
            await self.call('StartServiceByName', 'su', [SERVICE, 0], path='/org/freedesktop/DBus',
                            interface='org.freedesktop.DBus', destination='org.freedesktop.DBus')
            self.owner, = await self.call('GetNameOwner', 's', [SERVICE], path='/org/freedesktop/DBus',
                                         interface='org.freedesktop.DBus', destination='org.freedesktop.DBus')
            self.bus.add_message_handler(self.message)
            await self.call('AddMatch', 's', [f"type='signal',sender='{SERVICE}',path_namespace='{PATH}'"],
                            path='/org/freedesktop/DBus', interface='org.freedesktop.DBus', destination='org.freedesktop.DBus')
            result = await self.request('CreateSession', 'a{sv}', [
                {'session_handle_token': Variant('s', 'lv' + uuid.uuid4().hex)}])
            self.session = result['session_handle'].value
            result = await self.request('BindShortcuts', 'oa(sa{sv})sa{sv}', [self.session,
                [[self.shortcut_id, {'description': Variant('s', 'LocalVoice: Aufnahme starten / stoppen'),
                                    'preferred_trigger': Variant('s', self.trigger)}]], '', {}])
            shortcuts = result.get('shortcuts')
            bound = next((info for name, info in shortcuts.value if name == self.shortcut_id), None) if shortcuts else None
            if bound is None:
                raise RuntimeError('Desktop hat kein Tastenkürzel gebunden')
            description = bound.get('trigger_description')
            self.status.emit(True, 'Hotkey bereit: ' + (description.value if description else self.trigger))
            await self.bus.wait_for_disconnect()
            raise RuntimeError('Verbindung zum Desktop beendet')
        finally:
            if self.held and not self.closed:
                self.held = False
                self.released.emit()
            if self.session:
                try:
                    await self.call('Close', path=self.session, interface='org.freedesktop.portal.Session')
                except Exception:
                    pass  # disconnect also releases the session and its shortcuts
            self.bus.disconnect()

    def close(self):
        self.closed = True
        if self.loop and self.task and not self.loop.is_closed():
            try:
                self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:
                pass  # loop finished between the check and cancellation
        # ponytail: bounded shutdown; disconnect releases portal resources, no global desktop settings to restore.
        if self.thread.is_alive():
            self.thread.join(timeout=1)
