import {
  formatAmount,
  formatDate,
  MONTH_OPTIONS,
  getYearOptions,
  getMonthLabel,
  formatLocalISODate,
} from './formatters';

describe('formatAmount', () => {
  it('formats a positive number as DKK currency', () => {
    const result = formatAmount(1234.5);

    expect(result).toMatch(/1\.234,50/);
    expect(result).toMatch(/kr/i);
  });

  it('formats zero correctly', () => {
    const result = formatAmount(0);

    expect(result).toMatch(/0,00/);
  });

  it('returns fallback for NaN input', () => {
    expect(formatAmount('abc')).toBe('Kr. 0,00');
    expect(formatAmount(undefined)).toBe('Kr. 0,00');
  });

  it('treats null as zero (Number(null) === 0)', () => {
    const result = formatAmount(null);

    expect(result).toMatch(/0,00/);
  });

  it('respects custom decimal places', () => {
    const result = formatAmount(99.999, { decimals: 0 });

    expect(result).toMatch(/100/);
    expect(result).not.toMatch(/,99/);
  });

  it('handles negative numbers', () => {
    const result = formatAmount(-500);

    expect(result).toMatch(/500,00/);
  });

  it('accepts numeric strings', () => {
    const result = formatAmount('42.5');

    expect(result).toMatch(/42,50/);
  });
});

describe('formatDate', () => {
  it('formats a valid ISO date string in Danish locale', () => {
    const result = formatDate('2025-03-15');

    expect(result).toMatch(/15/);
    expect(result).toMatch(/03/);
    expect(result).toMatch(/2025/);
  });

  it('returns "Ingen dato" for falsy input', () => {
    expect(formatDate(null)).toBe('Ingen dato');
    expect(formatDate(undefined)).toBe('Ingen dato');
    expect(formatDate('')).toBe('Ingen dato');
  });

  it('accepts custom Intl.DateTimeFormat options', () => {
    const result = formatDate('2025-06-01', { month: 'long' });

    expect(result).toMatch(/juni/i);
  });
});

describe('MONTH_OPTIONS', () => {
  it('contains all 12 months', () => {
    expect(MONTH_OPTIONS).toHaveLength(12);
  });

  it('starts with January and ends with December', () => {
    expect(MONTH_OPTIONS[0]).toEqual({ value: '01', label: 'Januar' });
    expect(MONTH_OPTIONS[11]).toEqual({ value: '12', label: 'December' });
  });

  it('uses zero-padded values', () => {
    MONTH_OPTIONS.forEach((m) => {
      expect(m.value).toHaveLength(2);
    });
  });
});

describe('getYearOptions', () => {
  it('returns years centered around the current year', () => {
    const currentYear = new Date().getFullYear();
    const years = getYearOptions();

    expect(years).toContain(currentYear);
    expect(years).toContain(currentYear - 2);
    expect(years).toContain(currentYear + 2);
    expect(years).toHaveLength(5);
  });

  it('respects custom range', () => {
    const currentYear = new Date().getFullYear();
    const years = getYearOptions(1);

    expect(years).toEqual([currentYear - 1, currentYear, currentYear + 1]);
  });
});

describe('getMonthLabel', () => {
  it('returns the label for a known month value', () => {
    expect(getMonthLabel('01')).toBe('Januar');
    expect(getMonthLabel('06')).toBe('Juni');
    expect(getMonthLabel('12')).toBe('December');
  });

  it('returns the input value when no match is found', () => {
    expect(getMonthLabel('13')).toBe('13');
    expect(getMonthLabel('unknown')).toBe('unknown');
  });
});

describe('formatLocalISODate', () => {
  it('formats a date as YYYY-MM-DD', () => {
    expect(formatLocalISODate(new Date(2025, 5, 15))).toBe('2025-06-15');
  });

  it('zero-pads single-digit months and days', () => {
    expect(formatLocalISODate(new Date(2025, 0, 1))).toBe('2025-01-01');
    expect(formatLocalISODate(new Date(2025, 8, 9))).toBe('2025-09-09');
  });

  it('uses local calendar day, not UTC', () => {
    // A Date constructed at local midnight on the 1st must serialize as that
    // 1st, even when the ambient offset pushes the UTC instant into the
    // previous day. toISOString() would regress here; formatLocalISODate
    // must not.
    const localMidnight = new Date(2025, 2, 1, 0, 0, 0);

    expect(formatLocalISODate(localMidnight)).toBe('2025-03-01');
  });

  it('formats the last day of a month correctly', () => {
    expect(formatLocalISODate(new Date(2025, 1, 0))).toBe('2025-01-31');
    expect(formatLocalISODate(new Date(2024, 2, 0))).toBe('2024-02-29');
  });
});
