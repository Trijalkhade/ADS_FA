# Smart Event Manager

A Flask web app demonstrating advanced data structures:
**Red-Black Tree**, **Trie**, and **BK-Tree**.

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5001 in your browser.

## Features

| Tab | What it does |
|-----|--------------|
| **Event Management** | Add/edit/delete events stored in a Red-Black Tree (chronological O(log n) order). Autocomplete on name & location via Trie. Fuzzy typo-tolerant search via BK-Tree. |
| **Word Intelligence** | Autocomplete from 908-word corpus via Trie. Spelling correction via BK-Tree + Levenshtein distance. |
| **Data Structures** | Live stats — RBT height, trie node counts, BK-Tree sizes. |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/events` | All events (chronological) |
| POST | `/events` | Add event `{name, date (DD-MM-YYYY), time (HH:MM), type, location}` |
| PUT | `/events/<id>` | Update event fields |
| DELETE | `/events/<id>` | Delete event |
| POST | `/search-events` | Fuzzy search `{query, max_dist, k}` |
| POST | `/autocomplete/event-name` | Name autocomplete `{prefix, k}` |
| POST | `/autocomplete/location` | Location autocomplete `{prefix, k}` |
| POST | `/autocomplete` | Word autocomplete `{prefix, k}` |
| POST | `/autocorrect` | Spelling correction `{word, k, max_dist}` |
| GET | `/stats` | Word trie/BK-Tree stats |
| GET | `/event-stats` | Event data structure stats |

## Testing

```bash
python test_api.py   # integration tests (server must be running)
```

## Notes

- Events persist across restarts via `events_cache.pkl`
- Word corpus data caches to `cache.pkl` after first load
- Port is **5001** (configured in `app.py`)
