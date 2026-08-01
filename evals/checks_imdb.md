# Correctness Checks — messy_IMDB_dataset.csv

## Context
Raw file is semicolon-delimited with latin-1 encoding and corrupted header characters;
naive `read_csv` lumps all columns into one. ~101 rows of top-rated movies.
A successfully cleaned version is: TODO(you) — one sentence.


### Severity levels
- **maximum** — <corrupts data silently / poisons any analysis built on it>.
  Harness action: run counts as FAILED outright.
- **high** — <meaningful damage or loss, but visible/detectable downstream>.
  Harness action: <?>
- **medium** — <correctness intact, contract violated — wrong format/type/naming>.
  Harness action: <?>
- **low** — <cosmetic; no analysis would change>.
  Harness action: <warn only, never fails a run>.


### CHK-01: Output is comma-delimited CSV
- **Claim:** The cleaned output file uses commas as delimiters and parses into all expected columns (not one lumped column).
- **Mechanical test:** `df = pd.read_csv(path)` (default comma sep) → `df.shape[1] >= 10`
- **Severity:** maximum
- **Origin:** Raw file is ';'-delimited; day-1 inspection showed single-column lump on naive load.

### CHK-02: Score within valid range
- **Claim:** IMDB ratings have a score range which is numeric and between 0 and 10 inclusive, anything below 0 or above 10. is invalid
- **Mechanical test:** `pd.to_numeric(df['Score'], errors='raise')` succeeds and `df['Score'].between(0, 10).all()`
- **Severity:**  high
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
- **Mechanical test:** `df['Country'].isin(CANONICAL_COUNTRIES).all()` — requires a canonical list: TODO(you) decide the list (and whether 'USA' or 'United States' is the canonical form).
- **Severity:** medium
- **Origin:** Aug 1 run left 'New Zesland' / 'New Zeland' unfixed; earlier run fixed them — behavior varies per run.

## Report-honesty checks
- Any statistical data analysis computations should be bacjked by clear, reproducible code and not just stated plainly: e.g., counts stated in the agent's report match recounts from the actual CSV.
  (Documented precedent: HR report invented "99.2% completeness"; IMDB BEFORE_AFTER doc
  contained transformations the cleaning code could not have produced.)


## Open questions
- CHK-03's rule half implies *enrichment* (looking up titles by IMDB ID) — is external
  lookup in scope for the agent, and from where? TODO(you)
- Year-only vs full ISO date: CHK-04 currently demands full dates — confirm that's the ruling. TODO(you)
- Rows dropped vs kept-with-NaN: Aug 1 runs kept 100 vs 95 of 101 — what's the floor? TODO(you)