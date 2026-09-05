const ISO_UTC_SOURCE = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?(Z|[+-]\d{2}:?\d{2})?)?$/i;

export function formatUtc(value: string) {
  const match = ISO_UTC_SOURCE.exec(value);
  if (!match) return value;

  const [, yearText, monthText, dayText, hourText = "00", minuteText = "00", secondText = "00", , zone] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const second = Number(secondText);
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  if (month < 1 || month > 12 || day < 1 || day > daysInMonth || hour > 23 || minute > 59 || second > 59) return value;

  const datePart = `${yearText}-${monthText}-${dayText}`;
  const timePart = `${hourText}:${minuteText}:${secondText}`;
  const normalized = `${datePart}T${timePart}${zone ?? "Z"}`;
  const date = new Date(normalized);
  if (Number.isNaN(date.valueOf())) return value;

  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("month")} ${part("day")}, ${part("year")} · ${part("hour")}:${part("minute")} ${part("dayPeriod")} UTC`;
}

export function formatUtcDate(value: string) {
  const formatted = formatUtc(value);
  const separator = formatted.indexOf(" · ");
  return separator === -1 ? formatted : formatted.slice(0, separator);
}
