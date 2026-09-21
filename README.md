# data-agent

An autonomous data-cleaning agent, written from scratch with no agent frameworks. You point it at a messy CSV. It inspects the file, writes and runs its own pandas code, fixes its own mistakes, and saves a cleaned CSV plus a report of what it did.

The whole engine is one file, `agent/agent.py`, about 300 lines. It calls the Anthropic API directly. No LangChain, no CrewAI. The model picks a tool, my code runs it, the result goes back to the model, repeat until done.

## Tools

- `run_python`: runs the model's pandas code in a subprocess with a 30 second timeout. Every call is a fresh process. If the code crashes, the error goes back to the model so it can fix it.
- `lookup_imdb_title`: recovers corrupted movie titles from their IMDB IDs using the OMDb API. This runs in the engine, not in the model's code, so the model's code never touches the network.

A run stops when the model says it's done, or when the engine sees that both output files exist. Hard cap of 25 turns.

## Rules

The system prompt enforces a few rules:

- Every value in the output has to come from the source CSV or a tool result. Never from the model's memory. If a value can't be recovered it stays null and gets listed in the report. An earlier version made up 5 release dates from memory. This rule is what stopped that.
- Every number in the report has to be computed from the data at write time, not typed in.
- Only fully empty rows can be dropped, and every drop is reported.
- Clean everything once, save, then improve the saved file. Never start over from the raw file.
- A date has to be a real calendar date, not just date-shaped. A number can't shrink by 10x during parsing. An obvious typo (`4o8` for `408`) gets corrected and reported with the raw value beside it.

One engine rule as well: if nothing is saved by turn 6, the engine sends the model a single message telling it to write the CSV on its next call. Three runs died before this existed, all the same way: the model rebuilt its pipeline from the raw file every turn and ran out of turns with nothing on disk.

## Scoring

`evals/checks_imdb.md` has 10 checks on the messy IMDB set. Each one has a claim, a test, a severity level, and a note on which run caused it. 100 points, pass at 80. A failed maximum-severity check scores the run 0 outright.

`evals/score.py` runs them:

```
python evals/score.py examples/imdb/cleaned_messy_IMDB_dataset.csv --raw data/messy_IMDB_dataset.csv
```

```
Check   Result  Sev      Pts   Evidence
------------------------------------------------------------------------------
CHK-01  PASS    maximum        11 columns parsed with comma delimiter
CHK-02  PASS    maximum        min 7.4, max 9.3, 1 null
CHK-03  FAIL    high     -8    1 null titles
CHK-04  PASS    medium         all dates are YYYY-MM-DD
CHK-05  PASS    low            all column names are snake_case
CHK-06  PASS    medium         all country names are ISO canonical
CHK-07  PASS    high           no mojibake in titles
CHK-08  PASS    high           101 of 101 rows retained
CHK-09  PASS    high           all dates are real calendar dates
CHK-10  PASS    maximum        income magnitudes match raw digits for 101 rows
------------------------------------------------------------------------------
Score: 92/100  ->  PASS (pass mark 80)
```

That's run 5, the one in `examples/imdb/`. The one failure is the fully empty row in the raw file: the prompt says it *may* be dropped, the model read that as *must keep*, and its null title fails CHK-03. The prompt and the check disagree about one row. Undecided which one is right.

## What the harness found

Until this month I scored runs by hand. Run 4 got a 97. When I wrote the script and ran it on the same file, run 4 scored 0.

Two things I'd missed. Four dates like `1972-21-09` had passed the format check, because a regex checks shape, not meaning; that's CHK-09. And `$ 4o8,035,783` (someone typed a letter o for a zero) had been cleaned down to `$4`, and no check covered income at all; that's CHK-10, maximum severity. The run-1 file I'd passed on row retention turned out to have 95 of 101 rows.

Hand-scoring skims. The script doesn't. The fixes that took run 5 from 0 to 92 were all things the harness pointed at.

## Status

Works: the loop, both tools, the scoring harness, one dataset cleaned end to end and scored (IMDB).

Known gaps, in order of how much they matter:

- No check on the report. The HONESTY rule says every number must be computed, and run 5's report still typed some in. The harness only reads the CSV.
- No null-count check. A run that nulls a value instead of fixing it passes every "no bad values" check, because they all skip nulls. One attempt at run 5 nulled South Korea and Iran and CHK-06 passed.
- Column names drift between runs (`release_date` vs `release_year`). The harness tolerates the names it has seen; the real fix is to pin them in the prompt.
- Sandbox is a subprocess with a timeout, not real isolation.
- One dataset. The others in `data/` haven't been run or scored.

## Run it

```
pip install -r requirements.txt
python agent/agent.py path/to/messy.csv [output_dir]
python evals/score.py outputs/cleaned_messy.csv --raw path/to/messy.csv
```

Put `ANTHROPIC_API_KEY` and `OMDb_API_KEY` in a `.env` file. The datasets aren't committed, bring your own messy CSV.
