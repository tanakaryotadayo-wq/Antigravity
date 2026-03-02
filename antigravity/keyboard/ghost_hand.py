"""Ghost Hand — ステルス入力注入."""
from __future__ import annotations
import time
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()

@dataclass
class Point:
    x: float
    y: float

class GhostHand:
    _KEYCODES: dict[str, int] = {
        'a': 0, 'b': 11, 'c': 8, 'd': 2, 'e': 14, 'f': 3, 'g': 5, 'h': 4,
        'i': 34, 'j': 38, 'k': 40, 'l': 37, 'm': 46, 'n': 45, 'o': 31,
        'p': 35, 'q': 12, 'r': 15, 's': 1, 't': 17, 'u': 32, 'v': 9,
        'w': 13, 'x': 7, 'y': 16, 'z': 6,
        '0': 29, '1': 18, '2': 19, '3': 20, '4': 21, '5': 23, '6': 22,
        '7': 26, '8': 28, '9': 25,
        'return': 36, 'tab': 48, 'space': 49, 'delete': 51, 'escape': 53,
        'up': 126, 'down': 125, 'left': 123, 'right': 124,
    }
    _MODIFIER_FLAGS: dict[str, int] = {
        'cmd': 0x100000, 'command': 0x100000,
        'ctrl': 0x40000, 'control': 0x40000,
        'alt': 0x80000, 'option': 0x80000,
        'shift': 0x20000,
    }

    def __init__(self):
        self.log = logger.bind(component='ghost_hand')
        self._quartz_available = False
        try:
            import Quartz
            self._quartz_available = True
        except ImportError:
            self.log.warning('quartz_not_available')

    @property
    def available(self) -> bool: return self._quartz_available

    def move(self, x: float, y: float) -> None:
        if not self._quartz_available: return
        import Quartz
        event = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved,
                                               Quartz.CGPointMake(x, y), Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def click(self, x: float, y: float, button: str = 'left') -> None:
        if not self._quartz_available: return
        import Quartz
        point = Quartz.CGPointMake(x, y)
        btn = Quartz.kCGMouseButtonLeft if button == 'left' else Quartz.kCGMouseButtonRight
        down_t = Quartz.kCGEventLeftMouseDown if button == 'left' else Quartz.kCGEventRightMouseDown
        up_t = Quartz.kCGEventLeftMouseUp if button == 'left' else Quartz.kCGEventRightMouseUp
        Quartz.CGEventPost(Quartz.kCGHIDEventTap,
                           Quartz.CGEventCreateMouseEvent(None, down_t, point, btn))
        time.sleep(0.05)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap,
                           Quartz.CGEventCreateMouseEvent(None, up_t, point, btn))

    def key_press(self, key: str) -> None:
        if not self._quartz_available: return
        import Quartz
        keycode = self._KEYCODES.get(key.lower(), -1)
        if keycode == -1: return
        Quartz.CGEventPost(Quartz.kCGHIDEventTap,
                           Quartz.CGEventCreateKeyboardEvent(None, keycode, True))
        time.sleep(0.02)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap,
                           Quartz.CGEventCreateKeyboardEvent(None, keycode, False))

    def hotkey(self, *keys: str) -> None:
        if not self._quartz_available: return
        import Quartz
        modifiers = [k for k in keys if k.lower() in self._MODIFIER_FLAGS]
        normal = [k for k in keys if k.lower() not in self._MODIFIER_FLAGS]
        flag_mask = 0
        for mod in modifiers: flag_mask |= self._MODIFIER_FLAGS[mod.lower()]
        for key in normal:
            kc = self._KEYCODES.get(key.lower(), -1)
            if kc == -1: continue
            down = Quartz.CGEventCreateKeyboardEvent(None, kc, True)
            up = Quartz.CGEventCreateKeyboardEvent(None, kc, False)
            Quartz.CGEventSetFlags(down, flag_mask)
            Quartz.CGEventSetFlags(up, flag_mask)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
            time.sleep(0.02)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)

    def type_text(self, text: str, interval: float = 0.03) -> None:
        if not self._quartz_available: return
        import Quartz
        for char in text:
            if char == chr(10): self.key_press('return')
            elif char == chr(9): self.key_press('tab')
            elif char == ' ': self.key_press('space')
            elif char.lower() in self._KEYCODES:
                if char.isupper(): self.hotkey('shift', char.lower())
                else: self.key_press(char)
            else:
                ev = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
                Quartz.CGEventKeyboardSetUnicodeString(ev, len(char), char)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            time.sleep(interval)