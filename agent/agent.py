import anthropic
from anthropic.types import Message
from dotenv import load_dotenv
import os
import subprocess,sys

load_dotenv()

OUTPUT_DIR = 'outputs/'

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
csv_file = "data/messy_HR_data.csv"
prompt = f"""Inspect and clean the {csv_file} file using the pandas library.
             Once you have fully finished cleaning the dataset, 1. save cleaned dataset as csv into the {OUTPUT_DIR} with the name 'cleaned_messy_HR_data.csv',
             and 2. Save the results text as an md file into {OUTPUT_DIR} as 'results.md' """



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

      


