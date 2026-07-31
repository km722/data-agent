
def run_code(code:str) -> str:
    import subprocess, sys

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
    
if __name__ == "__main__":
    print(run_code('print("hi")'))
    print(run_code('1/0'))
    print(run_code('x = 5'))
    print(run_code('import time; time.sleep(60)'))