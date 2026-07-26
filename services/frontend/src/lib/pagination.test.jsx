import { describe, it, expect } from 'vitest';
import { PAGE_SIZE, pageCountOf } from './pagination';

describe('PAGE_SIZE', () => {
  it('er 50 — samme sidestørrelse for liste og søgning', () => {
    expect(PAGE_SIZE).toBe(50);
  });
});

describe('pageCountOf', () => {
  it('deler op i hele sider når totalen går op', () => {
    expect(pageCountOf(100)).toBe(2);
  });

  it('runder op på en delvis sidste side', () => {
    expect(pageCountOf(93)).toBe(2);
    expect(pageCountOf(51)).toBe(2);
  });

  it('giver 1 for præcis én fuld side', () => {
    expect(pageCountOf(50)).toBe(1);
  });

  it('bunder i 1 på en tom periode, så en clamp ikke kan give side 0', () => {
    expect(pageCountOf(0)).toBe(1);
  });

  it('bunder i 1 når totalen er ukendt (null/undefined)', () => {
    expect(pageCountOf(null)).toBe(1);
    expect(pageCountOf(undefined)).toBe(1);
  });

  it('respekterer en anden sidestørrelse', () => {
    expect(pageCountOf(93, 25)).toBe(4);
  });
});
