from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STEP_SCORES = [0, 1, 2, 3]
STEP_LABELS = ["0分", "一门得分", "二门得分", "三门得分"]
MAX_PILLARS = 4


def normalize_position(cycle: int, step: int) -> tuple[int, int]:
    if step >= 4:
        return min(cycle + 1, MAX_PILLARS), 0
    return min(cycle, MAX_PILLARS), max(0, step)


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
        return self.cycle

    def advance(self) -> str:
        if self.cycle >= MAX_PILLARS:
            return f"{self.number}号球已到上限"

        self.history.append((self.cycle, self.step))

        if self.step < 3:
            self.step += 1
            return f"{self.number}号球，{STEP_LABELS[self.step]}"

        self.cycle += 1
        self.step = 0
        return f"{self.number}号球，中柱得分"

    def undo(self) -> str:
        if not self.history:
            return f"{self.number}号球没有可撤销记录"

        old_cycle, old_step = self.cycle, self.step
        self.cycle, self.step = self.history.pop()
        label = STEP_LABELS[old_step] if old_step > 0 else "回到0分"
        if old_step == 0 and old_cycle > self.cycle:
            label = "中柱得分"
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
        cycle, step = normalize_position(
            int(data.get("cycle", 0)),
            int(data.get("step", 0)),
        )
        ball = cls(
            number=int(data["number"]),
            cycle=cycle,
            step=step,
        )
        ball.history = [
            normalize_position(int(item[0]), int(item[1]))
            for item in data.get("history", [])
        ]
        return ball


def new_balls() -> dict[int, BallState]:
    return {number: BallState(number) for number in range(1, 11)}


def team_for_ball(number: int) -> str:
    return "red" if number % 2 == 1 else "white"
