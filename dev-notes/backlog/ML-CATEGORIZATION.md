# ML categorization backlog — getting started, feedback loop, taxonomy smarts

Companion to [FEATURES.md](FEATURES.md) (F1-02 user rules, F1-03 feedback loop, F1-06 ML tier), [BACKLOG.md](BACKLOG.md) (P2-06 wire rules DB) and [AI-IMPROVEMENTS.md](AI-IMPROVEMENTS.md) (AI-14 shares the embedding-classifier pattern, AI-16 shares the feedback pattern). IDs `ML-xx` are stable.

Current state (see [architecture/services/categorization-and-ai-services.md](../architecture/services/categorization-and-ai-services.md)): tier orchestrator has **ready but empty ML/LLM slots** (`Optional` ports, nothing injected); rules tier live from a hardcoded seed dict; `categorization_results` records tier/confidence/needs_review for every decision (an audit log that becomes training data); `merchants` table has a dead `is_user_confirmed` flag; taxonomy (categories + subcategories, "Anden" fallback) is owned here per ADR-003. Transactions are short Danish strings ("REMA1000 KOEBENHAVN", "MobilePay Anabelle…") with amount/sign/date metadata.

**Ground rules** (mirror the AI backlog): **ML-01 eval set first** — every later item must prove itself against it. And **precision beats coverage**: a wrong auto-category costs more trust than a `needs_review`. The tier order is a precision ladder — each tier only sees what the more precise tier above couldn't decide.

## M1 — Getting started (no model until the cheap things are exhausted)

| ID | Idea | What & why | Builds on | Effort | Status |
|----|------|-----------|-----------|--------|--------|
| ML-01 | **Labeled dataset + eval harness** | Assemble labels from what already exists: manual corrections (gold), rule-engine hits (high-precision silver), seed mappings. Frozen golden set (~300 rows, stratified per category incl. hard cases: MobilePay person-names, sign-dependent merchants). Metrics: accuracy, per-category confusion matrix, coverage-vs-precision curve. pytest-marker runnable, report in CI | `categorization_results` table already logs every decision with tier+confidence — the dataset is sitting in Postgres | M | open |
| ML-02 | **Per-user merchant memory (tier 1.5)** | Before ANY model: a learned per-user map `normalized_merchant → subcategory` from confirmed corrections — highest possible precision, instant effect after one correction. This alone typically resolves the recurring 80% of a user's transactions | `merchants` table + dead `is_user_confirmed` flag; F1-03's correction event provides the writes | S | open |
| ML-03 | **Shared text-normalization module** | One canonical pipeline (casefold, æ/ø/å transliteration, strip card suffixes/dates/MobilePay prefixes, extract counterparty) used by rule engine, merchant memory AND all ML tiers. Feature quality = normalization quality for strings this short; today normalization lives only inside the rule engine | Rule engine's existing transliteration/keyword logic — extract, don't rewrite | S | open |
| ML-04 | **Baseline model: char-n-gram TF-IDF + linear classifier** | scikit-learn logistic/LinearSVC on 2-5 char n-grams of normalized text (+ ML-08 features). Handles "REMA1000"/"REMA 1000"/"REMA1000 668" without word boundaries; interpretable; trains in seconds on thousands of rows. This is the champion to beat — embeddings must outperform it on ML-01 to earn their latency | Label store from ML-01; joblib artifact, no new infra | M | open |
| ML-05 | **Wire the ML port — in shadow mode first** | Implement `IMLCategorizer` and inject into the orchestrator, but log-only: record ML prediction + confidence into `categorization_results` alongside the actual (rule/fallback) decision, never apply. After N weeks of shadow agreement stats, flip on with a confidence threshold (config). Activation of the existing empty slot, de-risked | Orchestrator's ML slot + results table already shaped for exactly this (tier column) | M | open |

## M2 — The feedback flywheel

| ID | Idea | What & why | Builds on | Effort | Status |
|----|------|-----------|-----------|--------|--------|
| ML-06 | **Correction event → label store** | `transaction.category_corrected` event (same event F1-03 defines) consumed into a `training_labels` table: normalized text, features, old→new subcategory, user_id, source (manual/confirm), timestamp. The flywheel's fuel line — every UI correction becomes a training row automatically | Outbox/consumer machinery everywhere; contract addition | S | open |
| ML-07 | **needs_review inbox (active learning)** | Frontend queue of low-confidence categorizations for one-click confirm/correct, ordered by frequency × uncertainty (fixing the top uncertain merchant fixes hundreds of rows). Confirmations are gold labels via ML-06. `needs_review` is already set by the pipeline — it's just never shown to anyone | `needs_review` + confidence already persisted per result | M | open |
| ML-08 | **Beyond text: metadata features** | Amount magnitude buckets, sign, weekday/day-of-month, recurrence flag (from F2-01 series), same-merchant history. Sign-dependent categories (renter, MobilePay in/out) are currently *hardcoded* rule overrides — learned priors replace brittle special cases | Feature builder in ML-03's module; F2-01 detections | M | open |
| ML-09 | **Champion/challenger retrain job** | Weekly worker: retrain on the label store, evaluate vs frozen golden set + current champion; promote only on non-regression; artifact + `model_version` stamped into `categorization_results` (so any decision is reproducible). Never silent hot-swaps | ML-01 harness; worker patterns everywhere in repo | M | open |
| ML-10 | **Quality monitoring & drift alerts** | Weekly per-tier metrics from data already collected: fallback-rate, correction-rate (corrections/decisions), shadow-agreement. Alert via notification service when correction rate spikes (new bank format, taxonomy change, drift) | `categorization_results` + ML-06 labels; F1-01 for alerting | S | open |

## M3 — Category detection & smart subcategories

| ID | Idea | What & why | Builds on | Effort | Status |
|----|------|-----------|-----------|--------|--------|
| ML-11 | **Hierarchical two-stage classification** | Predict parent category first, then subcategory *within* that parent. Masks impossible subcategories, concentrates sparse training data, and guarantees valid parent-child pairs by construction (today validated only at write time) | Taxonomy read-copies carry the hierarchy everywhere | M | open |
| ML-12 | **Two-level confidence → partial application** | When category is confident but subcategory isn't: apply the parent + that category's fallback subcategory with `needs_review`, instead of dumping into global "Anden". "Mad → uspecificeret" is far more useful than "Anden" and pre-filters the ML-07 inbox | ML-11's two-stage scores; "Anden"-style fallback concept exists (currently name-pinned — fix alongside the followups item) | M | open |
| ML-13 | **Taxonomy embeddings for zero-shot & cold start** | Embed each subcategory (name + synonyms + description — add these fields to taxonomy CRUD) with bge-m3; cosine similarity between transaction text and subcategory embedding as (a) a feature for ML-04, (b) the *only* classifier for a freshly user-created subcategory with zero training rows. Solves "user adds 'Padel' subcategory, nothing ever lands in it" | bge-m3 already served by Ollama; taxonomy events propagate new subcategories everywhere; ingest-side synonym enrichment in ai-service proves the synonym pattern | M | open |
| ML-14 | **LLM tier as bounded last resort** | qwen3 via Ollama, constrained JSON (choice restricted to the user's actual taxonomy — same constrained-sampling pattern as the ai-service router), invoked ONLY for rows the ML tier left `needs_review`, cached by normalized text. Output is a *weak* label: applied with needs_review flag, confirmed via ML-07 before it enters training data. Fills the empty LLM slot exactly as the orchestrator intended | Empty LLM port; Ollama infra; router's constrained-JSON prompt pattern | M | open |
| ML-15 | **Cross-user merchant priors (privacy-gated)** | Global `merchant → subcategory` distribution across users as a prior feature — "everyone labels REMA 1000 as Dagligvarer". Only for merchants seen across ≥K users and never exposing individual data; personal corrections (ML-02) always outrank the prior | Merchant memory data model from ML-02 | M | open |

## Links to ai-service (deliberate cross-pollination)

- **Shared "bge-m3 + light head" pattern**: ML-04/ML-13 and AI-14 (intent pre-classifier) are the same architecture — build the embedding-classifier utility once, use it in both services.
- **Better categories = better RAG**: every categorization improvement directly upgrades ai-service's metadata filters (AI-02), summary docs (AI-09) and aggregation answers (AI-03) — the chat is a downstream consumer of this backlog.
- **Shared feedback UX**: ML-07's confirm/correct inbox and AI-16's 👍/👎 are one product surface ("hjælp appen med at lære") — design them together.
- **LLM prompt patterns**: ML-14 reuses the router's constrained-sampling approach; keep the prompt conventions (Danish, 4T's) consistent across services.

## Sequencing

```
ML-01 eval set ──► gate for everything
Wave 1 (no models): ML-02 merchant memory + ML-03 normalization + ML-06 label store + ML-07 inbox
                    ← this alone gives users a visible "it learns!" moment
Wave 2 (baseline):  ML-04 champion → ML-05 shadow mode → activate on threshold
Wave 3 (quality):   ML-08 features → ML-11 hierarchy → ML-12 partial application → ML-09 retrain loop → ML-10 monitoring
Wave 4 (frontier):  ML-13 zero-shot taxonomy → ML-14 LLM tier → ML-15 global priors
```

Prereqs from the technical backlog: P2-06 (rules DB wired, consumer uses the orchestrator — otherwise the ML tier can never run on the async path) is a **hard prerequisite** for ML-05 onward.

## Parked (with reason)

- **Fine-tuned transformer classifier** — per-user data is small; char-n-gram + embeddings + hierarchy will saturate the eval set first. Revisit only if ML-09's curve plateaus with clear headroom.
- **External merchant/MCC databases** — licensing + Danish coverage questionable; ML-15's own-user priors are the same idea with better data.
- **Auto-applying LLM labels without review** — violates the precision ladder; weak labels must pass ML-07 confirmation before training or silent auto-apply.
