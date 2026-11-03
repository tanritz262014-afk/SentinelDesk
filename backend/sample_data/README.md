# Sample data

All files are **synthetic**. They contain no real users, hosts, credentials, personal data or malware.
Internal IPs use the private range 10.20.x.x. "External" IPs use the reserved documentation ranges
198.51.100.0/24 and 203.0.113.0/24, which are never assigned to real systems.

| File | Purpose | Expected upload result |
|---|---|---|
| `suspicious_events.json` | 8 failed logons for `admin.backup` from 203.0.113.45 in about 2 minutes, then a successful logon, a new account (4720) and a service installed from `C:\Users\Public\...` (7045) | 12 accepted, 0 rejected |
| `normal_events.json` | An ordinary working day: logons, logoffs, and a few mistyped passwords below the threshold | 13 accepted, 0 rejected |
| `mixed_events.csv` | CSV format: an overnight RDP brute-force burst (6 failures) against `test.user`, plus normal activity and a service installed under Program Files | 11 accepted, 0 rejected |
| `invalid_events.json` | Validation demo: 2 valid rows and 6 broken ones (missing timestamp, bad event ID, bad IP, bad date, not an object, nested value) | 2 accepted, 6 rejected |
