const daLocale = 'da-DK';

export function formatAmount(amount, { decimals = 2 } = {}) {
  const num = Number(amount);
  if (Number.isNaN(num)) return 'Kr. 0,00';

  return new Intl.NumberFormat(daLocale, {
    style: 'currency',
    currency: 'DKK',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num);
}

export function formatDate(dateString, options = {}) {
  if (!dateString) return 'Ingen dato';

  try {
    const date = new Date(dateString);
    return date.toLocaleDateString(daLocale, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      ...options,
    });
  } catch {
    return String(dateString);
  }
}

export const MONTH_OPTIONS = [
  { value: '01', label: 'Januar' },
  { value: '02', label: 'Februar' },
  { value: '03', label: 'Marts' },
  { value: '04', label: 'April' },
  { value: '05', label: 'Maj' },
  { value: '06', label: 'Juni' },
  { value: '07', label: 'Juli' },
  { value: '08', label: 'August' },
  { value: '09', label: 'September' },
  { value: '10', label: 'Oktober' },
  { value: '11', label: 'November' },
  { value: '12', label: 'December' },
];

export function getYearOptions(range = 2) {
  const currentYear = new Date().getFullYear();
  const years = [];
  for (let i = currentYear - range; i <= currentYear + range; i++) {
    years.push(i);
  }
  return years;
}

export function getMonthLabel(monthValue) {
  return MONTH_OPTIONS.find((m) => m.value === monthValue)?.label || monthValue;
}

export function getMonthName(monthNumber) {
  const idx = Number(monthNumber) - 1;
  return MONTH_OPTIONS[idx]?.label || String(monthNumber);
}

// Formats a Date as YYYY-MM-DD using the caller's local calendar day.
// Date.prototype.toISOString() would convert to UTC first, which can flip
// the day near midnight for users in offsets like UTC+1 (DK). This helper
// is safe for <input type="date"> values, which are always interpreted
// as a local calendar date by the browser.
export function formatLocalISODate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}
