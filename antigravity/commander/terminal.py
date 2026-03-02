"""Terminal Manager — ターミナル制御."""
from __future__ import annotations
import os, signal, subprocess, time
from dataclasses import dataclass
from pathlib import Path
import structlog
from antigravity.gate_engine import Decision, GateEngine

logger = structlog.get_logger()

@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    pid: int | None = None
    blocked: bool = False
    block_reason: str = ''

@dataclass
class RunningProcess:
    pid: int
    command: str
    started_at: float
    process: subprocess.Popen | None = None

class Terminal:
    def __init__(self, gate_engine: GateEngine | None = None, cwd: str | Path | None = None,
                 max_output_bytes: int = 256*1024, default_timeout: float = 30.0):
        self.gate = gate_engine or GateEngine()
        self.cwd = Path(cwd) if cwd else Path.cwd()
        self.max_output_bytes = max_output_bytes
        self.default_timeout = default_timeout
        self._processes: dict[int, RunningProcess] = {}
        self.log = logger.bind(component='terminal')

    def run(self, command: str, *, cwd: str | Path | None = None,
            timeout: float | None = None, env: dict[str, str] | None = None,
            check_gate: bool = True) -> CommandResult:
        if check_gate:
            gr = self.gate.check_command(command)
            if gr.decision == Decision.BLOCK:
                return CommandResult(command=command, exit_code=-1, stdout='', stderr=gr.reason,
                                    duration_ms=0, blocked=True, block_reason=gr.reason)
        work_dir = Path(cwd) if cwd else self.cwd
        run_timeout = timeout or self.default_timeout
        run_env = os.environ.copy()
        if env: run_env.update(env)
        start = time.monotonic()
        try:
            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, cwd=work_dir, env=run_env,
                                    preexec_fn=os.setsid if hasattr(os, 'setsid') else None)
            self._processes[proc.pid] = RunningProcess(pid=proc.pid, command=command,
                                                       started_at=time.time(), process=proc)
            try:
                stdout_b, stderr_b = proc.communicate(timeout=run_timeout)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                time.sleep(0.3)
                if proc.poll() is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                stdout_b, stderr_b = proc.communicate()
                self._processes.pop(proc.pid, None)
                return CommandResult(command=command, exit_code=-1,
                    stdout=stdout_b[:self.max_output_bytes].decode('utf-8', errors='replace'),
                    stderr=f'Timeout after {run_timeout}s',
                    duration_ms=(time.monotonic()-start)*1000, pid=proc.pid)
            self._processes.pop(proc.pid, None)
            return CommandResult(command=command, exit_code=proc.returncode,
                stdout=stdout_b[:self.max_output_bytes].decode('utf-8', errors='replace'),
                stderr=stderr_b[:self.max_output_bytes].decode('utf-8', errors='replace'),
                duration_ms=(time.monotonic()-start)*1000, pid=proc.pid)
        except FileNotFoundError:
            return CommandResult(command=command, exit_code=127, stdout='',
                stderr=f'Command not found', duration_ms=(time.monotonic()-start)*1000)
        except Exception as e:
            return CommandResult(command=command, exit_code=-1, stdout='', stderr=str(e),
                duration_ms=(time.monotonic()-start)*1000)

    def run_background(self, command: str, *, cwd: str|Path|None=None) -> int|None:
        gr = self.gate.check_command(command)
        if gr.decision == Decision.BLOCK: return None
        work_dir = Path(cwd) if cwd else self.cwd
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, cwd=work_dir,
                                preexec_fn=os.setsid if hasattr(os, 'setsid') else None)
        self._processes[proc.pid] = RunningProcess(pid=proc.pid, command=command,
                                                   started_at=time.time(), process=proc)
        return proc.pid

    def kill(self, pid: int) -> bool:
        pi = self._processes.get(pid)
        if pi and pi.process:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                pi.process.wait(timeout=5)
                self._processes.pop(pid, None)
                return True
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try: os.killpg(os.getpgid(pid), signal.SIGKILL)
                except ProcessLookupError: pass
                self._processes.pop(pid, None)
                return True
        return False

    def list_running(self) -> list[dict]:
        alive, dead = [], []
        for pid, info in self._processes.items():
            if info.process and info.process.poll() is None:
                alive.append({'pid': pid, 'command': info.command,
                              'elapsed_s': round(time.time()-info.started_at, 1)})
            else: dead.append(pid)
        for pid in dead: self._processes.pop(pid, None)
        return alive