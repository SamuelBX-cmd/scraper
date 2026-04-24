# Flight Tracker

Real-time flight tracker that sends push notifications to the Claude mobile app.

## Setup

1. Get a free API key from https://aviationstack.com (free tier = 100 req/month)
2. Set your key: `export AVIATIONSTACK_API_KEY=your_key_here`
3. Install dependencies: `pip install -r requirements.txt`

## How to track a flight

Ask Claude (in this session):

> "Track flight AA123"

Claude will:
1. Run `python track.py AA123` in the background
2. Monitor the output stream
3. Send push notifications to your phone for each event:
   - Initial status summary
   - Departure / takeoff
   - Delays (≥5 min change)
   - Gate changes
   - Landing

## Event types emitted by flight_tracker.py

| event | when |
|-------|------|
| `tracking_started` | Monitoring begins |
| `initial_status` | First successful fetch |
| `status_change` | Any status transition |
| `landed` | Flight lands |
| `delay` | Delay changes by ≥5 min |
| `gate_change` | Departure or arrival gate changes |
| `error` | API or network error |
| `tracking_ended` | Flight in terminal state or cancelled by user |

## Notes

- AviationStack free tier does **not** support historical flights — flight must be scheduled within ~24 hrs
- Default poll interval is 60 seconds. Pass `--interval 30` to poll more frequently (uses more quota)
- IATA flight codes: airline prefix + number, e.g. `BA456`, `UA789`, `DL100`
