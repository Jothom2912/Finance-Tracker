export const BANK_FORMAT_OPTIONS = [
  { value: 'internal', label: 'Intern CSV' },
  { value: 'nordea', label: 'Nordea' },
  { value: 'danske_bank', label: 'Danske Bank' },
];

/**
 * Upload-grænse for CSV-import, spejlet fra transaction-services
 * `CSV_MAX_BYTES` (P2-29).
 *
 * Bevidst duplikeret frem for hentet fra serveren: dette tal er ren UX — det
 * sparer brugeren en upload der ellers ville løbe ind i apiClient's
 * 30s-timeout for derefter at blive afvist. Serveren er den autoritative
 * håndhæver og svarer 413 uanset hvad der står her, så fejlmoden ved drift er
 * en let forkert klient-besked, ikke en omgåelse.
 */
export const CSV_MAX_BYTES = 10 * 1024 * 1024;
