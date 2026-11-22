"""Serve the fictional source pages and run the C06 task through dsh."""
import argparse
import functools
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading


ROOT = Path(__file__).resolve().parent


class QuietServer(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def dsh_command(explicit_entry):
    node = shutil.which("node")
    launcher = shutil.which("dsh")
    if explicit_entry is None and launcher:
        candidate = Path(launcher).parent / "node_modules/@deepseek-ai/dsh/lib/bin.js"
        explicit_entry = candidate if candidate.is_file() else None
    if explicit_entry:
        # Node 22 releases without import.meta.main need an explicit CLI entry call.
        entry_call = "await (await import(process.argv[1])).runCli()"
        return [node, "--input-type=module", "-e", entry_call, "--", explicit_entry.resolve().as_uri()]
    if launcher is None:
        raise SystemExit("Install dsh or pass --dsh-entry.")
    return [launcher]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsh-entry", type=Path)
    parser.add_argument("--run-dir", type=Path, default=ROOT / ".run/c06")
    args = parser.parse_args()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("Set DEEPSEEK_API_KEY before running.")
    run = args.run_dir.resolve()
    run.mkdir(parents=True, exist_ok=False)
    workspace = run / "workspace"
    shutil.copytree(ROOT / "case", workspace)
    handler = functools.partial(QuietServer, directory=ROOT / "site/mock")
    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            origin = f"http://127.0.0.1:{server.server_port}"
            (workspace / ".mock-origin").write_text(origin, encoding="utf-8")
            env = {key: value for key, value in os.environ.items()
                   if key.upper() in {
                       "SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP",
                       "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH",
                       "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "OS",
                       "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PLAYWRIGHT_BROWSERS_PATH",
                       "C06_CHROMIUM", "DEEPSEEK_API_KEY",
                   }}
            env.update(DSH_HOME=str(run / "dsh-home"), PYTHONIOENCODING="utf-8",
                       PYTHONUTF8="1", NO_PROXY="127.0.0.1,localhost")
            config = run / "case-tools.yml"
            disabled = ["tool-pwsh", "tool-bash", "tool-subagent", "tool-subagent-fork",
                        "tool-subagent-control", "tool-web-search", "tool-web-fetch"]
            tool_server = {"id": "mcp-c06", "name": "@deepseek-ai/dsh-mcp-client", "config": {
                "serverName": "c06", "transport": "stdio", "command": sys.executable,
                "args": [str(workspace / "mcp_server.py")], "cwd": str(workspace),
                "env": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
                "failOnStartupError": True,
            }}
            config.write_text(json.dumps([{"id": key, "disabled": True} for key in disabled]
                                         + [{"insert": [tool_server]}]), encoding="utf-8")
            command = dsh_command(args.dsh_entry) + [
                "headless", "--patch", str(config), "--json", "--permission-mode",
                "read-only", "--approval-policy", "never", "-",
            ]
            print("Running dsh headless with deepseek-flash on the fictional C06 case.", flush=True)
            with (workspace / "TASK.md").open("rb") as task, (run / "dsh.jsonl").open("wb") as journal, (run / "stderr.log").open("wb") as diagnostics:
                completed = subprocess.run(command, cwd=workspace, env=env, stdin=task,
                                           stdout=journal, stderr=diagnostics, timeout=360)
            print(f"dsh exit {completed.returncode}, submission: {(workspace / 'submission.json').is_file()}, trace: {(workspace / 'trace/browser.jsonl').is_file()}", flush=True)
            if completed.returncode or not (workspace / "submission.json").is_file():
                raise SystemExit(completed.returncode or 1)
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()

