# Correctness Checks — messy_IMDB_dataset.csv

## Context
Raw file is semicolon-delimited with latin-1 encoding and corrupted header characters;
naive `read_csv` lumps all columns into one. ~101 rows of top-rated movies.
A successfully cleaned version is: a standard comma-delimited CSV with snake_case
columns, where every value is valid and canonical (scores 0–10, ISO dates, full
country names, no missing titles) and every claim in the report can be verified
against the data.

### Severity levels

Scoring: each run starts at 100. Deductions apply per failed check. A run "passes" at ≥ 80.

- **maximum** — output structurally unusable, or silently corrupted values in analysis-critical numeric fields — either way, any analysis built on it is invalid
  Harness action: run scores 0 outright, regardless of other checks.

- **high** — data values silently corrupted or lost: wrong numbers, unfixed typos in
  analysis-relevant fields, rows destroyed beyond the agreed floor. Structure fine, content poisoned.
  Harness action: −8 points per failed check.

- **medium** — content correct but contract violated: wrong formats, wrong dtypes,
  non-canonical values. Fixable downstream, but the spec exists for a reason.
  Harness action: −3 points per failed check.

- **low** — cosmetic only; no analysis or contract is affected.
  Harness action: logged as a warning; 0 points.


### CHK-01: Output is comma-delimited CSV
- **Claim:** The cleaned output file uses commas as delimiters and parses into all expected columns (not one lumped column).
- **Mechanical test:** `df = pd.read_csv(path)` (default comma sep) → `df.shape[1] >= 10`
- **Severity:** maximum
- **Origin:** Raw file is ';'-delimited; day-1 inspection showed single-column lump on naive load.

### CHK-02: Score within valid range
- **Claim:** Score is numeric and between 0 and 10 inclusive; anything outside that range is invalid.
- **Mechanical test:** `pd.to_numeric(df['Score'], errors='raise')` succeeds and `df['Score'].between(0, 10).all()`
- **Severity:** maximum
- **Origin:** Run of Aug 1: row 16 contained Score = 870 (mangled decimal, e.g. '8,7e-0' → digits concatenated).

### CHK-03: No missing titles
- **Claim:** Every row in the cleaned output has a non-empty title. (Rule side: a missing or
  corrupted title with a valid IMDB ID is recovered via the lookup tool; a fully empty row —
  no ID, no data — is dropped, not recovered.)
- **Mechanical test:** `df['Original_Title'].notna().all()` and `(df['Original_Title'].str.strip() != '').all()`
- **Severity:** high
- **Origin:** Corrected Aug 2: raw row 13 is a completely empty row (correctly dropped by the
  agent) — not a missing-title case. No ID-bearing rows lack titles in this dataset.

### CHK-04: Dates in ISO format
- **Claim:** All date values are in standard ISO format YYYY-MM-DD.
- **Mechanical test:** `df['Release_Date'].str.match(r'^\d{4}-\d{2}-\d{2}$').all()`
- **Severity:** medium
- **Origin:** Raw file mixes formats ('09 21 1972', '23 -07-2008', '22 Feb 04'); Aug 1 runs disagreed on year-only vs full date.

### CHK-05: Column names in snake_case
- **Claim:** All column names follow the `<column_name>` convention: lowercase-or-capitalized words joined by underscores, no spaces, no corrupted characters.
- **Mechanical test:** `all(re.fullmatch(r'[A-Za-z0-9_]+', c) for c in df.columns)`
- **Severity:** low
- **Origin:** Raw headers include 'Original titlÊ', 'Genrë¨', ' Votes ' (padding), 'Unnamed: 8'.

### CHK-06: Country names correct and unabbreviated
- **Claim:** No typos in country names, and no abbreviations — full names only (e.g. 'United States', not 'US'/'USA.').
- **Mechanical test:** `df['Country'].isin(CANONICAL_COUNTRIES).all()` — canonical list per
  Decisions: ISO 3166 short names (CSV in evals/), canonical form 'United States'.
- **Severity:** medium
- **Origin:** Aug 1 run left 'New Zesland' / 'New Zeland' unfixed; earlier run fixed them — behavior varies per run.

### CHK-07: No mojibake in text fields
- **Claim:** No title (or other text field) contains encoding-corruption signatures.
  Legitimate accented characters ('Léon') are correct and must NOT be flagged — the target
  is the mojibake pattern (UTF-8 read as latin-1), not non-English text.
- **Mechanical test:** `ftfy.badness.is_bad(title)` is False for every non-null title.
  (Was a regex for 'Ã|Â'; ftfy catches more mojibake patterns and the harness uses it.)
- **Severity:** high
- **Origin:** Aug 2: cleaned output contained 'LÃ©on', 'WALLÂ·E', "AmÃ©lie", 'piÃ¹' —
  mixed-encoding file; latin-1 fallback mangled legitimately-UTF-8 titles. Persisted through
  the best run to date.

### CHK-08: Row retention
- **Claim:** The cleaned output retains at least 100 of the raw 101 rows — only the one fully
  empty row is legitimately droppable. Prevents passing quality checks by deleting problem rows.
- **Mechanical test:** `len(df) >= 100`
- **Severity:** high
- **Origin:** Aug 2: runs varied between keeping 95 and 100 rows; audit showed only raw row 13
  (entirely NaN) merits dropping. General principle: every "no bad values" check needs a
  companion "and you kept the data" check.

### CHK-09: Dates are real dates, not just ISO-shaped
- **Claim:** Every non-null date value is a calendar date that actually exists. CHK-04 tests the
  *shape* of the string; this tests whether the date is real.
- **Mechanical test:** `pd.to_datetime(df['release_date'], format='%Y-%m-%d', errors='coerce')`
  produces no new NaT for values that were non-null before the parse.
- **Severity:** high
- **Origin:** 2026-08-08 run: 4 values passed CHK-04's regex while being impossible —
  `1972-21-09` and `1946-21-11` (month 21), `1984-02-34` (day 34), `1976-13-24` (month 13).
  Cause: the agent's parser read `09 21 1972` as DD-MM-YYYY when it is MM-DD-YYYY. General
  principle: a regex validates format, never meaning. Any check whose test is a pattern match
  needs a companion check that parses.

### CHK-10: Numeric magnitudes survive cleaning
- **Claim:** Cleaning a numeric field must not silently truncate its magnitude. A value that was
  hundreds of millions in the raw file must not become single digits in the output.
- **Mechanical test:** for each row, strip every non-digit from the raw income string
  (`"$ 4o8,035,783"` → 48035783) and compare, by IMDB id, to the cleaned value. Fail if the
  cleaned value is more than 10x smaller. Without the raw file the harness falls back to
  `income.min() >= 1000`.
- **Severity:** maximum
- **Origin:** 2026-08-08 run: raw `"$ 4o8,035,783"` (letter 'o' typed for zero) was cleaned with
  `re.match(r'^(\d+)', val)`, which matched `4` and stopped at the `o`. $408,035,783 became $4.
  Scored 0 penalty because no check covered `income` at all. General principle: every numeric
  column that gets a bespoke parser needs a magnitude check, because regex-based extraction fails
  by truncating silently rather than raising.

## Report-honesty checks
- Any statistical data analysis computations should be backed by clear, reproducible code and not just stated plainly: e.g., counts stated in the agent's report match recounts from the actual CSV.
  (Documented precedent: HR report invented "99.2% completeness"; IMDB BEFORE_AFTER doc
  contained transformations the cleaning code could not have produced.)

## Decisions
- **2026-08-01 — Enrichment is in scope, via engine tool.** The agent gets a second tool,
  `lookup_imdb_title(imdb_id)`, implemented in the engine (OMDb API, key in .env). Rule: when
  a row's title is missing, the agent must recover it by passing that row's IMDB ID to the tool.
  The model's code sandbox stays network-free — all lookups go through the engine.
  (CHK-03 then verifies the outcome: no missing titles in the final output.)
- **2026-08-01 — Country canonicalization.** Canonical list = ISO 3166 country names (CSV in
  evals/). Rule: fuzzy-match unambiguous typos to the list; flag ambiguous cases in the report
  rather than guess.
- Rule: when a row's title is missing OR corrupted (mojibake) and the row has a valid IMDB ID,
  the agent must recover the correct title by passing that ID to the tool.
- **2026-09-21 — Obvious typos in numbers are corrected, and reported.** A letter `o` between
  digits in a money field has one sensible reading. The agent corrects it to `0` and lists the
  raw value next to the corrected one in the report, so a reader can disagree. Anything less
  clear-cut stays null and is listed as unrecoverable. Same principle as the country rule.
- **2026-09-21 — Open: the fully empty row.** PRESERVING DATA says an empty row *may* be
  dropped; run 5 read that as *must keep*, kept it, and failed CHK-03 on its null title. Either
  the prompt should say "drop it" or CHK-03 should ignore all-null rows. Not yet decided.
- **2026-09-21 — Harness column names.** `evals/score.py` accepts the column names seen so far
  (`release_date` or `release_year`, `original_title` or `title`) and fails anything else. The
  stricter fix is to pin exact names in the output contract.

## Run log

### 2026-08-08 — first run with two tools registered
Command: `python agent/agent.py data/messy_IMDB_dataset.csv` · model `claude-haiku-4-5` · 15 turns (hit cap)

**Score: 86/100 — pass.**

| Check | Result | Evidence |
|---|---|---|
| CHK-01 | PASS | 11 columns, comma-delimited |
| CHK-02 | PASS | Score 7.4–9.3, 2 NaN (unparseable, coerced not invented) |
| CHK-03 | PASS | no empty titles |
| CHK-04 | FAIL −3 | `Release_year` = `1995.0`, `1972.0` — year only, and float dtype (NaN coercion) |
| CHK-05 | PASS | |
| CHK-06 | FAIL −3 | typos fixed (`New Zesland`→`New Zealand`, `Italy1`→`Italy`) but canonical form wrong: `USA`, `UK`; `West Germany` kept silently |
| CHK-07 | FAIL −8 | 4 rows: `LÃ©on`, `WALLÂ·E`, `Le fabuleux destin d'AmÃ©lie Poulain`, `Per qualche dollaro in piÃ¹` |
| CHK-08 | PASS | 100 of 101 rows retained |

**Report-honesty: PASS, but fragile.** Every checkable claim recounted correctly against the CSV
(13 missing values, 1 row removed, 13 countries, 59 genres, 64 directors, rating breakdown).
However those figures were written as hardcoded string literals in the report-generating code,
not computed from the DataFrame — correct for this run, silently wrong on any other. The current
check ("do stated counts match the data?") passes this. A stronger check would ask whether the
number was computed or typed.

**Engine-level observations (not check failures):**
- `lookup_imdb_title` was called **0 times** in 15 turns despite being registered with an explicit
  mojibake trigger in its description. The agent fixed mojibake in *column names* via a hardcoded
  rename map and never inspected the *data* for it. Root cause is likely the absent system prompt:
  nothing instructs the agent to go looking for corrupted titles, so the tool's "use it when you
  find one" description never activates. CHK-07 failure follows directly.
- Hit MAX_TURNS. Both output files were written at turn 11; turns 12–14 were "verify the files
  exist", "one final comparison", "display the full report" — padding after the work was done,
  ending with no final answer. Stopping problem, first live instance.
- Turns 6 and 9 crashed on `df` not surviving between `run_python` calls. The "each call runs in a
  FRESH process" line in the tool description helped the agent recover in one turn each time, but
  did not prevent the assumption. ~4 of 15 turns lost to this.

### 2026-08-08 — run 4: full system prompt, provenance rule, engine-side stop
Command: `python agent/agent.py data/messy_IMDB_dataset.csv` · model `claude-haiku-4-5` ·
stopped at turn 11 of 25 via engine file-existence check.

**Score: 97/100 — pass.** CHK-06 the only failure (−3).
CHK-01 ✓ · CHK-02 ✓ · CHK-03 ✓ · CHK-04 ✓ · CHK-05 ✓ · CHK-06 ✗ · CHK-07 ✓ · CHK-08 ✓

**What changed since run 3:** SYSTEM_PROMPT gained a full output contract, a numbered WORKING
METHOD with a save-early mandate, and a PROVENANCE section. MAX_TURNS 15 → 25. Engine-side stop
added (break when both output paths exist).

**All three interventions worked, and each is attributable:**
- *Save-early:* CSV written at turn 6, then read back at turns 7, 8, 10, 11. The re-paste-from-raw
  loop that killed runs 2 and 3 did not occur. This is what freed enough turns to finish.
- *Engine stop:* fired at turn 11, 14 turns under the cap. First run ever to terminate on purpose.
- *Provenance rule:* 3 unparseable release dates were left NULL and listed in the report as
  unrecoverable. Run 3, under the narrower failure-scoped wording, invented 5 dates from model
  memory in a hardcoded dict. The agent also volunteered a "Provenance Notes" section naming its
  two permitted sources. Widening the rule from "when a tool fails" to "origin regardless of
  outcome" is what closed it.
- *CHK-07:* first pass. 4 genuine OMDb calls, 0 mojibake remaining.

**The important finding: the score is flattering.** Three real defects scored zero.
1. Four impossible dates passed CHK-04 (see CHK-09, added).
2. `income` for tt0071562 went from `$ 4o8,035,783` to `4` — maximum-severity silent corruption,
   uncaught because no check covered income (see CHK-10, added).
3. Enrichment changed the *meaning* of `original_title`. OMDb's `Title` field returns the English
   release title, so `Léon` → `Léon: The Professional`, `Le fabuleux destin d'Amélie Poulain` →
   `Amélie`, `Per qualche dollaro in più` → `For a Few Dollars More`. Mojibake is gone and CHK-07
   passes; the column no longer holds original titles. OPEN DECISION: either the tool should
   request OMDb's original-title field, or the column contract should say it holds the English
   title. Not yet resolved, so no check written.

**CHK-06 regressed.** Run 1 produced `USA`; this run standardised `USA` → `US`, moving further
from the canonical `United States`. `evals/countries_iso3166.csv` now exists but nothing in the
prompt or tools tells the agent it is there.

**Score history (hand-scored):** run 1 = 86 · run 2 = no output (max turns) · run 3 = no output
(max turns) · run 4 = 97.

### 2026-09-21 — the harness re-scores every run
`evals/score.py` now runs all ten checks automatically. Re-scoring the saved outputs:

| Run | Hand score | Harness | Why they differ |
|---|---|---|---|
| 1 (Aug 1) | 86 | 70 | CHK-08 was passed by hand; the file has 95 of 101 rows. CHK-09 didn't exist. |
| 4 (Aug 8) | 97 | 0 | CHK-09 caught four impossible dates (-8). CHK-10 caught `$4` (maximum, run scores 0). |

Both gaps are the harness being stricter than I was. Hand-scoring skims; the script doesn't.

### 2026-09-21 — run 5: harness-driven fixes, engine nudge
Command: `python agent/agent.py data/messy_IMDB_dataset.csv` · model `claude-haiku-4-5` ·
stopped at turn 16 via engine file-existence check.

**Score: 92/100 — pass.** CHK-03 the only failure (-8).

| Check | Result | Evidence |
|---|---|---|
| CHK-01 | PASS | 11 columns |
| CHK-02 | PASS | min 7.4, max 9.3, 1 null |
| CHK-03 | FAIL -8 | 1 null title: the fully empty raw row was kept (see Decisions) |
| CHK-04 | PASS | |
| CHK-05 | PASS | |
| CHK-06 | PASS | first pass ever: `Korea, Republic of`, `Iran, Islamic Republic of` |
| CHK-07 | PASS | 4 OMDb lookups, no hand-written replace map |
| CHK-08 | PASS | 101 of 101 |
| CHK-09 | PASS | first pass ever; run 4's four impossible dates are now honest nulls |
| CHK-10 | PASS | `$ 4o8,035,783` → 408035783, reported with the raw value |

**What changed since run 4.** Three prompt rules (real calendar dates; magnitude check with
the typo rule; use the countries CSV) and one engine change: if nothing is saved by turn 6, the
engine appends one message telling the model to write the CSV on its next call. The first
attempt at run 5 had the prompt rules but not the nudge, and stalled exactly like runs 2 and 3:
16 turns of rebuilding from raw, nothing on disk. The nudge fired at turn 7 of the second
attempt and the CSV was saved one turn later.

**Costs of the honesty rules.** Five null dates versus run 4's three: the agent now refuses
`10-29-99` and `21-11-46` as ambiguous instead of guessing. Correct under provenance, and two
fewer data points.

**Still wrong, not yet checked.** The report hardcodes several counts as literals ("95 dates
parsed"), against the HONESTY rule. No check covers the report yet. And a null-count check is
missing: the first attempt at run 5 nulled South Korea and Iran instead of mapping them, and
CHK-06 passed because it ignores nulls. Every "no bad values" check needs a "kept the data"
partner; CHK-06 doesn't have one.

**Score history:** run 1 = 70 · run 4 = 0 · run 5 = 92 (all harness-scored).
