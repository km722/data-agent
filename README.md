# data-agent

An autonomous data-cleaning agent, written from scratch with no agent frameworks. You point it at a messy CSV. It inspects the file, writes and runs its own pandas code, fixes its own mistakes, and saves a cleaned CSV plus a report of what it did.

The whole engine is one file, `agent/agent.py`, about 270 lines. It calls the Anthropic API directly. No LangChain, no CrewAI. The model picks a tool, my code runs it, the result goes back to the model, repeat until done.

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

## Scoring

`evals/checks_imdb.md` has 10 checks. Each one has a claim, a test, a severity level, and a note on which run caused it. 100 points, pass at 80.

Scores on the messy IMDB set: 86, then two runs that never finished, then 97. Each gain is tied to a specific change (save early, engine-side stop, the provenance rule).

The interesting part: the 97 was too generous. Real bugs scored zero. Dates like 1972-21-09 passed the format check, because a regex checks shape, not meaning. And "$ 4o8,035,783" (someone typed a letter o instead of a zero) got cleaned down to $4. Both are now checks CHK-09 and CHK-10.

## Status

Works now: the loop, both tools, two datasets cleaned end to end (HR and IMDB), the scoring rubric.

Not built yet: an automated eval harness (I score runs by hand right now), real sandbox isolation for the executor, a comparison against pasting the CSV into ChatGPT, a run on InfiAgent-DABench, and packaging as a CLI.

## Run it

```
pip install -r requirements.txt
python agent/agent.py path/to/messy.csv [output_dir]
```

Put `ANTHROPIC_API_KEY` and `OMDb_API_KEY` in a `.env` file. The datasets aren't committed, bring your own messy CSV.
