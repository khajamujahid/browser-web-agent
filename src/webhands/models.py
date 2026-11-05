"""Run records shared by the agent, CLI, and UI."""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Step:
    n: int
    op: str
    detail: str
    observation: str = ""
    ok: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunResult:
    goal: str
    mode: str
    planner: str
    export: str
    steps: list[Step] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "mode": self.mode,
            "planner": self.planner,
            "export": self.export,
            "steps": [step.to_dict() for step in self.steps],
            "columns": list(self.columns),
            "rows": list(self.rows),
        }

    def to_csv(self) -> str:
        from webhands.exporters import rows_to_csv

        return rows_to_csv(self.columns, self.rows)

    def to_json(self) -> str:
        from webhands.exporters import dumps

        return dumps(self.to_dict())

    def summary(self) -> str:
        return f"{len(self.rows)} rows · {self.mode} · {self.planner} planner · {len(self.steps)} steps"
