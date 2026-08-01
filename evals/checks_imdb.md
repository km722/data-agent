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
- **Claim:** - **Claim:** Score is numeric and between 0 and 10 inclusive; anything outside that range is invalid.
- **Mechanical test:** `pd.to_numeric(df['Score'], errors='raise')` succeeds and `df['Score'].between(0, 10).all()`
- **Severity:**  maximum
- **Origin:** Run of Aug 1: row 16 contained Score = 870 (mangled decimal, e.g. '8,7e-0' → digits concatenated).

### CHK-03: No missing titles
- **Claim:** Every movie row has a non-empty title. (Rule side: if a title is missing in the raw data, the agent should recover it from the IMDB ID column.)
- **Mechanical test:** `df['Original_Title'].notna().all()` and `(df['Original_Title'].str.strip() != '').all()`
- **Severity:** high
- **Origin:** Raw data contains rows with missing titles; ID column (tt…) uniquely identifies the movie.

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
- **Claim:** IMDB ratings have a score range which is numeric and between 0 and 10 inclusive, anything below 0 or above 10. is invalid
- **Mechanical test:** `pd.to_numeric(df['Score'], errors='raise')` succeeds and `df['Score'].between(0, 10).all()`
- **Severity:**  maximum
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
- **Mechanical test:** `df['Country'].isin(CANONICAL_COUNTRIES).all()` — requires a canonical list: TODO(you) decide the list (and whether 'USA' or 'United States' is the canonical form).
- **Severity:** medium
- **Origin:** Aug 1 run left 'New Zesland' / 'New Zeland' unfixed; earlier run fixed them — behavior varies per run.

### CHK-07: No mojibake in text fields
- **Claim:** No title (or other text field) contains encoding-corruption signatures.
  Legitimate accented characters ('Léon') are correct and must NOT be flagged — the target
  is the mojibake pattern (UTF-8 read as latin-1), not non-English text.
- **Mechanical test:** `~df['Original_Title'].str.contains('Ã|Â', na=False)` → must be all True
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

