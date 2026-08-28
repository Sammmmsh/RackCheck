"""Bounded subprocess execution. No shell; no commands from configuration."""

from dataclasses import dataclass
import os
import signal
import subprocess
import tempfile


@dataclass
class CommandResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    detail: str = ""


def run(argv: list[str], timeout: float, max_bytes=2_097_152) -> CommandResult:
    env = {**os.environ, "LC_ALL": "C", "LANG": "C", "SYSTEMD_COLORS": "0", "SYSTEMD_PAGER": "cat"}
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        try:
            proc = subprocess.Popen(
                argv, stdin=subprocess.DEVNULL, stdout=output, stderr=errors, shell=False,
                env=env, start_new_session=os.name == "posix",
            )
        except FileNotFoundError:
            return CommandResult("unsupported", detail=f"Required executable is unavailable: {argv[0]}")
        except OSError as exc:
            return CommandResult("error", detail=f"Cannot start collector: {exc}")
        def stop():
            if os.name == "posix":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                proc.kill()
            proc.wait()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop()
            return CommandResult("error", detail=f"Collector timed out after {timeout:g}s")
        except BaseException:
            stop()
            raise
        output.seek(0)
        errors.seek(0)
        raw = output.read(max_bytes + 1)
        stderr = errors.read(65_536).decode("utf-8", "replace")
        if len(raw) > max_bytes:
            return CommandResult("error", stderr=stderr, returncode=proc.returncode, detail="Collector output exceeded size limit")
        return CommandResult("ok", raw.decode("utf-8", "replace"), stderr, proc.returncode)
