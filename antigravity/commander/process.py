"""Process Manager — プロセス管理."""
from __future__ import annotations
import os, signal, subprocess
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()

@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_mb: float
    user: str
    command: str

class ProcessManager:
    def __init__(self):
        self.log = logger.bind(component='process_manager')

    def list_processes(self, *, filter_name: str|None=None, sort_by: str='cpu',
                       limit: int=50) -> list[ProcessInfo]:
        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=10)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
        processes: list[ProcessInfo] = []
        for line in result.stdout.strip().split(chr(10))[1:]:
            parts = line.split(None, 10)
            if len(parts) < 11: continue
            try:
                proc = ProcessInfo(pid=int(parts[1]), name=parts[10].split('/')[(-1)].split()[0],
                    cpu_percent=float(parts[2]), memory_mb=float(parts[5])/1024,
                    user=parts[0], command=parts[10][:200])
                if filter_name and filter_name.lower() not in proc.name.lower(): continue
                processes.append(proc)
            except (ValueError, IndexError): continue
        if sort_by == 'cpu': processes.sort(key=lambda p: p.cpu_percent, reverse=True)
        elif sort_by == 'memory': processes.sort(key=lambda p: p.memory_mb, reverse=True)
        return processes[:limit]

    def kill(self, pid: int, force: bool=False) -> bool:
        sig = signal.SIGKILL if force else signal.SIGTERM
        try:
            os.kill(pid, sig)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def find_by_port(self, port: int) -> list[ProcessInfo]:
        try:
            result = subprocess.run(['lsof', '-i', f':{port}', '-P', '-n'],
                                    capture_output=True, text=True, timeout=10)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
        processes: list[ProcessInfo] = []
        for line in result.stdout.strip().split(chr(10))[1:]:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    processes.append(ProcessInfo(pid=int(parts[1]), name=parts[0], cpu_percent=0,
                        memory_mb=0, user=parts[2] if len(parts)>2 else '', command=parts[0]))
                except ValueError: continue
        return processes