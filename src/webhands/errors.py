"""Errors the CLI and UI can explain without a traceback."""


class GoalError(Exception):
    """The goal could not be turned into a plan."""


class AgentError(Exception):
    """A run failed while the browser was working."""

    def __init__(self, message: str, steps: list | None = None) -> None:
        super().__init__(message)
        self.steps = list(steps or [])
