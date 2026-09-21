import os
import subprocess
import sys
from pathlib import Path

import anthropic
import requests
from anthropic.types import Message, MessageParam, ToolParam
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OMDb_API_KEY = os.getenv("OMDb_API_KEY")

SYSTEM_PROMPT = """You are an autonomous data-cleaning agent. You are given a messy CSV file. You
inspect it, clean it, and write out a cleaned CSV plus a markdown report of what you did.

OUTPUT CONTRACT
- The cleaned file is a standard comma-delimited CSV.
- Column names are snake_case: words joined by underscores, no spaces, no corrupted characters.
- Dates are full ISO format, YYYY-MM-DD. Reducing a date to its year alone is NOT acceptable. If a
  source value genuinely carries no day or month, leave it null rather than inventing one or
  silently degrading the format.
- A date must be a real calendar date. After parsing, verify the month is 1-12 and the day exists
  in that month. If a raw value cannot be read as a real date, leave it null and list it in the
  report.
- Numeric fields have numeric dtypes, and any field with a known valid range is validated against
  that range.
- When parsing a number, compare the result to the digits in the raw string. If the parsed value
  is more than 10x smaller, the parse failed: do not write it. If the error is an obvious typo
  (e.g. '8o8' for '808'), correct it and put the raw value next to the corrected one in the
  report. Otherwise leave it null and list it in the report.
- Categorical values are canonical: no abbreviations, no typos, no near-duplicate spellings of the
  same value.
- The canonical country list is in evals/countries_iso3166.csv. Read it and map every country to
  a name in that file. Flag any you cannot map.

WORKING METHOD — FOLLOW THIS ORDER
1. Inspect the raw file first: encoding, delimiter, header row, shape. Assume none of them.
2. Do ONE complete cleaning pass over every column, then WRITE THE CLEANED CSV TO ITS FINAL PATH.
   Do this even if the pass is imperfect. A saved imperfect file is worth far more than a perfect
   one you never reached. Aim to be saved within your first 6 tool calls.
3. After that, read the SAVED CSV back, improve one thing, save again. Never rebuild the pipeline
   from the raw file once step 2 is done — every run_python call is a fresh process, so re-deriving
   everything from raw each turn costs you the whole run.
4. Write the report last, once the CSV is final.
- Throughout: go looking for problems rather than waiting to trip over them. In particular, scan
  text columns for encoding corruption — the mojibake signature where 'Ã' or 'Â' appears mid-word
  ('LÃ©on', 'WALLÂ·E'). Legitimate accented characters ('Léon', 'Amélie') are correct, leave them.

PRESERVING DATA
- Do not drop rows to make the data look clean. Only a row that is entirely empty may be dropped.
- If a value can be recovered through a tool, recover it. Do not delete the row instead.
- Report every row you drop, with the reason.

PROVENANCE — THE RULE THAT MATTERS MOST
- Every value in the cleaned output originates from exactly one of two places: the source CSV, or
  a tool result. There is no third source.
- If a value cannot be obtained from either, leave it null and list it in the report as
  unrecoverable. NEVER fill a gap from your own knowledge, even when you are certain you know the
  answer. You cannot verify it and neither can the reader. A plausible invented value is worse than
  an honest null, because nobody knows to go and fix it.
- This holds whether or not a tool call failed. A tool that succeeds but returns something other
  than the field you needed has still not given you that value.
- Never write a hardcoded lookup table of values — dates, names, categories — from memory.

HONESTY
- Every number in your report must be computed from the DataFrame at the moment the report is
  written. Never type a count, percentage or range as a literal string.
- Report every tool call that failed, and every value left unrecoverable.
- Where a correction is ambiguous, flag it in the report rather than guessing.

WHEN YOU ARE DONE
You are done once both requested output files exist at their exact paths and you have verified
their contents once. Then stop and give a short summary. Do not run further verification passes,
do not re-print the dataset, and do not produce extra comparison output."""

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 10000
MAX_TURNS = 25

TOOLS: list[ToolParam] = [
    {
        "name": "run_python",
        "description": (
            "Execute Python code. pandas is available. Anything you want to see must be "
            "printed with print() — return values are not captured. "
            "IMPORTANT: each call runs in a FRESH process. No variables, imports, or "
            "DataFrames survive between calls, so every call must be self-contained "
            "(re-read the CSV each time). No network access from this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"}
            },
            "required": ["code"],
        },
    },
    {
        "name": "lookup_imdb_title",
        "description": (
            "Look up a movie's canonical title from its IMDB ID via the OMDb API. "
            "Use this ONLY when a row's title cannot be trusted: it is missing/empty, or it "
            "contains mojibake — the encoding-corruption signature where 'Ã' or 'Â' appears "
            "mid-word (e.g. 'LÃ©on', 'WALLÂ·E', 'AmÃ©lie'). "
            "Do NOT use it for titles that merely have leading/trailing whitespace, odd casing, "
            "or legitimate accented characters — 'Léon' and 'Amélie' are already correct. "
            "Fix those with pandas instead. "
            "Each call is a network request against a limited daily quota, so call it only for "
            "rows that genuinely need it. "
            "Returns the title string, or a message beginning 'Movie Not Found' / "
            "'Error occurred' if the lookup fails."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "imdb_id": {
                    "type": "string",
                    "description": "IMDB id of the movie to lookup",
                }
            },
            "required": ["imdb_id"],
        },
    },
]


# Tool 1: run the model's code in a fresh subprocess. Nothing survives between calls,
# and a crash comes back as text so the model can read it and try again.
def run_code(code: str) -> str:
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )

    except subprocess.TimeoutExpired:
        return "Code timed out after 30 seconds. Avoid infinite loops and very slow operations."

    if result.stdout and result.stderr:
        return f"{result.stdout}\n--- ERROR ---\n{result.stderr}"
    elif result.stdout:
        return result.stdout
    elif result.stderr:
        return f"--- ERROR ---\n{result.stderr}"
    else:
        return "Code ran successfully but printed nothing. Use print() to display any values you want to see."


# Tool 2: recover a movie title from its IMDB id via OMDb. This runs in the engine,
# not in the model's code, so the sandbox stays network-free.
def lookup_imdb_title(imdb_id: str) -> str:
    base_url = "https://www.omdbapi.com/"

    params = {"apikey": OMDb_API_KEY, "i": imdb_id}

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()

        movie_data = response.json()

        # OMDb reports its own errors inside a 200 response, so check the body too.
        if movie_data.get("Response") == "False":
            error_msg = movie_data.get("Error", "Unknown OMDb error")
            print(f"OMDb Error: {error_msg}")
            return f"Movie Not Found: {error_msg}"
        else:
            movie_title = movie_data.get("Title")
            if not movie_title:
                print("OMDb returned no title for this IMDB ID.")
                return "Movie Not Found: No title returned"

            print(f"Success! Title: {movie_title}")
            return movie_title

    except requests.exceptions.RequestException as e:
        print(f"Network/HTTP Error occurred: {e}")
        return "Error occurred while fetching movie title"


def call_model(messages: list) -> Message:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=5)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
        tools=TOOLS,
    )

    return response


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        csv_file_path = sys.argv[1]
        if not Path(csv_file_path).exists():
            print(f"File not found: {csv_file_path}")
            print("Check the path — e.g. data/messy_IMDB_dataset.csv")
            sys.exit(1)
    else:
        print("usage: python agent/agent.py <csv_path> [output_dir]")
        print("Required arg missing; please pass a csv file name as argument")
        sys.exit(1)

    if len(sys.argv) < 3:
        print("No output dir provided; defaulting to project outputs/")
        output_dir = Path(__file__).resolve().parent.parent / "outputs"
    else:
        output_dir = Path(sys.argv[2])

    output_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(csv_file_path).stem
    cleaned_path = output_dir / f"cleaned_{stem}.csv"
    report_path = output_dir / f"results_{stem}.md"

    # Clear leftovers from earlier runs, otherwise the stop check below fires immediately.
    cleaned_path.unlink(missing_ok=True)
    report_path.unlink(missing_ok=True)

    prompt = f"""Inspect and clean the {csv_file_path} file using the pandas library.
             Once you have fully finished cleaning the dataset:
             1. Save the cleaned dataset as csv to exactly this path: {cleaned_path}
             2. Save the report to exactly this path: {report_path}"""

    message: list[MessageParam] = [{"role": "user", "content": prompt}]
    nudged = False

    for turn in range(MAX_TURNS):
        response = call_model(message)
        print(f"[turn {turn}] stop_reason: {response.stop_reason}")
        print(f"--response--\n{response.content}")

        turn_results = []

        for block in response.content:
            if block.type == "text":
                print(block.text)

        if response.stop_reason != "tool_use":
            break

        for block in response.content:
            if block.type == "tool_use":
                block_id = block.id
                name = block.name

                if name == "lookup_imdb_title":
                    print(f"Tool use detected: {name}")
                    imdb_id = str(block.input["imdb_id"])
                    result = lookup_imdb_title(imdb_id)
                    print(f"--- result ({name}) ---\n{result[:500]}")

                elif name == "run_python":
                    print(f"Tool use detected: {name} ")
                    code = str(block.input["code"])
                    print(f"--- running code (turn {turn}) ---")
                    result = run_code(code)
                    print(f"--- result ({name}) ---\n{result[:500]}")

                else:
                    print(f"Unknown tool: {name}")
                    result = f"Unknown tool: {name}"
                    print(f"--- result ({name}) ---\n{result[:500]}")

                turn_results.append(
                    {"type": "tool_result", "tool_use_id": block_id, "content": result}
                )

        message.append({"role": "assistant", "content": response.content})

        # Runs 2, 3 and 5 stalled here: the model kept rebuilding from raw instead of
        # saving, and ran out of turns. One reminder, sent once, fixed it.
        if turn >= 6 and not cleaned_path.exists() and not nudged:
            turn_results.append({
                "type": "text",
                "text": f"You are {turn + 1} tool calls in and nothing is saved. Your next "
                        f"run_python call must write the cleaned CSV to {cleaned_path}, "
                        "even if it is imperfect. Improve it after it is on disk.",
            })
            nudged = True
        message.append({"role": "user", "content": turn_results})

        # Engine-side stop: the job is done when both files exist. The CSV is saved early
        # on purpose, so the report is the real done signal.
        if cleaned_path.exists() and report_path.exists():
            print(f"[turn {turn}] both output files exist — stopping.")
            break

    else:
        print(f"Agent did not finish and reach Max Turns:{MAX_TURNS}")
