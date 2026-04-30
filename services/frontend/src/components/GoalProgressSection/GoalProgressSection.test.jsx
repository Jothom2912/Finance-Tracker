
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import GoalProgressSection from './GoalProgressSection';

const mockGoals = [
  {
    id: 1,
    name: 'Ferie',
    targetAmount: 10000,
    currentAmount: 3500,
    targetDate: '2026-09-01',
    status: 'active',
    percentComplete: 35.0,
  },
  {
    id: 2,
    name: 'Nødopsparing',
    targetAmount: 50000,
    currentAmount: 50000,
    targetDate: null,
    status: 'completed',
    percentComplete: 100.0,
  },
];

describe('GoalProgressSection', () => {
  it('renders all goals', () => {
    render(<GoalProgressSection goals={mockGoals} />);

    expect(screen.getByText('Sparemål')).toBeInTheDocument();
    expect(screen.getByText('Ferie')).toBeInTheDocument();
    expect(screen.getByText('Nødopsparing')).toBeInTheDocument();
  });

  it('shows completion badge for completed goals', () => {
    render(<GoalProgressSection goals={mockGoals} />);

    expect(screen.getByText('Nået!')).toBeInTheDocument();
  });

  it('shows percentage for each goal', () => {
    render(<GoalProgressSection goals={mockGoals} />);

    expect(screen.getByText('35%')).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('shows deadline when present', () => {
    render(<GoalProgressSection goals={mockGoals} />);

    expect(screen.getByText(/Deadline:/)).toBeInTheDocument();
  });

  it('renders empty state when no goals', () => {
    render(<GoalProgressSection goals={[]} />);

    expect(screen.getByText(/Ingen sparemål oprettet/)).toBeInTheDocument();
  });

  it('renders empty state when goals is null', () => {
    render(<GoalProgressSection goals={null} />);

    expect(screen.getByText(/Ingen sparemål oprettet/)).toBeInTheDocument();
  });
});
