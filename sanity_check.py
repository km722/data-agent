
import anthropic
from dotenv import load_dotenv
import os

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def run_python() -> str:

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": "What is the capital of France?"}
            ],
        )

    return message.content[0].text


if __name__ == "__main__":
    print(run_python())