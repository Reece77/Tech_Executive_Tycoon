// TanStack Query hooks for financial services and currencies (M54, formulas.md 64): the Bank,
// Payments, Insurance and Currency screens (one view) and the founder's finance and currency
// actions. Kept beside hooks/api.ts so lanes' hooks merge cleanly. No game values are computed
// here.
import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Schemas } from '../api/client';
import { unwrap, useInvalidateSave } from './api';

export type Finserv = Schemas['FinservScreenOut'];
export type BankScreen = Schemas['BankScreenOut'];
export type Bank = Schemas['OwnBankOut'];
export type PaymentsScreen = Schemas['PaymentsScreenOut'];
export type PaymentsRegion = Schemas['PaymentsRegionOut'];
export type InsuranceScreen = Schemas['InsuranceScreenOut'];
export type CurrencyScreen = Schemas['CurrencyScreenOut'];
export type CurrencyRegion = Schemas['CurrencyRegionOut'];
export type Hedge = Schemas['HedgeOut'];

const path = (saveId: string) => ({ params: { path: { save_id: saveId } } });

export function useFinserv(saveId: string) {
  return useQuery({
    queryKey: ['saves', saveId, 'finserv'],
    queryFn: async () => unwrap(await api.GET('/api/saves/{save_id}/finserv', path(saveId))),
    enabled: saveId !== '',
  });
}

function useAct<B>(saveId: string, send: (body: B) => Promise<unknown>) {
  const invalidate = useInvalidateSave(saveId);
  return useMutation({ mutationFn: send, onSuccess: () => void invalidate() });
}

export function useApplyCharter(saveId: string) {
  return useAct(saveId, async (body: Schemas['RegionIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/finserv/charter', { ...path(saveId), body })),
  );
}

export function usePartnerBank(saveId: string) {
  return useAct(saveId, async (body: Schemas['RegionIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/finserv/partner', { ...path(saveId), body })),
  );
}

export function useSetBank(saveId: string) {
  return useAct(saveId, async (args: { bankId: number; body: Schemas['BankSettingsIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/finserv/banks/{bank_id}/settings', {
        params: { path: { save_id: saveId, bank_id: args.bankId } },
        body: args.body,
      }),
    ),
  );
}

export function useBankCapital(saveId: string) {
  return useAct(saveId, async (args: { bankId: number; body: Schemas['AmountIn'] }) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/finserv/banks/{bank_id}/capital', {
        params: { path: { save_id: saveId, bank_id: args.bankId } },
        body: args.body,
      }),
    ),
  );
}

export function useLaunchNetwork(saveId: string) {
  return useAct(saveId, async (body: Schemas['RegionIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/finserv/networks', { ...path(saveId), body })),
  );
}

export function useApplyInsuranceLicence(saveId: string) {
  return useAct(saveId, async (body: Schemas['RegionIn']) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/finserv/insurance/licence', { ...path(saveId), body }),
    ),
  );
}

export function useInsurerCapital(saveId: string) {
  return useAct(saveId, async (body: Schemas['AmountIn']) =>
    unwrap(
      await api.POST('/api/saves/{save_id}/finserv/insurance/capital', { ...path(saveId), body }),
    ),
  );
}

export function useBuyForward(saveId: string) {
  return useAct(saveId, async (body: Schemas['ForwardIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/finserv/forwards', { ...path(saveId), body })),
  );
}

export function useSetHedgeProgramme(saveId: string) {
  return useAct(saveId, async (body: Schemas['ProgrammeIn']) =>
    unwrap(await api.POST('/api/saves/{save_id}/finserv/programme', { ...path(saveId), body })),
  );
}
