#!/usr/bin/env python3
"""
Claude flight tracking runner.

This script is designed to be run by Claude Code. It starts flight_tracker.py
as a subprocess and prints human-readable instructions for Claude to follow,
so Claude can issue push notifications when flight events occur.

Usage (inside a Claude Code session):
    python track.py <FLIGHT_IATA>

Claude will:
  1. Run this script in the background via the Monitor tool
  2. Parse the JSON event lines
  3. Send push notifications to your phone for each event
"""

import subprocess
import sys
import os

CLAUDE_INSTRUCTIONS = """
=== CLAUDE INSTRUCTIONS ===
This process will emit JSON lines to stdout. For each line:
- Parse the JSON
- If event == "initial_status": send a push notification summarising the flight details
- If event == "status_change" or "landed": send a push notification with the new status
- If event == "delay": send a push notification with delay info
- If event == "gate_change": send a push notification with the new gate
- If event == "error": report the error to the user and stop monitoring
- If event == "tracking_ended": send a final notification and stop monitoring
=== END INSTRUCTIONS ===
"""

def main():
    if len(sys.argv) < 2:
        print("Usage: python track.py <FLIGHT_IATA>  (e.g. python track.py AA123)")
        sys.exit(1)

    flight = sys.argv[1].upper()
    interval = sys.argv[2] if len(sys.argv) > 2 else "60"

    print(CLAUDE_INSTRUCTIONS, flush=True)
    print(f"Starting tracker for flight {flight} (polling every {interval}s)...", flush=True)

    tracker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flight_tracker.py")
    cmd = [sys.executable, tracker, flight, "--interval", interval]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for line in proc.stdout:
            print(line, end="", flush=True)
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print('{"event": "tracking_ended", "reason": "user_cancelled"}', flush=True)


if __name__ == "__main__":
    main()
