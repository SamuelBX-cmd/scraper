#!/usr/bin/env python3
"""
Real-time flight tracker using AviationStack API.
Polls for status changes and emits JSON events to stdout for Claude to act on.

Usage:
    python flight_tracker.py <FLIGHT_IATA> [--interval SECONDS]

    AVIATIONSTACK_API_KEY must be set in the environment.

Events are written to stdout as JSON lines:
    {"event": "status_change", "flight": "AA123", "from": "scheduled", "to": "active", ...}
    {"event": "delay", "flight": "AA123", "type": "departure", "minutes": 45, ...}
    {"event": "gate_change", "flight": "AA123", "type": "departure", "old": "A1", "new": "B3", ...}
    {"event": "landed", "flight": "AA123", "airport": "JFK", ...}
    {"event": "error", "message": "..."}
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

API_BASE = "http://api.aviationstack.com/v1/flights"

STATUS_LABELS = {
    "scheduled": "Scheduled",
    "active": "In the air",
    "landed": "Landed",
    "cancelled": "Cancelled",
    "incident": "Incident reported",
    "diverted": "Diverted",
}

TERMINAL_STATUSES = {"landed", "cancelled"}


def emit(event: dict):
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(event), flush=True)


def fetch_flight(api_key: str, flight_iata: str) -> dict | None:
    try:
        resp = requests.get(
            API_BASE,
            params={"access_key": api_key, "flight_iata": flight_iata},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        emit({"event": "error", "message": f"API request failed: {e}"})
        return None

    if data.get("error"):
        emit({"event": "error", "message": data["error"].get("message", "Unknown API error")})
        return None

    flights = data.get("data", [])
    if not flights:
        return None

    return flights[0]


def summarize(flight: dict) -> dict:
    dep = flight.get("departure", {})
    arr = flight.get("arrival", {})
    return {
        "status": flight.get("flight_status"),
        "dep_gate": dep.get("gate"),
        "arr_gate": arr.get("gate"),
        "dep_delay": dep.get("delay"),
        "arr_delay": arr.get("delay"),
        "dep_airport": dep.get("iata"),
        "arr_airport": arr.get("iata"),
        "dep_estimated": dep.get("estimated"),
        "arr_estimated": arr.get("estimated"),
        "dep_actual": dep.get("actual"),
        "arr_actual": arr.get("actual"),
    }


def detect_changes(prev: dict, curr: dict, flight_iata: str) -> list[dict]:
    events = []

    if prev["status"] != curr["status"] and curr["status"]:
        base = {
            "event": "status_change",
            "flight": flight_iata,
            "from": prev["status"],
            "to": curr["status"],
            "label": STATUS_LABELS.get(curr["status"], curr["status"]),
        }
        if curr["status"] == "landed":
            base["event"] = "landed"
            base["airport"] = curr["arr_airport"]
            base["actual_arrival"] = curr["arr_actual"]
        elif curr["status"] == "active":
            base["dep_airport"] = curr["dep_airport"]
            base["arr_airport"] = curr["arr_airport"]
        events.append(base)

    if prev["dep_gate"] and curr["dep_gate"] and prev["dep_gate"] != curr["dep_gate"]:
        events.append({
            "event": "gate_change",
            "flight": flight_iata,
            "type": "departure",
            "old": prev["dep_gate"],
            "new": curr["dep_gate"],
            "airport": curr["dep_airport"],
        })

    if prev["arr_gate"] and curr["arr_gate"] and prev["arr_gate"] != curr["arr_gate"]:
        events.append({
            "event": "gate_change",
            "flight": flight_iata,
            "type": "arrival",
            "old": prev["arr_gate"],
            "new": curr["arr_gate"],
            "airport": curr["arr_airport"],
        })

    for delay_type in ("dep", "arr"):
        old_delay = prev[f"{delay_type}_delay"] or 0
        new_delay = curr[f"{delay_type}_delay"] or 0
        if new_delay > 0 and abs(new_delay - old_delay) >= 5:
            events.append({
                "event": "delay",
                "flight": flight_iata,
                "type": "departure" if delay_type == "dep" else "arrival",
                "minutes": new_delay,
                "change": new_delay - old_delay,
                "airport": curr["dep_airport"] if delay_type == "dep" else curr["arr_airport"],
            })

    return events


def track(flight_iata: str, api_key: str, interval: int):
    flight_iata = flight_iata.upper()
    emit({"event": "tracking_started", "flight": flight_iata, "poll_interval_seconds": interval})

    flight = fetch_flight(api_key, flight_iata)
    if flight is None:
        emit({"event": "error", "message": f"Flight {flight_iata} not found. Check the flight number and try again."})
        sys.exit(1)

    state = summarize(flight)
    emit({
        "event": "initial_status",
        "flight": flight_iata,
        "status": state["status"],
        "label": STATUS_LABELS.get(state["status"], state["status"]),
        "dep_airport": state["dep_airport"],
        "arr_airport": state["arr_airport"],
        "dep_estimated": state["dep_estimated"],
        "arr_estimated": state["arr_estimated"],
        "dep_gate": state["dep_gate"],
        "arr_gate": state["arr_gate"],
        "dep_delay": state["dep_delay"],
    })

    if state["status"] in TERMINAL_STATUSES:
        emit({"event": "tracking_ended", "flight": flight_iata, "reason": state["status"]})
        return

    while True:
        time.sleep(interval)

        flight = fetch_flight(api_key, flight_iata)
        if flight is None:
            continue

        new_state = summarize(flight)
        for event in detect_changes(state, new_state, flight_iata):
            emit(event)
        state = new_state

        if state["status"] in TERMINAL_STATUSES:
            emit({"event": "tracking_ended", "flight": flight_iata, "reason": state["status"]})
            break


def main():
    parser = argparse.ArgumentParser(description="Real-time flight tracker")
    parser.add_argument("flight", help="IATA flight number (e.g. AA123, BA456)")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds (default: 60)")
    args = parser.parse_args()

    api_key = os.environ.get("AVIATIONSTACK_API_KEY")
    if not api_key:
        emit({"event": "error", "message": "AVIATIONSTACK_API_KEY environment variable is not set."})
        sys.exit(1)

    track(args.flight, api_key, args.interval)


if __name__ == "__main__":
    main()
