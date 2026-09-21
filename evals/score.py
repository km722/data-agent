"""Score a cleaned CSV against the checks in evals/checks_imdb.md.

    python evals/score.py <cleaned.csv> --raw <raw.csv>

Start at 100. A failed maximum check zeroes the run; high costs 8, medium 3,
low is a warning. Pass mark is 80. Each check returns (passed, evidence).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from ftfy.badness import is_bad

PASS_MARK = 80
PENALTY = {"maximum": None, "high": 8, "medium": 3, "low": 0}

# The agent has named the same column differently across runs (Release_Year vs
# release_date). Checks ask for a logical name; anything not listed here fails.
ALIASES = {
    "id": ["imdb_id", "imdb_title_id", "imbd_title_id"],
    "title": ["original_title", "title"],
    "date": ["release_date", "release_year"],
    "country": ["country"],
    "score": ["score"],
    "income": ["income"],
}


@dataclass
class Context:
    cleaned: pd.DataFrame
    raw: pd.DataFrame | None
    canonical_countries: set[str]

    def col(self, key: str) -> str | None:
        """Real column name in `cleaned` for a logical key, or None."""
        lower = {c.lower(): c for c in self.cleaned.columns}
        for candidate in ALIASES[key]:
            if candidate in lower:
                return lower[candidate]
        return None


def check_01_comma_delimited(ctx: Context) -> tuple[bool, str]:
    """Parses with the default comma separator into >= 10 columns."""
    n = ctx.cleaned.shape[1]
    return n >= 10, f"{n} columns parsed with comma delimiter"


def check_02_score_range(ctx: Context) -> tuple[bool, str]:
    """Score is numeric and every non-null value is within [0, 10]."""
    name = ctx.col("score")
    if name is None:
        return False, "no score column found"

    try:
        scores = pd.to_numeric(ctx.cleaned[name])
    except ValueError:
        return False, "score column is not numeric"

    present = scores.dropna()
    mask = present.between(0, 10)
    if not mask.all():
        return False, f"scores outside [0, 10]: {present[~mask].to_list()}"

    return True, f"min {scores.min()}, max {scores.max()}, {scores.isna().sum()} null"


def check_03_no_missing_titles(ctx: Context) -> tuple[bool, str]:
    """Every row has a non-empty title."""
    title = ctx.col("title")
    if title is None:
        return False, "no title column found"

    if ctx.cleaned[title].isna().any():
        return False, f"{ctx.cleaned[title].isna().sum()} null titles"

    stripped = ctx.cleaned[title].str.strip()
    if (stripped == "").any():
        return False, f"{(stripped == '').sum()} blank titles"

    return True, "no missing titles"


def check_04_iso_date_shape(ctx: Context) -> tuple[bool, str]:
    """Every non-null date matches YYYY-MM-DD."""
    date_col = ctx.col("date")
    if date_col is None:
        return False, "no date column found"

    dates = ctx.cleaned[date_col].dropna().astype(str)
    mask = dates.str.match(r"^\d{4}-\d{2}-\d{2}$")
    if not mask.all():
        bad = dates[~mask].to_list()
        return False, f"{len(bad)} dates not ISO-shaped, e.g. {bad[:5]}"

    return True, "all dates are YYYY-MM-DD"


def check_05_snake_case_columns(ctx: Context) -> tuple[bool, str]:
    """All column names are letters, digits and underscores only."""
    bad = [c for c in ctx.cleaned.columns if not re.fullmatch(r"[A-Za-z0-9_]+", c)]
    if bad:
        return False, f"column names not snake_case: {bad}"
    return True, "all column names are snake_case"


def check_06_canonical_countries(ctx: Context) -> tuple[bool, str]:
    """Every country value is in the ISO 3166 list (evals/countries_iso3166.csv)."""
    country_col = ctx.col("country")
    if country_col is None:
        return False, "no country column found"

    countries = ctx.cleaned[country_col].dropna()
    mask = countries.isin(ctx.canonical_countries)
    if not mask.all():
        return False, f"not in ISO list: {list(countries[~mask].unique())}"

    return True, "all country names are ISO canonical"


def check_07_no_mojibake(ctx: Context) -> tuple[bool, str]:
    """No title looks encoding-corrupted, judged by ftfy.badness.is_bad."""
    title = ctx.col("title")
    if title is None:
        return False, "no title column found"

    titles = ctx.cleaned[title].dropna()
    mask = titles.apply(is_bad)
    if mask.any():
        return False, f"mojibake in {mask.sum()} titles: {titles[mask].to_list()}"

    return True, "no mojibake in titles"


def check_08_row_retention(ctx: Context) -> tuple[bool, str]:
    """Cleaned file keeps all raw rows except the one fully empty row."""
    if ctx.raw is None:
        return True, "skipped: no --raw"

    kept, total = len(ctx.cleaned), len(ctx.raw)
    if kept >= total - 1:
        return True, f"{kept} of {total} rows retained"
    return False, f"{kept} of {total} rows retained"


def check_09_real_dates(ctx: Context) -> tuple[bool, str]:
    """Every ISO-shaped date is a real calendar date (CHK-04 only checks shape)."""
    date_col = ctx.col("date")
    if date_col is None:
        return False, "no date column found"

    dates = ctx.cleaned[date_col].dropna().astype(str)
    parsed = pd.to_datetime(dates, format="%Y-%m-%d", errors="coerce")
    mask = parsed.isna()
    if mask.any():
        bad = dates[mask].to_list()
        return False, f"{len(bad)} impossible dates, e.g. {bad[:5]}"

    return True, "all dates are real calendar dates"


def check_10_magnitude_survives(ctx: Context) -> tuple[bool, str]:
    """Cleaning must not shrink a number.

    Run 4 turned "$ 4o8,035,783" into 4 because a regex stopped at the letter o.
    With --raw: each cleaned income is compared, by IMDB id, to the digits in its
    raw string, and fails if it is more than 10x smaller. Without --raw: any income
    below 1000 fails (nothing in this dataset earned less).
    """
    income_col = ctx.col("income")
    if income_col is None:
        return False, "no income column found"

    try:
        income = pd.to_numeric(ctx.cleaned[income_col])
    except ValueError:
        return False, "income column is not numeric"

    if ctx.raw is None:
        low = income[income < 1000]
        if len(low):
            return False, f"income below 1000 (no --raw, proxy check): {low.to_list()}"
        return True, "no income below 1000 (no --raw, proxy check)"

    id_col = ctx.col("id")
    if id_col is None:
        return False, "no id column found, cannot align with raw rows"

    raw_income_col = next((c for c in ctx.raw.columns if "income" in c.lower()), None)
    if raw_income_col is None:
        return False, "no income column in raw file"

    # "$ 4o8,035,783" -> 48035783. Not the true value, but the right order of magnitude.
    raw_ids = ctx.raw.iloc[:, 0].astype(str).str.strip()
    raw_digits = ctx.raw[raw_income_col].astype(str).str.replace(r"\D", "", regex=True)
    raw_map = dict(zip(raw_ids, pd.to_numeric(raw_digits, errors="coerce")))

    cleaned_ids = ctx.cleaned[id_col].astype(str).str.strip()
    expected = cleaned_ids.map(raw_map)

    mask = income < expected / 10
    if mask.any():
        bad = [f"{i}: raw {int(e)} -> cleaned {v:g}"
               for i, e, v in zip(cleaned_ids[mask], expected[mask], income[mask])]
        return False, f"{mask.sum()} income values shrank 10x or more: {bad[:5]}"

    return True, f"income magnitudes match raw digits for {len(cleaned_ids)} rows"


CHECKS = [
    ("CHK-01", "maximum", check_01_comma_delimited),
    ("CHK-02", "maximum", check_02_score_range),
    ("CHK-03", "high",    check_03_no_missing_titles),
    ("CHK-04", "medium",  check_04_iso_date_shape),
    ("CHK-05", "low",     check_05_snake_case_columns),
    ("CHK-06", "medium",  check_06_canonical_countries),
    ("CHK-07", "high",    check_07_no_mojibake),
    ("CHK-08", "high",    check_08_row_retention),
    ("CHK-09", "high",    check_09_real_dates),
    ("CHK-10", "maximum", check_10_magnitude_survives),
]


def load_context(cleaned_path: Path, raw_path: Path | None) -> Context:
    cleaned = pd.read_csv(cleaned_path)  # default comma separator, CHK-01 relies on it

    raw = None
    if raw_path is not None:
        raw = pd.read_csv(raw_path, sep=None, engine="python", encoding="latin-1")

    countries_csv = Path(__file__).with_name("countries_iso3166.csv")
    canonical: set[str] = set()
    if countries_csv.exists():
        canonical = set(pd.read_csv(countries_csv).iloc[:, 0].astype(str).str.strip())

    return Context(cleaned=cleaned, raw=raw, canonical_countries=canonical)


def run_checks(ctx: Context) -> tuple[int, list[dict]]:
    score = 100
    zeroed = False
    rows = []
    for code, severity, fn in CHECKS:
        try:
            passed, evidence = fn(ctx)
        except Exception as e:
            passed, evidence = False, f"check crashed: {type(e).__name__}: {e}"

        deduction = 0
        if not passed:
            if PENALTY[severity] is None:
                zeroed = True
            else:
                deduction = PENALTY[severity]
                score -= deduction
        rows.append(dict(code=code, severity=severity, passed=passed,
                         deduction=deduction, evidence=evidence))

    if zeroed:
        score = 0
    return max(score, 0), rows


def print_table(score: int, rows: list[dict], cleaned_path: Path) -> None:
    print(f"\nScoring {cleaned_path}\n")
    print(f"{'Check':<8}{'Result':<8}{'Sev':<9}{'Pts':<6}Evidence")
    print("-" * 78)
    for r in rows:
        result = "PASS" if r["passed"] else "FAIL"
        if r["passed"]:
            pts = ""
        elif PENALTY[r["severity"]] is None:
            pts = "0/100"
        else:
            pts = f"-{r['deduction']}"
        print(f"{r['code']:<8}{result:<8}{r['severity']:<9}{pts:<6}{r['evidence']}")
    print("-" * 78)
    verdict = "PASS" if score >= PASS_MARK else "FAIL"
    print(f"Score: {score}/100  ->  {verdict} (pass mark {PASS_MARK})\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score a data-agent run against evals/checks_imdb.md")
    p.add_argument("cleaned", type=Path, help="cleaned CSV produced by the agent")
    p.add_argument("--raw", type=Path, default=None,
                   help="raw input CSV; enables CHK-08 and the stronger CHK-10")
    args = p.parse_args(argv)

    ctx = load_context(args.cleaned, args.raw)
    score, rows = run_checks(ctx)
    print_table(score, rows, args.cleaned)
    return 0 if score >= PASS_MARK else 1


if __name__ == "__main__":
    sys.exit(main())
