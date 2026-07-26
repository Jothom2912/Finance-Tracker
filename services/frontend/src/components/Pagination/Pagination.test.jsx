import { vi, describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Pagination from './Pagination';

function setup(props = {}) {
  const onPageChange = vi.fn();
  const { container, rerender } = render(
    <Pagination page={1} totalCount={93} onPageChange={onPageChange} {...props} />,
  );
  const rerenderWith = (next) =>
    rerender(
      <Pagination page={1} totalCount={93} onPageChange={onPageChange} {...props} {...next} />,
    );
  return { onPageChange, container, rerenderWith };
}

const forrige = () => screen.getByRole('button', { name: 'Forrige side' });
const naeste = () => screen.getByRole('button', { name: 'Næste side' });

describe('Pagination', () => {
  describe('tællelinjen', () => {
    it('viser rækkeinterval og total på første side', () => {
      setup({ page: 1, totalCount: 93 });

      expect(screen.getByText('Viser 1–50 af 93 transaktioner')).toBeInTheDocument();
    });

    it('afkorter intervallet på sidste, delvise side', () => {
      setup({ page: 2, totalCount: 93 });

      expect(screen.getByText('Viser 51–93 af 93 transaktioner')).toBeInTheDocument();
    });

    it('vises også når der kun er én side — det er svaret på "var det alt?"', () => {
      setup({ page: 1, totalCount: 37 });

      expect(screen.getByText('Viser 1–37 af 37 transaktioner')).toBeInTheDocument();
    });

    it('regner med en anden sidestørrelse', () => {
      setup({ page: 3, totalCount: 93, pageSize: 25 });

      expect(screen.getByText('Viser 51–75 af 93 transaktioner')).toBeInTheDocument();
    });

    it('er en høflig live-region, så sideskift annonceres', () => {
      setup();

      const status = screen.getByRole('status');
      expect(status).toHaveAttribute('aria-live', 'polite');
      expect(status).toHaveTextContent('Viser 1–50 af 93 transaktioner');
    });

    // Live-regionen skal blive monteret på tværs af sideskift, så kun teksten
    // muteres. Bliver den unmountet og monteret igen (fx ved at flytte den ind
    // i `pageCount > 1 && …`) tæller det som to ændringer og oplæseren
    // annoncerer to gange per klik.
    it('er den SAMME node efter et sideskift — kun teksten muteres', () => {
      const { rerenderWith } = setup({ page: 1, totalCount: 93 });
      const before = screen.getByRole('status');

      rerenderWith({ page: 2 });

      const after = screen.getByRole('status');
      expect(after).toBe(before);
      expect(after).toHaveTextContent('Viser 51–93 af 93 transaktioner');
    });

    // Samme egenskab i den anden retning: går man fra flere sider til én
    // (fx efter at et filter smalner resultatet), forsvinder knapperne, men
    // tællelinjen skal overleve som node.
    it('overlever at knapperne forsvinder ved fald til én side', () => {
      const { rerenderWith } = setup({ page: 1, totalCount: 93 });
      const before = screen.getByRole('status');

      rerenderWith({ totalCount: 12 });

      expect(screen.getByRole('status')).toBe(before);
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });
  });

  describe('tom / ukendt total', () => {
    it('rendrer intet ved totalCount = 0, så en tom periode ikke får "Side 1 af 1"', () => {
      const { container } = setup({ totalCount: 0 });

      expect(container).toBeEmptyDOMElement();
    });

    it('rendrer intet før serveren har svaret (totalCount = null)', () => {
      const { container } = setup({ totalCount: null });

      expect(container).toBeEmptyDOMElement();
    });
  });

  describe('knapper', () => {
    it('skjuler knapperne ved én side, men beholder tællelinjen', () => {
      setup({ page: 1, totalCount: 37 });

      expect(screen.queryByRole('button')).not.toBeInTheDocument();
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('viser sidetal og sideantal', () => {
      setup({ page: 2, totalCount: 93 });

      expect(screen.getByText('Side 2 af 2')).toBeInTheDocument();
    });

    it('kalder onPageChange med næste side', () => {
      const { onPageChange } = setup({ page: 1, totalCount: 93 });

      fireEvent.click(naeste());

      expect(onPageChange).toHaveBeenCalledWith(2);
    });

    it('kalder onPageChange med forrige side', () => {
      const { onPageChange } = setup({ page: 2, totalCount: 93 });

      fireEvent.click(forrige());

      expect(onPageChange).toHaveBeenCalledWith(1);
    });

    it('disabler Forrige på første side', () => {
      setup({ page: 1, totalCount: 93 });

      expect(forrige()).toBeDisabled();
      expect(naeste()).toBeEnabled();
    });

    it('disabler Næste på sidste side', () => {
      setup({ page: 2, totalCount: 93 });

      expect(naeste()).toBeDisabled();
      expect(forrige()).toBeEnabled();
    });

    it('har begge knapper aktive på en mellemside', () => {
      setup({ page: 2, totalCount: 200 });

      expect(forrige()).toBeEnabled();
      expect(naeste()).toBeEnabled();
    });

    it('bruger rigtig disabled, ikke aria-disabled', () => {
      setup({ page: 1, totalCount: 93 });

      expect(forrige()).not.toHaveAttribute('aria-disabled');
    });
  });

  describe('a11y', () => {
    it('ligger i en navigation med dansk label', () => {
      setup();

      expect(screen.getByRole('navigation', { name: 'Sidenavigation' })).toBeInTheDocument();
    });

    // WCAG 2.5.3 Label in Name: talestyring skal kunne sige den synlige tekst.
    it('har aria-labels der indeholder den synlige knaptekst', () => {
      setup({ page: 2, totalCount: 200 });

      expect(forrige()).toHaveAccessibleName('Forrige side');
      expect(forrige()).toHaveTextContent('Forrige');
      expect(naeste()).toHaveAccessibleName('Næste side');
      expect(naeste()).toHaveTextContent('Næste');
    });
  });
});
