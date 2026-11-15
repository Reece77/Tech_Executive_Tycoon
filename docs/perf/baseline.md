# Benchmark: baseline

commit c6c035a, Python 3.12.3, Linux x86_64, 4 CPUs. Written by `tools/bench.py run`.

## Turns, Holiday and saves

| Save | From | Turn median ms | Turn p95 ms | Turn max ms | Holiday s (months) | Size MB | Load s | Cold start s | Digest after turns | Digest after Holiday |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| integrator | Jan 2039 | 768 | 1248 | 1248 | 9.9 (12) | 157.5 | 0.38 | 5.72 | `b08cd2d4a4e8a4cc` | `78c1e4a5ab781b98` |
| software | Jan 2039 | 1713 | 2333 | 2333 | 20.8 (12) | 344.3 | 0.74 | 5.91 | `e610d8a31b2ac5f0` | `6e3c83a1a28c3f22` |
| world | Jan 2039 | 271 | 363 | 363 | 3.6 (12) | 18.2 | 0.13 | 5.12 | `c8bf675d5013d0ba` | `835290d7918ad962` |

## Screens (API, ms: first request after a month is played / warm p95)

| Screen | Endpoint | integrator | software | world |
|---|---|---:|---:|---:|
| Overview | `/overview` | 133 / 189 | 121 / 157 | 67 / 75 |
| Overview | `/events` | 126 / 7 | 128 / 6 | 131 / 8 |
| Overview | `/finance/summary` | 145 / 175 | 137 / 144 | 61 / 63 |
| People | `/people` | 72 / 284 | 58 / 387 | 9 / 9 |
| Products | `/products` | 48 / 64 | 30 / 40 | 5 / 5 |
| Products | `/portfolio` | 8 / 8 | 9 / 11 | 8 / 9 |
| Market | `/markets/{category}` | 9 / 11 | 13 / 13 | 10 / 11 |
| Rivals | `/rivals` | 137 / 153 | 172 / 197 | 77 / 91 |
| Rivals | `/news` | 11 / 13 | 12 / 9 | 9 / 9 |
| World news | `/world-news` | 324 / 11 | 239 / 10 | 250 / 12 |
| Group | `/group` | 122 / 170 | 113 / 139 | 92 / 78 |
| Fabs | `/fabs` | 17 / 14 | 11 / 10 | 9 / 8 |
| Mines | `/mines` | 170 / 183 | 212 / 200 | 119 / 144 |
| Automation | `/automation` | 23 / 29 | 18 / 25 | 9 / 8 |
| Automation | `/automation/digest` | 12 / 10 | 13 / 13 | 10 / 10 |
