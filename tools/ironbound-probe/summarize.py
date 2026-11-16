#!/usr/bin/env python3
"""Produce an allowlisted, shareable summary; raw messages remain private."""
import argparse
import collections
import json
from pathlib import Path
import statistics


def summarize(rows):
    kinds = collections.Counter(row.get("kind", "unknown") for row in rows)
    messages = [r for r in rows if r.get("kind") == "message" and isinstance(r.get("value"), dict)]
    types = collections.Counter(str(r["value"].get("msgtype", "unknown")) for r in messages)
    motor = [r for r in messages if r["value"].get("msgtype") in (4132, 4116)]
    arrivals = [r["received_elapsed_ms"] for r in motor]
    gaps = [b - a for a, b in zip(arrivals, arrivals[1:]) if b >= a]
    transport = []
    devices = []
    profiles = []
    for row in messages:
        msg = row["value"]
        body = msg.get("body", {})
        if not isinstance(body, dict):
            continue
        if msg.get("msgtype") == 4147:
            fields = ("component_type", "bytes_received", "bytes_sent", "rx_failures", "rx_bytes_dropped", "tx_bytes_dropped")
            transport.append({k: body[k] for k in fields if k in body})
        if msg.get("msgtype") == 4130:
            fields = ("identifier", "component_type", "firmware_version", "hardware_revision", "part_number", "bootloader_version")
            devices.append({k: body[k] for k in fields if k in body})
        if msg.get("msgtype") == 4131:
            fields = ("control_mode", "location", "base_weight_lbs", "ecc_weight_lbs", "rom_weight_lbs", "rom_weight_mode", "spotter_mode", "number_reps", "outward_speed_ips", "inward_speed_ips")
            profiles.append({k: body[k] for k in fields if k in body})
    # Never include arbitrary raw body fields, serials, listener names or error strings.
    states = [r["value"] for r in rows if r.get("kind") in ("state", "status") and isinstance(r.get("value"), int)]
    complete = any(r.get("kind") == "capture_finished" for r in rows)
    discrete = {}
    ranges = {}
    for field in ("control_mode", "rom_weight_mode", "spotter_mode", "rep_phase", "rep_alg_phase", "is_racked", "is_grounded"):
        values = {r["value"].get("body", {}).get(field) for r in motor}
        discrete[field] = sorted(v for v in values if isinstance(v, (bool, int)))
    for field in ("base_weight_applied_lbs", "ecc_weight_applied_lbs", "total_weight_applied_lbs", "rep_count", "position_cable_left_in", "position_cable_right_in"):
        values = [r["value"].get("body", {}).get(field) for r in motor]
        numbers = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if numbers:
            ranges[field] = {"min": min(numbers), "max": max(numbers)}
    return {
        "summary_schema_version": 1,
        "complete": complete,
        "record_count": len(rows),
        "duration_observed_ms": rows[-1]["received_elapsed_ms"] - rows[0]["received_elapsed_ms"] if rows else None,
        "lifecycle_counts": dict(sorted(kinds.items())),
        "service_states": states,
        "message_counts": dict(sorted(types.items())),
        "motor_sample_count": len(motor),
        "motor_arrival_gap_ms": {"median": statistics.median(gaps), "max": max(gaps)} if gaps else None,
        "transport_stats": transport,
        "device_info": devices,
        "mass_profiles": profiles,
        "observed_motor_states": discrete if motor else {},
        "observed_motor_ranges": ranges,
        "interpretation": "Callback receipt proves observation access only; no motor commands or physical behavior are validated.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.capture.read_text().splitlines() if line.strip()]
    result = json.dumps(summarize(rows), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result)
    print(result, end="")


if __name__ == "__main__":
    main()
