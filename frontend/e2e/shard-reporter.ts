// M59: shards balanced by measured file time. `playwright test --shard=N/T` normally splits the
// files, in name order, into runs of equal test counts; the M31-M55 flows (about a minute a test)
// sit together in that order and gave one shard twice the mean. This reporter takes the split
// over (TestRun.skipSharding): whole files, heaviest first, each to the shard with the least
// time so far, from e2e/durations.json (seconds a file, summed test durations on CI). A file
// missing from it counts as the mean of the known ones. Every test still runs exactly once
// across the T shards, in the same order within a file and the same file order within a shard.
//
// backend/tests/unit/test_ci_shards.py predicts the same split (keep the two in step) and
// warns or fails when the slowest shard nears the job's limit.
//
// With TST_E2E_DURATIONS_OUT set, the run also writes each file's summed test durations there
// (seconds, JSON): the nightly merges the four shards' files into a fresh e2e/durations.json.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import type {
  FullConfig,
  Reporter,
  Suite,
  TestCase,
  TestResult,
  TestRun,
} from '@playwright/test/reporter';

const DURATIONS_FILE = join(import.meta.dirname, 'durations.json');

/** Files to shards (0-based): heaviest first, ties by name, each to the lightest shard so far
 * (ties: the lowest shard). */
export function assignShards(
  files: string[],
  seconds: Record<string, number>,
  total: number,
): Map<string, number> {
  const known = files.filter((f) => f in seconds).map((f) => seconds[f]);
  const fallback = known.length ? known.reduce((a, b) => a + b, 0) / known.length : 1;
  const weight = (f: string) => seconds[f] ?? fallback;
  const sums = Array.from({ length: total }, () => 0);
  const out = new Map<string, number>();
  const order = [...files].sort((a, b) => weight(b) - weight(a) || (a < b ? -1 : a > b ? 1 : 0));
  for (const f of order) {
    let k = 0;
    for (let i = 1; i < total; i++) if (sums[i] < sums[k]) k = i;
    out.set(f, k);
    sums[k] += weight(f);
  }
  return out;
}

function fileKey(testDir: string, file: string): string {
  return relative(testDir, file).split(sep).join('/');
}

export default class ShardReporter implements Reporter {
  private testDir = '';
  private times = new Map<string, number>();

  async preprocess({
    config,
    suite,
    testRun,
  }: {
    config: FullConfig;
    suite: Suite;
    testRun: TestRun;
  }): Promise<void> {
    this.testDir = config.projects[0]?.testDir ?? '';
    const shard = config.shard;
    if (!shard) return;
    const seconds = JSON.parse(readFileSync(DURATIONS_FILE, 'utf8')) as Record<string, number>;
    const files = suite.suites.flatMap((project) => project.suites);
    const keys = [...new Set(files.map((f) => fileKey(this.testDir, f.location?.file ?? '')))];
    const assigned = assignShards(keys, seconds, shard.total);
    testRun.skipSharding();
    for (const f of files) {
      if (assigned.get(fileKey(this.testDir, f.location?.file ?? '')) !== shard.current - 1) {
        testRun.exclude(f);
      }
    }
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    const key = fileKey(this.testDir, test.location.file);
    this.times.set(key, (this.times.get(key) ?? 0) + result.duration / 1000);
  }

  onEnd(): void {
    const out = process.env.TST_E2E_DURATIONS_OUT;
    if (!out) return;
    const rows = [...this.times.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
    mkdirSync(dirname(out), { recursive: true });
    writeFileSync(
      out,
      JSON.stringify(
        Object.fromEntries(rows.map(([f, s]) => [f, Math.round(s * 10) / 10])),
        null,
        1,
      ) + '\n',
    );
  }

  printsToStdio(): boolean {
    return false;
  }
}
