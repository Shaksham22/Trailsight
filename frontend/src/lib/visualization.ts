import type { AccountNetwork, ActivityContext, BankCountryFlowRow, BankCountryRoute } from "../api/types.ts";
import { getBankCountryVisualizationCentroid, type BankCountryVisualizationCentroid } from "./bankCountries.ts";

export interface RouteVisualModel {
  sameCountry: boolean;
  sending: [number, number];
  receiving: [number, number];
  routeLine: Array<[[number, number], [number, number]]>;
  summary: string;
}

export function buildRouteVisualModel(route: BankCountryRoute): RouteVisualModel {
  const sending: [number, number] = [route.sending.centroid_longitude, route.sending.centroid_latitude];
  const receiving: [number, number] = [route.receiving.centroid_longitude, route.receiving.centroid_latitude];
  return {
    sameCountry: route.same_bank_country,
    sending,
    receiving,
    routeLine: route.same_bank_country ? [] : [[sending, receiving]],
    summary: route.same_bank_country ? "Same bank-country route" : `${route.sending.bank_country} → ${route.receiving.bank_country}`,
  };
}

export interface AccountBankCountryConnection {
  bankCountry: string;
  centroid: BankCountryVisualizationCentroid | null;
  incomingTransactionCount: number;
  outgoingTransactionCount: number;
  distinctCounterparties: number;
  latestInteraction: string;
  sameCountry: boolean;
}

export interface AccountBankCountryLine {
  from: [number, number];
  to: [number, number];
  bankCountry: string;
  direction: "INCOMING" | "OUTGOING";
  transactionCount: number;
  distinctCounterparties: number;
  latestInteraction: string;
}

export interface AccountBankCountryVisualModel {
  root: BankCountryVisualizationCentroid | null;
  connections: AccountBankCountryConnection[];
  incomingLines: AccountBankCountryLine[];
  outgoingLines: AccountBankCountryLine[];
  unmappedCountries: string[];
  summary: string;
}

export function buildAccountBankCountryVisualModel(rootBankCountry: string, flows: BankCountryFlowRow[]): AccountBankCountryVisualModel {
  const root = getBankCountryVisualizationCentroid(rootBankCountry);
  const connections = flows.map((flow): AccountBankCountryConnection => ({
    bankCountry: flow.bank_country,
    centroid: getBankCountryVisualizationCentroid(flow.bank_country),
    incomingTransactionCount: flow.incoming_transaction_count,
    outgoingTransactionCount: flow.outgoing_transaction_count,
    distinctCounterparties: flow.distinct_counterparties,
    latestInteraction: flow.latest_interaction,
    sameCountry: flow.bank_country === rootBankCountry,
  }));
  const incomingLines: AccountBankCountryLine[] = [];
  const outgoingLines: AccountBankCountryLine[] = [];
  if (root) {
    const rootPoint: [number, number] = [root.centroid_longitude, root.centroid_latitude];
    for (const connection of connections) {
      if (!connection.centroid || connection.sameCountry) continue;
      const connectedPoint: [number, number] = [connection.centroid.centroid_longitude, connection.centroid.centroid_latitude];
      if (connection.outgoingTransactionCount > 0) {
        outgoingLines.push({ from: rootPoint, to: connectedPoint, bankCountry: connection.bankCountry, direction: "OUTGOING", transactionCount: connection.outgoingTransactionCount, distinctCounterparties: connection.distinctCounterparties, latestInteraction: connection.latestInteraction });
      }
      if (connection.incomingTransactionCount > 0) {
        incomingLines.push({ from: connectedPoint, to: rootPoint, bankCountry: connection.bankCountry, direction: "INCOMING", transactionCount: connection.incomingTransactionCount, distinctCounterparties: connection.distinctCounterparties, latestInteraction: connection.latestInteraction });
      }
    }
  }
  const mappedNames = [...new Set(connections.map((connection) => connection.bankCountry))].sort();
  const unmappedCountries = connections.filter((connection) => !connection.centroid).map((connection) => connection.bankCountry);
  const summary = mappedNames.length
    ? `Root Bank Country: ${rootBankCountry}. Connected Bank Countries (${mappedNames.length}): ${mappedNames.join(", ")}.`
    : `Root Bank Country: ${rootBankCountry}. No Bank-Country flow rows are available in this resolved context.`;
  return { root, connections, incomingLines, outgoingLines, unmappedCountries, summary };
}

export function activityCurrencies(activity: ActivityContext): string[] {
  return [...new Set(activity.buckets.map((bucket) => bucket.currency))].sort();
}

export function activityBucketsForCurrency(activity: ActivityContext, currency: string) {
  return activity.buckets.filter((bucket) => bucket.currency === currency);
}

export function graphTruncationText(network: AccountNetwork): string | null {
  if (!network.truncated) return null;
  return `Showing ${network.shown_counterparties} of ${network.total_direct_counterparties} direct counterparties from the backend-bounded one-hop network.`;
}
