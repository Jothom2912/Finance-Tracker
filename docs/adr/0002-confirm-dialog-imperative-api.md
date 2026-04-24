# ADR-0002: Imperative provider API for ConfirmDialog

**Date:** 2026-04-24
**Status:** Accepted, implemented in commits `69f22bb` (provider) and `f1bee1d` (call-site replacements).
**Context:** Phase 2.3 of the frontend a11y/UX uplift replaced six `window.confirm` call sites with a Radix Dialog-backed component. Two API shapes were on the table.

## Decision

Use an **imperative provider + hook** API:

```jsx
const confirm = useConfirm();
const ok = await confirm({
  title: 'Slet transaktion?',
  message: 'Transaktionen slettes permanent.',
  confirmLabel: 'Slet',
  variant: 'danger',
});
if (!ok) return;
```

A single `<ConfirmDialogProvider>` is mounted in `AppWithAuth` next to `NotificationProvider`. There is exactly one `<Dialog.Root>` rendered in the tree, configured per call via promise.

## Alternatives considered

**B. Declarative component with local state at each call site:**

```jsx
const [confirmOpen, setConfirmOpen] = useState(false);
// ... in JSX:
<ConfirmDialog
  open={confirmOpen}
  onOpenChange={setConfirmOpen}
  onConfirm={handleDelete}
  title="Slet transaktion?"
  variant="danger"
/>
```

B is closer to Radix' own API shape, has no async bridge between caller and rendered UI, and was the pattern initially recommended during the Phase 2.3 design discussion ("5 call sites is below the threshold for a provider; Radix is already declarative; B avoids an extra abstraction layer").

## Rationale for choosing A

Three reasons, in order of weight:

1. **Pattern consistency with the existing codebase.** `NotificationProvider` already establishes the imperative-provider-plus-hook pattern for cross-cutting UI orchestration in this same app. Introducing a second pattern (declarative-with-local-state) for a structurally similar concern (modal-style overlay surface, mounted globally, configured per use) would create two ways to do the same kind of thing. The cost of "yet another provider" is lower when an established template exists.

2. **Homogeneous call sites.** All six replacement sites are destructive-delete confirmations with the same shape: title + short message + danger variant. The declarative B would require six `useState(false)` + six JSX renders for configuration that is effectively constant per site. The imperative A collapses that to one hook call per site.

3. **Migration risk in the replacement commit.** The shape `if (!await confirm({...})) return` is a one-line, line-for-line equivalent of `if (!window.confirm(...)) return`. The declarative B would have required a structural refactor at every call site (lift state, render JSX, wire callbacks), making the replacement commit harder to verify and review.

## Honest note on how the decision was made

The decision was made by pattern-matching on `NotificationProvider`, not by deliberately weighing A against B. The three rationales above were articulated post-implementation, not before. The original Phase 2.3 design recommendation (B) was therefore not formally rebutted before code landed; this ADR closes that gap retrospectively.

This is documented here rather than hidden because (a) the rationales for A still hold up in retrospect, and (b) the lesson — "flag deviations from a recommendation explicitly, before implementing" — is more valuable than the rationalisation.

## Consequences

- One `<ConfirmDialogProvider>` is the canonical place for confirm-dialog rendering. New destructive actions use `useConfirm()`; they do not import `<ConfirmDialog>` directly.
- The provider serialises pending confirms: opening a new one resolves any prior pending confirm as `false`. This is acceptable because confirms are short-lived modal interactions; a chained "confirm → confirm" flow would need a different shape.
- Cancel is rendered before Confirm in DOM order so default focus and Enter-press behaviour favour the safe option for `variant=danger`.

## Re-evaluate if

- Non-destructive confirms are added (e.g. multi-step wizards, long-form content) where the homogeneity argument no longer holds.
- A confirm flow needs to nest inside another confirm (the serialisation-as-cancel behaviour becomes wrong).
- A future contributor introduces a second declarative dialog component for a similar concern — at that point the consistency argument has already been broken and this ADR should be reconsidered rather than silently worked around.
