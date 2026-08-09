from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STEP_SCORES = [0, 1, 2, 3, 5]
STEP_LABELS = ["0分", "一门得分", "二门得分", "三门得分", "中柱得分"]
MAX_PILLARS = 4


@dataclass
class BallState:
    number: int
    cycle: int = 0
    step: int = 0
    history: list[tuple[int, int]] = field(default_factory=list)

    @property
    def score(self) -> int:
        return self.cycle * 5 + STEP_SCORES[self.step]

    @property
    def pillar_count(self) -> int:
        return self.cycle + (1 if self.step == 4 else 0)

    def advance(self) -> str:
        if self.cycle >= MAX_PILLARS and self.step == 4:
            return f"{self.number}号球已到上限"

        self.history.append((self.cycle, self.step))

        if self.step < 4:
            self.step += 1
            return f"{self.number}号球，{STEP_LABELS[self.step]}"

        self.cycle = min(self.cycle + 1, MAX_PILLARS)
        self.step = 0
        return f"{self.number}号球，回到0分"

    def undo(self) -> str:
        if not self.history:
            return f"{self.number}号球没有可撤销记录"

        old_cycle, old_step = self.cycle, self.step
        self.cycle, self.step = self.history.pop()
        label = STEP_LABELS[old_step] if old_step > 0 else "回到0分"
        if old_step == 0 and old_cycle > self.cycle:
            label = "中柱后回到0分"
        return f"撤销，{self.number}号球，{label}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "cycle": self.cycle,
            "step": self.step,
            "score": self.score,
            "pillarCount": min(self.pillar_count, MAX_PILLARS),
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BallState":
        ball = cls(
            number=int(data["number"]),
            cycle=int(data.get("cycle", 0)),
            step=int(data.get("step", 0)),
        )
        ball.history = [tuple(item) for item in data.get("history", [])]
        return ball


def new_balls() -> dict[int, BallState]:
    return {number: BallState(number) for number in range(1, 11)}


def team_for_ball(number: int) -> str:
    return "red" if number % 2 == 1 else "white"

