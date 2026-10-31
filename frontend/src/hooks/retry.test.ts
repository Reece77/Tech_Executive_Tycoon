import { describe, expect, it } from 'vitest';
import { ApiError, retryBusy } from './api';

// M8r (Codex review 1, finding 2): a mutation is retried only when the API says nothing was
// written. A busy answer without `retryable` (an older server, or anything after a commit)
// is shown, never sent again, so one Continue can't play two months.
describe('retryBusy', () => {
  it('retries a busy refusal the API marks retryable', () => {
    expect(retryBusy(0, new ApiError('save_busy', 'busy', true))).toBe(true);
    expect(retryBusy(5, new ApiError('save_busy', 'busy', true))).toBe(false);
  });
  it('never retries a busy answer without the mark, or another error', () => {
    expect(retryBusy(0, new ApiError('save_busy', 'busy'))).toBe(false);
    expect(retryBusy(0, new ApiError('critical_event_open', 'answer it', true))).toBe(false);
    expect(retryBusy(0, new Error('network'))).toBe(false);
  });
});
