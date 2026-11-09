import type { Schemas } from '../api/client';
import { formatMoneyWhole, formatWhole } from './format';

type Unit = Schemas['ExplainOut']['unit'];

/** A number as the API sent it, in its unit; display only. */
export function formatUnit(value: number, unit: Unit, signed = false): string {
  const sign = signed && value > 0 ? '+' : '';
  switch (unit) {
    case 'cents':
      return sign + formatMoneyWhole(Math.round(value));
    case 'percent':
      return `${sign}${value.toFixed(Math.abs(value) < 10 ? 2 : 1)}%`;
    case 'count':
      return sign + formatWhole(value);
    case 'months':
      return `${sign}${value.toFixed(1)} months`;
    default:
      return `${sign}${value.toFixed(1)}`;
  }
}
