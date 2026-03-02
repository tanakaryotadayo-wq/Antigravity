"""Keyboard + Commander テスト."""

from antigravity.keyboard.doppelganger import Doppelganger
from antigravity.commander.terminal import Terminal
from antigravity.commander.filesystem import FileSystem
from antigravity.commander.process import ProcessManager


class TestDoppelganger:
    def setup_method(self):
        self.doppel = Doppelganger()

    def test_detect_dangerous_command(self):
        signals = self.doppel.feed_keystrokes("rm -rf /\n")
        dangerous = [s for s in signals if s.intent == "dangerous"]
        assert len(dangerous) > 0

    def test_detect_secret(self):
        signals = self.doppel.feed_keystrokes("key = sk-abc123xyz\n")
        secrets = [s for s in signals if s.intent == "secret"]
        assert len(secrets) > 0

    def test_no_signal_on_normal(self):
        signals = self.doppel.feed_keystrokes("git status\n")
        dangerous = [s for s in signals if s.intent in ("dangerous", "secret")]
        assert len(dangerous) == 0

    def test_analyze_buffer(self):
        self.doppel.feed_keystrokes("AKIAIOSFODNN7EXAMPLE")
        signals = self.doppel.analyze()
        secrets = [s for s in signals if s.intent == "secret"]
        assert len(secrets) > 0

    def test_typing_stats(self):
        self.doppel.feed_keystrokes("hello world")
        stats = self.doppel.get_typing_stats()
        assert stats["buffer_length"] == 11


class TestTerminal:
    def setup_method(self):
        self.terminal = Terminal()

    def test_run_safe_command(self):
        result = self.terminal.run("echo hello")
        assert result.exit_code == 0
        assert "hello" in result.stdout

    def test_block_dangerous_command(self):
        result = self.terminal.run("rm -rf /")
        assert result.blocked is True
        assert result.exit_code == -1

    def test_timeout(self):
        result = self.terminal.run("sleep 10", timeout=1)
        assert result.exit_code == -1
        assert "Timeout" in result.stderr


class TestFileSystem:
    def setup_method(self):
        self.fs = FileSystem()

    def test_read_nonexistent(self):
        content = self.fs.read("/nonexistent/file.txt")
        assert content is None

    def test_write_and_read(self):
        import tempfile, os
        path = os.path.join(tempfile.mkdtemp(), "test.txt")
        success = self.fs.write(path, "hello from antigravity")
        assert success is True
        content = self.fs.read(path)
        assert content == "hello from antigravity"
        os.unlink(path)

    def test_block_env_write(self):
        success = self.fs.write("/tmp/test/.env", "SECRET=xyz")
        assert success is False

    def test_diff(self):
        import tempfile, os
        path = os.path.join(tempfile.mkdtemp(), "diff_test.txt")
        with open(path, "w") as f:
            f.write("line1\nline2\n")
        result = self.fs.diff(path, "line1\nline3\n")
        assert "-line2" in result
        assert "+line3" in result
        os.unlink(path)


class TestProcessManager:
    def setup_method(self):
        self.pm = ProcessManager()

    def test_list_processes(self):
        procs = self.pm.list_processes(limit=10)
        assert len(procs) > 0
        assert procs[0].pid > 0
