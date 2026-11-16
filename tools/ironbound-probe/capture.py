#!/usr/bin/env python3
"""Run an installed observation-only probe without changing the foreground app."""
import argparse
import datetime
import json
from pathlib import Path
import re
import subprocess
import time
from summarize import summarize


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--serial", required=True)
    p.add_argument("--port", default="5038")
    p.add_argument("--adb", default="adb")
    p.add_argument("--seconds", type=int, default=20, choices=range(5, 61), metavar="5..60")
    p.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[2] / ".tools/ironbound-captures")
    args = p.parse_args()
    base = [args.adb, "-P", args.port, "-s", args.serial]

    def adb(*argv):
        return subprocess.check_output(base + list(argv), timeout=20).decode("utf-8").replace("\r\n", "\n")

    def files():
        listing = adb("shell", "run-as", "app.ironbound.probe", "ls", "files")
        return set(re.findall(r"^capture-\d+\.jsonl$", listing, re.MULTILINE))

    # An absent files directory is normal before the very first launch.
    adb("shell", "run-as", "app.ironbound.probe", "mkdir", "-p", "files")
    before = files()
    response = adb("shell", "am", "startservice", "-n", "app.ironbound.probe/.CaptureService", "--ei", "seconds", str(args.seconds))
    if "Error" in response or "Exception" in response:
        raise RuntimeError(response)
    deadline = time.monotonic() + args.seconds + 40
    raw = ""
    rows = []
    while time.monotonic() < deadline:
        new_files = files() - before
        if len(new_files) > 1:
            raise RuntimeError("Multiple new captures; cannot identify this run")
        if new_files:
            filename = next(iter(new_files))
            raw = adb("exec-out", "run-as", "app.ironbound.probe", "cat", "files/" + filename)
            # A file copied mid-write may have an incomplete final line.
            rows = [json.loads(line) for line in raw.splitlines(keepends=True) if line.endswith("\n")]
            if any(r.get("kind") == "capture_finished" for r in rows):
                break
        time.sleep(2)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = args.output_dir / (stamp + ".jsonl")
    raw_path.write_text(raw)
    result = summarize(rows)
    (args.output_dir / (stamp + "-summary.json")).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print("Private raw capture:", raw_path)
    if not result["complete"]:
        raise SystemExit("Capture did not finish within the deadline; retained partial evidence. Do not infer successful cleanup.")


if __name__ == "__main__":
    main()
