"""Quartz Listener — macOS グローバルイベントタップ."""
from __future__ import annotations
import threading, time
from collections.abc import Callable
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()

@dataclass
class KeyEvent:
    keycode: int
    characters: str
    flags: int
    timestamp: float
    event_type: str
    is_repeat: bool = False
    @property
    def is_modifier(self) -> bool: return self.event_type == 'flags_changed'
    @property
    def has_cmd(self) -> bool: return bool(self.flags & 0x100000)
    @property
    def has_ctrl(self) -> bool: return bool(self.flags & 0x40000)
    @property
    def has_alt(self) -> bool: return bool(self.flags & 0x80000)
    @property
    def has_shift(self) -> bool: return bool(self.flags & 0x20000)

EventCallback = Callable[[KeyEvent], None]

class QuartzListener:
    def __init__(self):
        self._callbacks: list[EventCallback] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._tap = None
        self.log = logger.bind(component='quartz_listener')
        self._buffer: list[KeyEvent] = []
        self._buffer_lock = threading.Lock()

    def on_key(self, callback: EventCallback) -> None:
        self._callbacks.append(callback)

    @property
    def is_running(self) -> bool: return self._running

    def start(self) -> bool:
        if self._running: return True
        try:
            import Quartz
        except ImportError:
            self.log.error('quartz_not_available')
            return False
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name='quartz-listener')
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._tap = None

    def get_buffer(self, clear: bool = True) -> list[KeyEvent]:
        with self._buffer_lock:
            events = list(self._buffer)
            if clear: self._buffer.clear()
        return events

    def _run_loop(self) -> None:
        try:
            import Quartz
            from Quartz import (CGEventGetFlags, CGEventGetIntegerValueField, CGEventTapCreate,
                CFMachPortCreateRunLoopSource, CFRunLoopAddSource, CFRunLoopGetCurrent,
                CFRunLoopStop, kCFRunLoopCommonModes, kCGEventKeyDown, kCGEventKeyUp,
                kCGEventFlagsChanged, kCGHeadInsertEventTap, kCGSessionEventTap,
                kCGKeyboardEventKeycode, kCGKeyboardEventAutorepeat)

            def _callback(proxy, event_type, event, refcon):
                try:
                    keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                    flags = CGEventGetFlags(event)
                    is_repeat = bool(CGEventGetIntegerValueField(event, kCGKeyboardEventAutorepeat))
                    type_map = {kCGEventKeyDown: 'key_down', kCGEventKeyUp: 'key_up',
                                kCGEventFlagsChanged: 'flags_changed'}
                    key_event = KeyEvent(keycode=keycode, characters='', flags=flags,
                        timestamp=time.time(), event_type=type_map.get(event_type, 'unknown'),
                        is_repeat=is_repeat)
                    for cb in self._callbacks:
                        try: cb(key_event)
                        except Exception: pass
                    with self._buffer_lock:
                        self._buffer.append(key_event)
                        if len(self._buffer) > 10000: self._buffer = self._buffer[-5000:]
                except Exception: pass
                return event

            event_mask = (1 << kCGEventKeyDown) | (1 << kCGEventKeyUp) | (1 << kCGEventFlagsChanged)
            self._tap = CGEventTapCreate(kCGSessionEventTap, kCGHeadInsertEventTap, 0,
                                         event_mask, _callback, None)
            if self._tap is None:
                self._running = False
                return
            loop_source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
            loop = CFRunLoopGetCurrent()
            CFRunLoopAddSource(loop, loop_source, kCFRunLoopCommonModes)
            while self._running:
                Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 0.5, False)
            CFRunLoopStop(loop)
        except Exception as e:
            self.log.error('run_loop_error', error=str(e))
            self._running = False