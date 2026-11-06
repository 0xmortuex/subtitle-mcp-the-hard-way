"""Run every module's main.py, then check the finished server for real.

Part 1: each NN-*/main.py is run as a subprocess. Its own asserts check what its README
        claims, so a chapter whose code drifts from its prose fails here.
Part 2: the module 07 server is started over real stdio and driven the way an agent
        would, on files that none of the chapters used, and the files it writes are
        checked byte for byte.

Usage: python verify.py            # everything
       python verify.py 03 05      # just these modules (part 2 runs only with no arguments)
"""

from __future__ import annotations

import asyncio
import glob
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}  # Windows CI consoles are cp1252


def run_modules(only: list[str]) -> None:
    dirs = sorted(glob.glob(str(ROOT / "[0-9][0-9]-*")))
    if only:
        dirs = [d for d in dirs if os.path.basename(d)[:2] in only]
    assert dirs, "no modules selected"
    for d in dirs:
        name = os.path.basename(d)
        proc = subprocess.run(
            [sys.executable, os.path.join(d, "main.py")],
            capture_output=True, text=True, encoding="utf-8", env=ENV, timeout=180, check=False,
        )
        marker = f"module {name[:2]} OK"
        if proc.returncode != 0 or marker not in proc.stdout:
            print(proc.stdout)
            print(proc.stderr)
            sys.exit(f"FAIL {name}: exit {proc.returncode}, expected {marker!r}")
        print(f"ok   {name}")


TURKISH = (
    "1\n00:00:01,000 --> 00:00:03,000\nGünaydın çocuklar.\n\n"
    "2\n00:00:04,000 --> 00:00:06,000\nİstanbul'da şimdi.\n"
)
DRIFT = (
    "1\n00:00:10,000 --> 00:00:11,000\nline 1\n\n2\n00:10:00,000 --> 00:10:01,000\nline 2\n\n"
    "3\n00:50:00,000 --> 00:50:01,000\nline 3\n\n4\n01:40:00,000 --> 01:40:01,000\nline 4\n"
)
DAMAGED = (
    "5\n00:00:03,500 --> 00:00:03,500\nZero length\n\n"
    "1\n00:00:01,000 --> 00:00:04,000\nOverlaps the next one\n"
)


async def drive_server() -> None:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp).resolve()
        (work / "tr.srt").write_text(TURKISH, encoding="utf-8", newline="\n")
        (work / "drift.srt").write_text(DRIFT, encoding="utf-8", newline="\n")
        (work / "damaged.srt").write_text(DAMAGED, encoding="utf-8", newline="\n")
        server = ROOT / "07-mcp-wrapper-and-testing" / "main.py"
        params = StdioServerParameters(
            command=sys.executable, args=[str(server), "--serve", "--dir", str(work)], env=ENV
        )
        async with stdio_client(params) as (read, write), ClientSession(read, write) as s:
            await s.initialize()

            res = await s.call_tool("subtitle_info", {"path": "tr.srt"})
            info = json.loads(res.content[0].text)  # type: ignore[union-attr]
            assert info["cue_count"] == 2 and info["last_end"] == "00:00:06,000", info

            res = await s.call_tool("shift", {"path": "tr.srt", "offset_ms": 1500})
            assert not res.is_error, res.content
            assert (work / "tr.shifted.srt").read_text(encoding="utf-8") == (
                "1\n00:00:02,500 --> 00:00:04,500\nGünaydın çocuklar.\n\n"
                "2\n00:00:05,500 --> 00:00:07,500\nİstanbul'da şimdi.\n"
            )

            res = await s.call_tool("resync", {"path": "drift.srt", "anchors": [
                {"cue": 1, "to": "00:00:12,510"}, {"cue": 4, "to": "01:40:08,500"}]})
            assert not res.is_error and "[0, 0] ms" in res.content[0].text, res.content  # type: ignore[union-attr]
            assert (work / "drift.resynced.srt").read_text(encoding="utf-8").splitlines()[5] == (
                "00:10:03,100 --> 00:10:04,101"
            )

            res = await s.call_tool("check_problems", {"path": "damaged.srt"})
            text = res.content[0].text  # type: ignore[union-attr]
            assert "Dry run" in text and not (work / "damaged.fixed.srt").exists(), text
            await s.call_tool("check_problems", {"path": "damaged.srt", "apply": True})
            assert (work / "damaged.fixed.srt").read_text(encoding="utf-8") == (
                "1\n00:00:01,000 --> 00:00:03,500\nOverlaps the next one\n\n"
                "2\n00:00:03,500 --> 00:00:04,500\nZero length\n"
            )

            res = await s.call_tool("chunk_for_translation", {"path": "tr.srt"})
            ids = [c["id"] for c in json.loads(res.content[0].text)["cues"]]  # type: ignore[union-attr]
            assert ids == ["1", "2"]
            res = await s.call_tool("apply_translation", {
                "path": "tr.srt", "mapping": {"1": "Good morning kids.", "2": "In Istanbul now."}})
            assert not res.is_error, res.content
            assert (work / "tr.translated.srt").read_text(encoding="utf-8") == (
                "1\n00:00:01,000 --> 00:00:03,000\nGood morning kids.\n\n"
                "2\n00:00:04,000 --> 00:00:06,000\nIn Istanbul now.\n"
            )
    print("ok   finished server, driven over real stdio")


if __name__ == "__main__":
    selected = sys.argv[1:]
    run_modules(selected)
    if not selected:
        asyncio.run(drive_server())
    print("all good")
