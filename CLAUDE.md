# MISP-PurgeEvents — Project Guide 

## Overview
A Python 3 CLI tool for cleaning up old or unwanted events from a MISP (Malware Information Sharing Platform) instance. It supports date-range-based deletion, blocklist purging, per-organization filtering, dry-run simulation, and chunked bulk deletion to avoid MISP database instability.

Created by Dennis Rand / eCrimeLabs (https://www.ecrimelabs.com).

## File Structure

| File | Purpose |
|------|---------|
| `misp-purgeevents.py` | Main entry point — CLI argument parsing, all core logic |
| `config.py.template` | Template for `config.py` — copy and fill in values before first run |
| `requirements.txt` | Python package dependencies |
| `README.md` | User-facing documentation with usage examples |

## Configuration (`config.py`)

Copy `config.py.template` → `config.py` and set:

```python
misp_url = 'https://<MISP DOMAIN>'
misp_key = '<MISP API KEY>'
misp_verifycert = True          # Set False only if using self-signed certs

chunk_size = 200                # Events deleted per API batch

exclude_orgs = [                # OrgC UUIDs never deleted (e.g. your own org)
    '1cb16c82-c808-4342-a874-60574c9c4df9',
]
```

**Warning:** `config.py` contains credentials — never commit it.

## Dependencies

Install inside a virtualenv (Python 3.8+ required):

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Packages: `pymisp`, `datetime`, `argparse`, `arrow`, `tendo`, `uuid`

## CLI Arguments

| Flag | Description |
|------|-------------|
| `-f / --first` | Start of date range (YYYY-MM-DD). Default: yesterday |
| `-l / --last` | End of date range (YYYY-MM-DD). Default: today |
| `-d / --dryrun` | Simulate only — no deletions performed |
| `-v / --verbose` | Print each event UUID as it is processed |
| `-b / --blocklist` | Target MISP blocklisted events instead of regular events |
| `-o / --orguuid` | Restrict deletions to a single organization by UUID |
| `--include-unpublished` | Also purge unpublished events (default: published only) |
| `--force` | Skip the interactive confirmation prompt |

## Core Functions

### `main()`
Parses CLI args, validates date formats and UUID, sets globals (`dryrun`, `verbose`, `blocklisted`), then calls `perform_task()`.

### `perform_task(first, last, blocklisted, force, orguuid, include_unpublished)`
Orchestrates the full deletion workflow:
1. Enforces singleton (one instance at a time via `tendo`).
2. Prompts for confirmation unless `--force` or `--dryrun`.
3. Connects to MISP via `PyMISP`.
4. Fetches feed-pinned event IDs to exclude.
5. Dispatches to either `search_and_delete_blocklist_events()` or the standard search + delete path.
6. Chunks large event sets and sleeps between chunks to protect the database.

### `search_misp_events(misp, time_list, exclude_event_ids, orguuid, include_unpublished)`
Calls `/events/index` with `minimal=1` for efficiency. Filters out excluded org UUIDs and feed-pinned IDs. Returns a list of integer event IDs.

### `delete_misp_events(misp, event_db)`
Sends a bulk POST to `/events/delete` with a JSON list of IDs. Returns `(cntSuccess, cntFailed)`.

### `search_and_delete_blocklist_events(misp, earliest, latest)`
Fetches the full blocklist, filters by date range, and deletes each matching UUID individually via `misp.delete_event_blocklist()`.

### `get_active_lists_fixed_id(misp)`
Returns a list of event IDs pinned by MISP Feeds so they are never accidentally deleted.

### Utility helpers
- `is_valid_uuid(val)` — validates UUID format
- `valid_date(date_string)` — validates YYYY-MM-DD format
- `timestamp_today()` / `timestamp_yesterday()` — default date values for CLI
- `timestamp()` — human-readable UTC timestamp for logging
- `handler(signum, frame)` — graceful Ctrl-C handler

## Chunking & Sleep Logic

Large deletions are split into chunks of `chunk_size` (default 200). The tool sleeps automatically to prevent database overload:
- **360 seconds** after any chunk with failures
- **120 seconds** every 10 successful chunks
- Exits after **3+ consecutive failures**

## Recommended Pre-Deletion Steps (large datasets)

1. Disable correlations in MISP: `Administration → Server Settings → MISP.completely_disable_correlation = True`
2. Confirm the correlations table is empty via `Diagnostics → SQL database status`
3. Run with `--dryrun` first to preview scope
4. Re-enable correlations after the purge completes

## Development Notes

- `test.py` contains a prototype for date-range splitting using `pandas.date_range`. This logic was **not** ported into the main script — the main tool passes the full date range directly to the MISP API rather than splitting it client-side.
- Global state (`verbose`, `dryrun`, `blocklisted`) is set in `main()` and consumed by all helper functions.
- `misp_url` and `misp_key` are also imported as globals and used directly inside `delete_misp_events()` for the raw `requests.post` call (the bulk-delete endpoint is not wrapped by PyMISP).
