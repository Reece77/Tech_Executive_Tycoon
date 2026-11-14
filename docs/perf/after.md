# Benchmark: after

commit a74133c, Python 3.12.3, Linux x86_64, 4 CPUs. Written by `tools/bench.py run`.

## Turns, Holiday and saves

| Save | From | Turn median ms | Turn p95 ms | Turn max ms | Holiday s (months) | Size MB | Load s | Cold start s | Digest after turns | Digest after Holiday |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| integrator | Jan 2039 | 470 | 821 | 821 | 5.4 (12) | 158.2 | 0.48 | 6.60 | `b08cd2d4a4e8a4cc` | `78c1e4a5ab781b98` |
| software | Jan 2039 | 646 | 1457 | 1457 | 9.3 (12) | 345.9 | 0.58 | 6.09 | `e610d8a31b2ac5f0` | `6e3c83a1a28c3f22` |
| world | Jan 2039 | 239 | 378 | 378 | 3.3 (12) | 18.4 | 0.13 | 4.75 | `c8bf675d5013d0ba` | `835290d7918ad962` |

## Screens (API, ms: first request after a month is played / warm p95)

| Screen | Endpoint | integrator | software | world |
|---|---|---:|---:|---:|
| Overview | `/overview` | 141 / 21 | 126 / 31 | 71 / 15 |
| Overview | `/events` | 117 / 6 | 109 / 7 | 151 / 6 |
| Overview | `/finance/summary` | 127 / 7 | 118 / 14 | 60 / 6 |
| People | `/people` | 53 / 60 | 69 / 76 | 8 / 8 |
| Products | `/products` | 37 / 41 | 28 / 34 | 5 / 5 |
| Products | `/portfolio` | 7 / 8 | 9 / 9 | 7 / 7 |
| Market | `/markets/{category}` | 10 / 9 | 9 / 9 | 8 / 9 |
| Rivals | `/rivals` | 160 / 31 | 156 / 26 | 74 / 22 |
| Rivals | `/news` | 13 / 12 | 9 / 8 | 9 / 7 |
| World news | `/world-news` | 306 / 13 | 232 / 12 | 204 / 8 |
| Group | `/group` | 128 / 9 | 141 / 8 | 86 / 7 |
| Fabs | `/fabs` | 12 / 11 | 12 / 11 | 9 / 9 |
| Mines | `/mines` | 160 / 42 | 135 / 34 | 79 / 28 |
| Automation | `/automation` | 18 / 21 | 18 / 14 | 6 / 6 |
| Automation | `/automation/digest` | 14 / 12 | 14 / 11 | 10 / 9 |
