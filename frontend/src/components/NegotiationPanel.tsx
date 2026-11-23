import { Alert, Badge, Button, Drawer, NumberInput, Select, Textarea } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import {
  useFinishNegotiation,
  useNegotiation,
  useOpenNegotiation,
  usePlayRound,
  type DealParams,
  type MoveIn,
  type Negotiation,
  type NegotiationRound,
} from '../hooks/negotiations';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';
import { DataTable } from './DataTable';
import { Explain } from './Explain';
import { LoadError, Loading } from './ScreenState';
import { Term } from './Term';

// Negotiations by conversation (M47, formulas.md 58): the panel opened beside a deal's Accept.
// The engine decides every response; this shows the conversation, three suggested replies, the
// counterpart's offer and the revealed range, the player's offer, and the debrief. Values are
// sent in their unit: a sum in cents (typed in dollars), a quote's share in basis points (typed
// as a percentage). Nothing here computes a game value.

const MOVES: { kind: string; label: string }[] = [
  { kind: 'justify', label: 'Justify' },
  { kind: 'appeal', label: 'Appeal to the relationship' },
  { kind: 'anchor', label: 'Anchor' },
  { kind: 'concede', label: 'Concede' },
  { kind: 'close', label: 'Ask to close' },
  { kind: 'threaten_walk', label: 'Threaten to walk' },
];

const STATUS: Record<string, string> = {
  open: 'Talks are open',
  agreed: 'Agreed',
  skipped: 'Skipped: closed at today’s terms',
  walked: 'They walked away',
  lapsed: 'Lapsed at the month end',
  failed: 'Agreed, but the deal could not close',
};

/** The "Open negotiation" button beside a deal's Accept: opens (or resumes) talks on it. */
export function OpenNegotiation({
  saveId,
  kind,
  params,
  disabled,
  label = 'Open negotiation',
}: {
  saveId: string;
  kind: string;
  params: DealParams;
  disabled?: boolean;
  label?: string;
}) {
  const open = useOpenNegotiation(saveId);
  const [id, setId] = useState<number | null>(null);
  return (
    <>
      <Button
        size="xs"
        variant="light"
        data-testid={`open-negotiation-${kind}`}
        disabled={disabled}
        loading={open.isPending}
        onClick={() => open.mutate({ kind, params }, { onSuccess: (n) => setId(n.negotiation_id) })}
      >
        {label}
      </Button>
      {open.error && (
        <span className="tst-negative" style={{ fontSize: 12 }} data-testid="negotiation-error">
          {open.error.message}
        </span>
      )}
      {id !== null && (
        <Drawer opened onClose={() => setId(null)} position="right" size="xl" title="Negotiation">
          <NegotiationView saveId={saveId} id={id} />
        </Drawer>
      )}
    </>
  );
}

// Both units are shown in hundredths: cents as dollars, basis points as a percentage.
const toInput = (value: number): number => value / 100;
const fromInput = (value: number): number => Math.round(value * 100);

export function NegotiationView({ saveId, id }: { saveId: string; id: number }) {
  const q = useNegotiation(saveId, id);
  if (q.isPending) return <Loading />;
  if (q.error || !q.data) return <LoadError title="Could not load the talks" error={q.error} />;
  return <Talks saveId={saveId} n={q.data} />;
}

function Talks({ saveId, n }: { saveId: string; n: Negotiation }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }} data-testid="negotiation">
      <header>
        <h3 className="tst-ptitle" data-testid="negotiation-subject" style={{ margin: 0 }}>
          {n.subject}
        </h3>
        <div className="tst-muted" style={{ fontSize: 13 }} data-testid="negotiation-counterpart">
          {n.counterpart_name}, {n.counterpart_role}
          {n.counterpart_organisation ? ` at ${n.counterpart_organisation}` : ''}
          {n.counterpart_style ? ` · ${n.counterpart_style}` : ''} · relationship {n.relationship}
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
          <Badge variant="light" data-testid="negotiation-status">
            {STATUS[n.status] ?? n.status}
          </Badge>
          <Badge variant="outline" data-testid="negotiation-mode">
            {n.mode.mode === 'llm'
              ? 'Free text'
              : `Template mode${n.mode.reason ? ` (${n.mode.reason})` : ''}`}
          </Badge>
        </div>
      </header>
      <Log n={n} />
      {n.status === 'open' ? <Table saveId={saveId} n={n} /> : <Debrief n={n} />}
    </div>
  );
}

function Log({ n }: { n: Negotiation }) {
  return (
    <section aria-label="Conversation" data-testid="negotiation-log">
      <p style={{ margin: '0 0 8px' }}>
        <strong>{n.counterpart_name}:</strong> {n.opening_line}
      </p>
      {n.rounds.map((r) => (
        <div key={r.n} data-testid="negotiation-round" style={{ marginBottom: 8 }}>
          <p style={{ margin: 0 }}>
            <strong>You:</strong> {r.message}{' '}
            <span className="tst-muted" style={{ fontSize: 12 }}>
              (offer {r.offer_shown.join(', ')}; {r.moves.map((m) => m.words).join(', ')})
            </span>
          </p>
          <p style={{ margin: 0 }}>
            <strong>{n.counterpart_name}:</strong> {r.reply}
          </p>
        </div>
      ))}
    </section>
  );
}

function RangeLine({ n }: { n: Negotiation }) {
  return (
    <p style={{ margin: 0 }} data-testid="negotiation-range">
      <Term term="negotiation.reservation">Their limit</Term> lies between{' '}
      {n.ranges.map((r) => r.shown).join('; ')}{' '}
      <Explain metric="negotiation_range" entity={n.negotiation_id} label="the revealed range" />
    </p>
  );
}

function Table({ saveId, n }: { saveId: string; n: Negotiation }) {
  const play = usePlayRound(saveId, n.negotiation_id);
  const finish = useFinishNegotiation(saveId, n.negotiation_id);
  const [offer, setOffer] = useState<(number | string)[]>(() =>
    (n.offer ?? n.counter).map(toInput),
  );
  const [message, setMessage] = useState('');
  const [picked, setPicked] = useState<string[]>([]);
  const [fact, setFact] = useState<string | null>(
    String(n.facts.findIndex((_, i) => !n.used_facts.includes(i))),
  );
  const template = n.mode.mode === 'template';
  const values = offer.map((v) => fromInput(Number(v)));
  const valid = values.every((v) => Number.isFinite(v) && v > 0);
  const moves: MoveIn[] = picked.map((kind) =>
    kind === 'justify'
      ? { kind, fact: Number(fact ?? 0) }
      : kind === 'concede'
        ? { kind, term: 0 }
        : { kind },
  );
  const send = () => {
    if (template) {
      play.mutate({ offer: values, moves, source: 'template' }, { onSuccess: () => setPicked([]) });
    } else {
      play.mutate(
        { offer: values, message, source: n.suggestions.includes(message) ? 'suggested' : 'free' },
        { onSuccess: () => setMessage('') },
      );
    }
  };
  const error = play.error ?? finish.error;
  return (
    <section aria-label="The table" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <p style={{ margin: 0 }} data-testid="negotiation-counter">
        Their offer: <strong>{n.counter_shown.join('; ')}</strong>
        {n.mood !== 'open' && (
          <span className="tst-negative" data-testid="negotiation-mood">
            {' '}
            ({n.mood === 'final' ? 'close to walking' : 'getting firm'})
          </span>
        )}
      </p>
      <RangeLine n={n} />
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'end' }}>
        {n.terms.map((t, i) => (
          <NumberInput
            key={t.key}
            label={
              t.unit === 'cents' ? `Your ${t.label.toLowerCase()} ($)` : `${t.label} (% of quote)`
            }
            description={t.unit === 'bp' ? `Quote: ${t.base_shown}` : undefined}
            data-testid={`negotiation-offer-${i}`}
            value={offer[i]}
            onChange={(v) => setOffer(offer.map((o, j) => (j === i ? v : o)))}
            min={0}
            decimalScale={2}
            thousandSeparator=","
            style={{ width: 220 }}
          />
        ))}
      </div>
      {template ? (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'end' }}>
          {MOVES.map((m) => (
            <Button
              key={m.kind}
              size="xs"
              variant={picked.includes(m.kind) ? 'filled' : 'default'}
              data-testid={`move-${m.kind}`}
              onClick={() =>
                setPicked(
                  picked.includes(m.kind)
                    ? picked.filter((k) => k !== m.kind)
                    : [...picked, m.kind].slice(-3),
                )
              }
            >
              {m.kind === 'anchor' ? <Term term="negotiation.anchor">{m.label}</Term> : null}
              {m.kind === 'threaten_walk' ? (
                <Term term="negotiation.walk_away">{m.label}</Term>
              ) : null}
              {m.kind !== 'anchor' && m.kind !== 'threaten_walk' ? m.label : null}
            </Button>
          ))}
          {picked.includes('justify') && (
            <Select
              size="xs"
              data-testid="move-fact"
              label="Citing"
              value={fact}
              onChange={setFact}
              data={n.facts.map((f, i) => ({ value: String(i), label: f }))}
              style={{ width: 320 }}
            />
          )}
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {n.suggestions.map((s) => (
              <Button
                key={s}
                size="xs"
                variant="subtle"
                justify="flex-start"
                data-testid="negotiation-suggestion"
                onClick={() => setMessage(s)}
                style={{ whiteSpace: 'normal', height: 'auto', textAlign: 'left' }}
              >
                {s}
              </Button>
            ))}
          </div>
          <Textarea
            label="Your message"
            data-testid="negotiation-message"
            value={message}
            onChange={(e) => setMessage(e.currentTarget.value)}
            autosize
            minRows={2}
            maxLength={600}
          />
        </>
      )}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Button
          size="xs"
          data-testid="negotiation-send"
          loading={play.isPending}
          disabled={!valid || (template ? picked.length === 0 : !message.trim())}
          onClick={send}
        >
          {template ? 'Make these moves' : 'Send'}
        </Button>
        <Button
          size="xs"
          variant="light"
          data-testid="negotiation-accept"
          loading={finish.isPending && finish.variables === 'accept'}
          onClick={() => finish.mutate('accept')}
        >
          Accept their offer
        </Button>
        <Button
          size="xs"
          variant="default"
          data-testid="negotiation-skip"
          loading={finish.isPending && finish.variables === 'skip'}
          onClick={() => finish.mutate('skip')}
        >
          Skip (today’s terms)
        </Button>
      </div>
      {error && (
        <Alert color="red" data-testid="negotiation-error">
          {error.message}
        </Alert>
      )}
    </section>
  );
}

const helper = createColumnHelper<GameTableFeatures, NegotiationRound>();

function Debrief({ n }: { n: Negotiation }) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor('n', {
          header: 'Round',
          sortFn: 'basic',
          meta: { term: 'negotiation.round' },
        }),
        helper.accessor((r) => r.offer_shown.join('; '), {
          id: 'offer',
          header: 'Your offer',
          meta: { term: 'negotiation.offer' },
        }),
        helper.accessor((r) => r.moves.map((m) => m.words).join(', '), {
          id: 'moves',
          header: 'Moves (as the engine took them)',
          meta: { term: 'negotiation.moves' },
        }),
        helper.accessor((r) => r.counter_shown.join('; '), {
          id: 'counter',
          header: 'Their offer after',
          meta: { term: 'negotiation.counter' },
        }),
        helper.accessor('reason_words', {
          header: 'What they said',
          meta: { term: 'negotiation.said' },
        }),
      ]),
    [],
  );
  const table = useTable({ features: gameTableFeatures, columns, data: n.rounds });
  return (
    <section aria-label="Debrief" data-testid="negotiation-debrief">
      <h3 className="tst-ptitle">Debrief</h3>
      <p style={{ margin: '0 0 6px' }} data-testid="negotiation-final">
        {n.final_shown.length
          ? `Final terms: ${n.final_shown.join('; ')} (they opened at ${n.opening_shown.join('; ')}).`
          : `No deal (they opened at ${n.opening_shown.join('; ')}).`}
        {n.error ? ` ${n.error}` : ''}
      </p>
      <RangeLine n={n} />
      <DataTable
        table={table}
        label="Rounds"
        rowTestId="debrief-round"
        empty="No rounds were played."
      />
    </section>
  );
}
