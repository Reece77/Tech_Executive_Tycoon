# Benchmark: baseline-iw

commit 42a8037, Python 3.12.3, Linux x86_64, 4 CPUs. Written by `tools/bench.py run`.

## Turns, Holiday and saves

| Save | From | Turn median ms | Turn p95 ms | Turn max ms | Holiday s (months) | Size MB | Load s | Cold start s | Digest after turns | Digest after Holiday |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| integrator | Jan 2039 | 698 | 1289 | 1289 | 10.0 (12) | 157.5 | 0.42 | 6.36 | `b08cd2d4a4e8a4cc` | `78c1e4a5ab781b98` |
| world | Jan 2039 | 266 | 361 | 361 | 3.8 (12) | 18.2 | 0.12 | 5.31 | `c8bf675d5013d0ba` | `835290d7918ad962` |

## Screens (API, ms: first request after a month is played / warm p95)

| Screen | Endpoint | integrator | world |
|---|---|---:|---:|
| Overview | `/overview` | 999 / 153 | 77 / 103 |
| Overview | `/events` | 140 / 7 | 128 / 8 |
| Overview | `/finance/summary` | 110 / 149 | 61 / 85 |
| People | `/people` | 67 / 312 | 14 / 13 |
| Products | `/products` | 40 / 39 | 7 / 8 |
| Products | `/portfolio` | 8 / 9 | 10 / 9 |
| Market | `/markets/{category}` | 10 / 11 | 9 / 11 |
| Rivals | `/rivals` | 138 / 154 | 97 / 94 |
| Rivals | `/news` | 10 / 9 | 13 / 10 |
| World news | `/world-news` | 212 / 12 | 559 / 10 |
| Group | `/group` | 114 / 130 | 62 / 76 |
| Fabs | `/fabs` | 15 / 12 | 10 / 10 |
| Mines | `/mines` | 177 / 192 | 124 / 144 |
| Automation | `/automation` | 21 / 26 | 7 / 7 |
| Automation | `/automation/digest` | 11 / 11 | 9 / 10 |
