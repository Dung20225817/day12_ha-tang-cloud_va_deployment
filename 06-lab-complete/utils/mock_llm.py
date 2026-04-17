"""Mock LLM used for deployment and reliability exercises."""
import random
import time

MOCK_RESPONSES = {
    "docker": [
        "Docker packages the app and its dependencies into a consistent runtime.",
    ],
    "deploy": [
        "Deployment moves your tested app to an environment users can access.",
    ],
    "default": [
        "Mock response from the AI agent. Replace with real LLM API in production.",
        "The agent is running correctly in this lab environment.",
        "Your request was processed by the mock LLM.",
    ],
}


def ask(question: str, delay: float = 0.06) -> str:
    """Return deterministic-style mock output with small latency."""
    time.sleep(delay)
    lowered = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword != "default" and keyword in lowered:
            return random.choice(responses)
    return random.choice(MOCK_RESPONSES["default"])
