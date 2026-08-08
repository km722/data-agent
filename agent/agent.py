import anthropic
from anthropic.types import Message
from dotenv import load_dotenv
import os
import subprocess,sys
from pathlib import Path
import requests 
 

load_dotenv()

OUTPUT_DIR = 'outputs/'

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OMDb_API_KEY = os.getenv('OMDb_API_KEY')




#CONSTANTS
MODEL="claude-haiku-4-5"
MAX_TOKENS=10000
TOOLS=[
                {
                    "name": "run_python",  
                    "description": f"Python with pandas available, output must be printed to the console.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Python code to execute"}
                        },
                        "required": ["code"]
                    }
                }
            ]
MAX_TURNS = 15


#Tool 1: Execute python code
def run_code(code:str) -> str:

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

#Tool 2: Query IMDdb API by imdb id to retrieve missing movie title in messy_IMDB_dataset
def lookup_imdb_title(imdb_id: str) -> str:
    base_url = f"http://www.omdbapi.com/"

    params = {
        "apikey":OMDb_API_KEY,
        "i":imdb_id
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Only catches network/server errors (e.g., 404, 500)
    
        movie_data = response.json()

  # TRAP FIX: Catch OMDb's internal error response
        if movie_data.get("Response") == "False":
            error_msg = movie_data.get("Error", "Unknown OMDb error")
            print(f"OMDb Error: {error_msg}")
        # Return your custom fallback string here
            movie_title = "Movie Not Found" 
        else:
            movie_title = movie_data.get("Title")
            print(f"Success! Title: {movie_title}")

    except requests.exceptions.RequestException as e:
    # This only triggers if the website is down or the URL is broken
        print(f"Network/HTTP Error occurred: {e}")









def call_model(messages:list) -> Message:

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model = MODEL,
        max_tokens = MAX_TOKENS,
        messages = messages,
        tools = TOOLS
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
    report_path  = output_dir / f"results_{stem}.md"


    
    prompt = f"""Inspect and clean the {csv_file_path} file using the pandas library.
             Once you have fully finished cleaning the dataset: 
             1. Save cleaned dataset as csv into exaclty this path - {cleaned_path},
             2. Save the results into exactly this path {report_path} """

    messages = [{"role": "user", "content": prompt}]

    for turn in range(MAX_TURNS):
        response = call_model(messages)
        print(f"[turn {turn}] stop_reason: {response.stop_reason}")
        print(f'--response--\n{response.content}')
        

        for block in response.content:                 
            if block.type == "text":
                print(block.text)

        if response.stop_reason != "tool_use":         
            break                                      

        for block in response.content:                 
            if block.type == "tool_use":
                block_id = block.id
                code = block.input["code"]

        print(f"--- running code (turn {turn}) ---")   
        output = run_code(code)

        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": block_id,
                "content": output,
            }],
        })
    else:
        print(f"Agent did not finish and reach Max Turns:{MAX_TURNS}")

      

