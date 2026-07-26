import { PAGE_SIZE, pageCountOf } from '../../lib/pagination';
import './Pagination.css';

/**
 * Pager til transaktionslisten og søgeresultaterne.
 *
 * Tællelinjen er komponentens egentlige formål: den svarer på spørgsmålet
 * "er det alt der var?", som en tabel uden total ikke kan svare på. Derfor
 * vises den ALTID når der er rækker — også når der kun er én side, hvor
 * "Viser 1–37 af 37 transaktioner" er modgiften mod netop den tvivl. Kun
 * knapperne skjules ved én side.
 *
 * @param {number} page             1-indekseret aktuel side
 * @param {number|null} totalCount  rækker i alt; null = serveren har ikke svaret endnu
 * @param {number} pageSize
 * @param {(page: number) => void} onPageChange
 */
function Pagination({ page, totalCount, pageSize = PAGE_SIZE, onPageChange }) {
  // Ingen rækker (eller intet svar endnu) → ingen pager. Ellers ville en
  // reelt tom periode få "Side 1 af 1" stående ved siden af tomtilstanden.
  if (!totalCount || totalCount <= 0) return null;

  const pageCount = pageCountOf(totalCount, pageSize);
  const firstRow = (page - 1) * pageSize + 1;
  const lastRow = Math.min(page * pageSize, totalCount);

  return (
    <nav className="pagination" aria-label="Sidenavigation">
      {/*
        Bliver monteret så længe der er rækker, så kun teksten muteres og
        oplæseren annoncerer én gang per sideskift i stedet for to (unmount
        + mount af en live-region tæller som to ændringer).
      */}
      <p className="pagination-count" role="status" aria-live="polite">
        Viser {firstRow}–{lastRow} af {totalCount} transaktioner
      </p>

      {pageCount > 1 && (
        <div className="pagination-controls">
          {/*
            Rigtig `disabled` ved kanterne, ikke aria-disabled: repoet har
            intet aria-disabled-mønster. Accepteret omkostning: et klik til
            sidste side disabler den fokuserede knap og taber fokus til
            <body> — role="status"-annonceringen er kompensationen.
            Knapperne disables IKKE under hentning: hurtigt næste-næste er
            legitimt, og keepPreviousData håndterer overlappet.
          */}
          <button
            type="button"
            className="pagination-btn"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            // Indeholder den synlige tekst "Forrige" — WCAG 2.5.3 (Label in Name).
            aria-label="Forrige side"
          >
            Forrige
          </button>
          <span className="pagination-position">
            Side {page} af {pageCount}
          </span>
          <button
            type="button"
            className="pagination-btn"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= pageCount}
            aria-label="Næste side"
          >
            Næste
          </button>
        </div>
      )}
    </nav>
  );
}

export default Pagination;
