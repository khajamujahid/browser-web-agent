"""WebHands: a small autonomous browser agent."""

__version__ = "0.1.0"


def __getattr__(name: str):
    if name == "Agent":
        from webhands.agent import Agent

        return Agent
    if name == "RunResult":
        from webhands.models import RunResult

        return RunResult
    if name == "Step":
        from webhands.models import Step

        return Step
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["Agent", "RunResult", "Step", "__version__"]
