import type { CurrencyActivityRow } from "../api/types";

const countFormatter = new Intl.NumberFormat("en-CA");
const amountFormatter = new Intl.NumberFormat("en-CA", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const percentileFormatter = new Intl.NumberFormat("en-CA", {
  maximumFractionDigits: 2,
});

export type ActivityDirection = "incoming" | "outgoing";

export interface DirectionAmountLine {
  currency: string;
  text: string;
}

export interface CurrencyAmountComparison {
  currency: string;
  difference: string;
}

export function formatCount(value: number) {
  return countFormatter.format(value);
}

export function summarizeTransactionCounts(incoming: number, outgoing: number) {
  const total = incoming + outgoing;
  const difference = Math.abs(incoming - outgoing);
  const differenceText = difference === 0
    ? "Balanced transaction count"
    : `${formatCount(difference)} more ${incoming > outgoing ? "incoming" : "outgoing"}`;
  return {
    total,
    difference,
    totalText: `${formatCount(total)} transaction${total === 1 ? "" : "s"}`,
    differenceText,
  };
}

export function formatDetectorStanding(percentile: string | null) {
  if (percentile === null) return { primary: "Not scored", secondary: "Relative standing unavailable" };
  const value = Number(percentile);
  if (!Number.isFinite(value) || value < 0 || value > 100) {
    return { primary: "Not scored", secondary: "Relative standing unavailable" };
  }
  const topPercent = Math.max(0, Math.min(100, 100 - value));
  return {
    primary: `${formatMeaningfulPercent(value)}th percentile`,
    secondary: `Top ${formatMeaningfulPercent(topPercent)}% of eligible accounts`,
  };
}

function formatMeaningfulPercent(value: number) {
  const concise = percentileFormatter.format(value);
  const rounded = Number(concise.replace(/,/g, ""));
  if ((value > 0 && rounded === 0) || (value < 100 && rounded === 100)) {
    return new Intl.NumberFormat("en-CA", { maximumSignificantDigits: 8 }).format(value);
  }
  return concise;
}

export function formatOverviewAmount(value: string, currency: string) {
  const amount = Number(value);
  return Number.isFinite(amount) ? `${currency} ${amountFormatter.format(amount)}` : `${currency} ${value}`;
}

export function directionAmountLines(rows: CurrencyActivityRow[], direction: ActivityDirection): DirectionAmountLine[] {
  return rows.flatMap((row) => {
    const count = direction === "incoming" ? row.incoming_count : row.outgoing_count;
    if (count <= 0) return [];
    return [{
      currency: row.currency,
      text: formatOverviewAmount(direction === "incoming" ? row.incoming_amount : row.outgoing_amount, row.currency),
    }];
  });
}

export function buildCurrencyAmountComparisons(rows: CurrencyActivityRow[]): CurrencyAmountComparison[] {
  return rows.flatMap((row) => {
    if (row.incoming_count <= 0 || row.outgoing_count <= 0) return [];
    const incoming = Number(row.incoming_amount);
    const outgoing = Number(row.outgoing_amount);
    if (!Number.isFinite(incoming) || !Number.isFinite(outgoing)) return [];
    const difference = Math.abs(incoming - outgoing);
    const differenceText = difference === 0
      ? `${row.currency} amounts are balanced`
      : `${formatOverviewAmount(String(difference), row.currency)} more ${incoming > outgoing ? "incoming" : "outgoing"}`;
    return [{
      currency: row.currency,
      difference: differenceText,
    }];
  });
}
