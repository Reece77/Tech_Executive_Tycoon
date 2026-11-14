// Platforms (M31, formulas.md 44): every platform's users, developer share, catalogue index, fees
// and rules by region; the player's own platforms' settings; device lines' platforms; apps' fees
// and listings; standards contests. No game values are computed here: shares are formatted only.
import { Alert, Button, NumberInput, Select, Switch } from '@mantine/core';
import { createColumnHelper, useTable } from '@tanstack/react-table';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { DataTable } from '../components/DataTable';
import { Explain } from '../components/Explain';
import { LoadError, Loading, Panel, ScreenTitle } from '../components/ScreenState';
import { Term } from '../components/Term';
import {
  formatShare,
  useAdoptStandard,
  useComplyListing,
  useCreateDeveloperPlatform,
  usePlatforms,
  useSetDevicePlatform,
  useSetPlatformRules,
  useSetSteering,
  type Platform,
  type Platforms,
  type Standard,
} from '../hooks/platforms';
import { formatMoneyWhole } from '../lib/format';
import { gameTableFeatures, type GameTableFeatures } from '../lib/table';

interface Row {
  platform: Platform;
  users: number;
  developers: string;
  catalogue: number;
  fee: number;
  rules: string;
}

const helper = createColumnHelper<GameTableFeatures, Row>();
const standardHelper = createColumnHelper<GameTableFeatures, Standard>();
const PERCENT = 100;

export function PlatformsScreen() {
  const { saveId = '' } = useParams();
  const q = usePlatforms(saveId);
  if (q.isPending) return <Loading />;
  if (q.error) return <LoadError title="Could not load platforms" error={q.error} />;
  return <PlatformsBody saveId={saveId} p={q.data} />;
}

export function PlatformsBody({ saveId, p }: { saveId: string; p: Platforms }) {
  const regions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const pl of p.platforms) for (const r of pl.regions) seen.set(r.region, r.label);
    return [...seen].map(([value, label]) => ({ value, label }));
  }, [p]);
  const [region, setRegion] = useState<string>('north_america');
  const own = p.platforms.filter((x) => x.own);
  return (
    <>
      <ScreenTitle
        aside={
          <span className="tst-muted" style={{ fontSize: 13 }}>
            {p.started
              ? 'Shares, developers and catalogues are computed from January 2026.'
              : 'To 2025, users and fees follow the historical record.'}{' '}
            {p.fees_posting ? 'Store fees post monthly.' : 'Store fees post from January 2026.'}
          </span>
        }
      >
        Platforms
      </ScreenTitle>
      <Panel
        title="Platforms by region"
        testId="platforms-table"
        action={
          <Select
            aria-label="Region"
            data={regions}
            value={region}
            onChange={(v) => v && setRegion(v)}
            allowDeselect={false}
            w={220}
          />
        }
      >
        <RegionTable p={p} region={region} />
      </Panel>
      {own.map((pl) => (
        <OwnPlatform key={pl.platform_id} saveId={saveId} pl={pl} range={p.own_fee_range} />
      ))}
      <DeviceLines saveId={saveId} p={p} />
      <Apps saveId={saveId} p={p} />
      <DeveloperCandidates saveId={saveId} p={p} />
      <Standards saveId={saveId} p={p} />
    </>
  );
}

function RegionTable({ p, region }: { p: Platforms; region: string }) {
  const rows = useMemo<Row[]>(
    () =>
      p.platforms.flatMap((pl) => {
        const r = pl.regions.find((x) => x.region === region);
        if (!r || (r.users <= 0 && !pl.own)) return [];
        const developers =
          r.developer_share !== null && r.developer_share !== undefined
            ? formatShare(r.developer_share)
            : `${formatShare(r.developer_range[0])}–${formatShare(r.developer_range[1])}`;
        return [
          {
            platform: pl,
            users: r.users,
            developers,
            catalogue: r.catalogue_index,
            fee: r.fees.standard,
            rules: [...r.rules, ...r.rival_stores.map((s) => `${s} open`)].join('; ') || '—',
          },
        ];
      }),
    [p, region],
  );
  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor((x) => `${x.platform.name} (${x.platform.store})`, {
          id: 'platform',
          header: 'Platform',
          meta: { term: 'platform.store' },
        }),
        helper.accessor((x) => x.platform.owner_label, {
          id: 'owner',
          header: 'Owner',
          meta: { term: 'platform.store' },
        }),
        helper.accessor('users', {
          header: 'Users',
          meta: { term: 'platform.users' },
          cell: (c) => formatShare(c.getValue()),
        }),
        helper.accessor('developers', {
          header: 'Developers',
          meta: { term: 'platform.developers' },
        }),
        helper.accessor('catalogue', {
          header: 'Catalogue',
          meta: { term: 'platform.catalogue' },
          cell: (c) => c.getValue().toFixed(0),
        }),
        helper.accessor('fee', {
          header: 'Store fee',
          meta: { term: 'platform.fee' },
          cell: (c) => formatShare(c.getValue()),
        }),
        helper.accessor('rules', { header: 'Rules', meta: { term: 'platform.rules' } }),
      ]),
    [],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: rows,
    getRowId: (x) => String(x.platform.platform_id),
  });
  return <DataTable table={table} label="Platforms" rowTestId="platform-row" />;
}

function OwnPlatform({
  saveId,
  pl,
  range,
}: {
  saveId: string;
  pl: Platform;
  range: number[];
}) {
  const rules = useSetPlatformRules(saveId);
  const s = pl.settings;
  const [fee, setFee] = useState<number>(Math.round((s?.fee ?? 0.3) * PERCENT));
  const [strictness, setStrictness] = useState<string>(s?.strictness ?? 'standard');
  const [selfPref, setSelfPref] = useState<string>(s?.self_pref ?? 'off');
  const [licence, setLicence] = useState<number | ''>(
    s?.licence_cents === null || s?.licence_cents === undefined ? '' : s.licence_cents / PERCENT,
  );
  if (!s) return null;
  const devShares = pl.regions.filter((r) => r.users > 0 || (r.developer_share ?? 0) > 0);
  return (
    <Panel title={`Your platform: ${pl.name}`} testId="own-platform">
      <p className="tst-muted" style={{ marginTop: 0 }}>
        {pl.kind === 'device' ? 'Operating system and store' : 'Developer platform'} ·{' '}
        <Term term="platform.catalogue">catalogue</Term> and{' '}
        <Term term="platform.goodwill">goodwill</Term> by region:{' '}
        {devShares.length === 0
          ? 'no users yet'
          : devShares
              .map(
                (r) =>
                  `${r.label} ${formatShare(r.users)} users, ${formatShare(r.developer_share ?? 0)} developers, catalogue ${r.catalogue_index.toFixed(0)}`,
              )
              .join(' · ')}
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'end' }}>
        <NumberInput
          label="Store fee (%)"
          data-testid="own-fee-input"
          min={range[0] * PERCENT}
          max={range[1] * PERCENT}
          value={fee}
          onChange={(v) => setFee(Number(v))}
          w={140}
        />
        <Select
          label="Review"
          data={['lenient', 'standard', 'strict']}
          value={strictness}
          onChange={(v) => v && setStrictness(v)}
          w={140}
        />
        <Select
          label="Self-preferencing"
          data={['off', 'mild', 'strong']}
          value={selfPref}
          onChange={(v) => v && setSelfPref(v)}
          w={160}
        />
        {pl.kind === 'device' && (
          <NumberInput
            label="Licence to other makers ($ a unit, blank = none)"
            value={licence}
            min={0}
            onChange={(v) => setLicence(v === '' ? '' : Number(v))}
            w={260}
          />
        )}
        <Button
          data-testid="save-rules"
          loading={rules.isPending}
          onClick={() =>
            rules.mutate({
              platform_id: pl.platform_id,
              fee: fee / PERCENT,
              strictness: strictness as 'lenient' | 'standard' | 'strict',
              self_pref: selfPref as 'off' | 'mild' | 'strong',
              licence_cents: licence === '' ? null : Math.round(licence * PERCENT),
              stop_licensing: licence === '' && s.licence_cents !== null,
            })
          }
        >
          Save rules
        </Button>
      </div>
      <div style={{ display: 'flex', gap: 24, marginTop: 12 }}>
        <Switch
          label="Forbid links to pay outside (where the law allows)"
          checked={s.anti_steering}
          onChange={(e) =>
            rules.mutate({ platform_id: pl.platform_id, anti_steering: e.currentTarget.checked })
          }
        />
        <Switch
          label={
            <>
              Allow <Term term="platform.side_loading">side-loading</Term>
            </>
          }
          checked={s.side_loading}
          onChange={(e) =>
            rules.mutate({ platform_id: pl.platform_id, side_loading: e.currentTarget.checked })
          }
        />
      </div>
      {rules.error && (
        <Alert color="red" mt="sm">
          {String(rules.error.message)}
        </Alert>
      )}
    </Panel>
  );
}

function DeviceLines({ saveId, p }: { saveId: string; p: Platforms }) {
  const move = useSetDevicePlatform(saveId);
  const [choice, setChoice] = useState<Record<number, string>>({});
  if (p.device_lines.length === 0) return null;
  const options = p.platforms
    .filter((x) => x.kind === 'device' && !x.ended_label && (x.own || x.licensable))
    .map((x) => ({ value: String(x.platform_id), label: x.name }));
  return (
    <Panel title="Device lines" testId="device-lines">
      {p.device_lines.map((d) => (
        <div
          key={d.product_id}
          data-testid={`device-line-${d.product_id}`}
          style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8 }}
        >
          <strong>{d.name}</strong>
          <span>
            runs {d.platform_name}
            {d.previous_name
              ? ` (${formatShare(d.previous_share)} of its devices still on ${d.previous_name})`
              : ''}
          </span>
          <span className="tst-muted">
            <Term term="platform.catalogue">Catalogue effect</Term>:{' '}
            {Object.keys(d.catalogue_points).length === 0
              ? 'from 2026'
              : `${Math.min(...Object.values(d.catalogue_points)).toFixed(1)} feature points at worst`}
            <Explain metric="catalogue_effect" entity={d.product_id} label="Catalogue effect" />
          </span>
          <Select
            aria-label={`Platform for ${d.name}`}
            data-testid={`device-platform-${d.product_id}`}
            data={options}
            value={choice[d.product_id] ?? String(d.platform_id)}
            onChange={(v) => v && setChoice({ ...choice, [d.product_id]: v })}
            w={200}
          />
          <Button
            size="xs"
            data-testid={`switch-platform-${d.product_id}`}
            disabled={!choice[d.product_id] || choice[d.product_id] === String(d.platform_id)}
            loading={move.isPending}
            onClick={() =>
              move.mutate({ product_id: d.product_id, platform_id: Number(choice[d.product_id]) })
            }
          >
            Switch (one-off)
          </Button>
        </div>
      ))}
      {move.error && <Alert color="red">{String(move.error.message)}</Alert>}
    </Panel>
  );
}

function Apps({ saveId, p }: { saveId: string; p: Platforms }) {
  const comply = useComplyListing(saveId);
  const steering = useSetSteering(saveId);
  if (p.apps.length === 0) return null;
  return (
    <Panel title="Your apps in the stores" testId="platform-apps">
      {p.apps.map((a) => (
        <div
          key={a.product_id}
          data-testid={`platform-app-${a.product_id}`}
          style={{ marginBottom: 10 }}
        >
          <strong>{a.name}</strong> · <Term term="platform.fees_month">store fees this month</Term>{' '}
          {formatMoneyWhole(a.fees_total_cents)}
          <Explain metric="platform_fees" entity={a.product_id} label="Platform fees" />
          <Switch
            size="xs"
            style={{ display: 'inline-flex', marginLeft: 16 }}
            label="Link users to pay outside"
            checked={a.steering}
            onChange={(e) =>
              steering.mutate({ product_id: a.product_id, on: e.currentTarget.checked })
            }
          />
          {a.listings.length > 0 && (
            <div style={{ marginTop: 4 }}>
              <Term term="platform.listing">Listing</Term>:{' '}
              {a.listings
                .map(
                  (x) =>
                    `${x.platform_name} in ${x.region_label}: ${x.status}${x.answer_label ? ` (answer ${x.answer_label})` : ''}`,
                )
                .join('; ')}{' '}
              {a.listings.some((x) => x.status === 'removed') && (
                <Button
                  size="xs"
                  data-testid={`comply-${a.product_id}`}
                  loading={comply.isPending}
                  onClick={() => comply.mutate(a.product_id)}
                >
                  Comply and relist
                </Button>
              )}
            </div>
          )}
          {a.recent_actions.length > 0 && (
            <div className="tst-muted" style={{ fontSize: 12 }}>
              {a.recent_actions.join(' · ')}
            </div>
          )}
        </div>
      ))}
      {(comply.error ?? steering.error) && (
        <Alert color="red">{String((comply.error ?? steering.error)?.message)}</Alert>
      )}
    </Panel>
  );
}

function DeveloperCandidates({ saveId, p }: { saveId: string; p: Platforms }) {
  const create = useCreateDeveloperPlatform(saveId);
  if (p.developer_candidates.length === 0) return null;
  return (
    <Panel title="Developer platforms">
      <p className="tst-muted" style={{ marginTop: 0 }}>
        A model API, a cloud or a developer tool can become a platform developers build on: its
        catalogue cuts churn.
      </p>
      {p.developer_candidates.map((id) => (
        <Button
          key={id}
          size="xs"
          mr="sm"
          onClick={() => create.mutate(id)}
          loading={create.isPending}
        >
          Open product #{id} to developers
        </Button>
      ))}
      {create.error && <Alert color="red">{String(create.error.message)}</Alert>}
    </Panel>
  );
}

function Standards({ saveId, p }: { saveId: string; p: Platforms }) {
  const adopt = useAdoptStandard(saveId);
  const columns = useMemo(
    () =>
      standardHelper.columns([
        standardHelper.accessor('label', {
          header: 'Standard',
          meta: { term: 'platform.standard' },
        }),
        standardHelper.accessor((s) => s.formats.join(' vs '), {
          id: 'formats',
          header: 'Formats',
          meta: { term: 'platform.standard' },
        }),
        standardHelper.accessor('adoption', {
          header: 'First format',
          meta: { term: 'platform.standard' },
          cell: (c) => formatShare(c.getValue()),
        }),
        standardHelper.accessor((s) => (s.winner ? `${s.winner} (${s.tipped_label})` : 'open'), {
          id: 'winner',
          header: 'Winner',
          meta: { term: 'platform.standard' },
        }),
        standardHelper.display({
          id: 'adopt',
          header: '',
          cell: ({ row }) =>
            row.original.yours_on_loser.map((pid) => (
              <Button
                key={pid}
                size="xs"
                onClick={() =>
                  adopt.mutate({ product_id: pid, standard_id: row.original.standard_id })
                }
              >
                Adopt the winner for #{pid}
              </Button>
            )),
        }),
      ]),
    [adopt],
  );
  const table = useTable({
    features: gameTableFeatures,
    columns,
    data: p.standards,
    getRowId: (s) => String(s.standard_id),
  });
  if (p.standards.length === 0) return null;
  return (
    <Panel title="Standards">
      <DataTable table={table} label="Standards" rowTestId="standard-row" />
    </Panel>
  );
}
