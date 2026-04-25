from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate

PROMPTS_DIR = Path(__file__).parent / "md"
SEPARATOR = "---HUMAN---"


def load_prompt(filename: str) -> ChatPromptTemplate:
    text = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
    parts = text.split(SEPARATOR, maxsplit=1)
    if len(parts) != 2:
        raise ValueError(
            f"Prompt file '{filename}' must contain exactly one '{SEPARATOR}' separator."
        )
    system, human = parts
    return ChatPromptTemplate.from_messages([
        ("system", system.strip()),
        ("human", human.strip()),
    ])
