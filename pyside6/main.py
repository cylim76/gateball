from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import (
        QApplication,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QInputDialog,
        QMainWindow,
        QMessageBox,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError:
    print("PySide6 is not installed. Run: python -m pip install -r pyside6/requirements.txt")
    raise

from common.gateball_rules import BallState, new_balls, team_for_ball


class GateballWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("门球计分 PySide6 原型")
        self.balls: dict[int, BallState] = new_balls()
        self.selected_ball = 1
        self.running = False
        self.time_expired = False
        self.allow_scoring_when_paused = False
        self.duration = 30 * 60
        self.remaining = self.duration
        self.finish_password = "1234"

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)

        self.build_ui()
        self.render()

    def build_ui(self) -> None:
        root = QWidget()
        root.setStyleSheet(
            """
            QWidget { background: #050505; color: white; font-family: Microsoft YaHei; }
            QLabel#title { color: #ffd43b; font-size: 44px; font-weight: 900; }
            QLabel#redTotal { color: #ff111a; font-size: 86px; font-weight: 900; }
            QLabel#whiteTotal { color: #f2f2f2; font-size: 86px; font-weight: 900; }
            QLabel#time { color: #ffd43b; font-size: 72px; font-weight: 900; }
            QLabel#message { color: #eeeeee; font-size: 24px; }
            QLabel.team { font-size: 42px; font-weight: 900; }
            QTableWidget { gridline-color: #777; font-size: 28px; }
            QHeaderView::section { background: #202020; color: white; font-size: 22px; font-weight: 900; }
            """
        )
        layout = QVBoxLayout(root)

        title = QLabel("★ 红星村老年会门球比赛 ★")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        top = QHBoxLayout()
        red_name = QLabel("红队")
        red_name.setProperty("class", "team")
        white_name = QLabel("白队")
        white_name.setProperty("class", "team")
        self.red_total = QLabel("0")
        self.red_total.setObjectName("redTotal")
        self.red_total.setAlignment(Qt.AlignCenter)
        self.time_label = QLabel("30:00")
        self.time_label.setObjectName("time")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.white_total = QLabel("0")
        self.white_total.setObjectName("whiteTotal")
        self.white_total.setAlignment(Qt.AlignCenter)
        top.addWidget(red_name, 1)
        top.addWidget(self.red_total, 1)
        top.addWidget(self.time_label, 2)
        top.addWidget(self.white_total, 1)
        top.addWidget(white_name, 1)
        layout.addLayout(top)

        tables = QGridLayout()
        self.red_table = self.make_table()
        self.white_table = self.make_table()
        tables.addWidget(self.red_table, 0, 0)
        tables.addWidget(self.white_table, 0, 1)
        layout.addLayout(tables)

        self.message = QLabel("等待开始")
        self.message.setObjectName("message")
        layout.addWidget(self.message)
        self.setCentralWidget(root)

    def make_table(self) -> QTableWidget:
        table = QTableWidget(5, 7)
        table.setHorizontalHeaderLabels(["球号", "0分", "1分", "2分", "3分", "中柱", "分数"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.horizontalHeader().setStretchLastSection(True)
        for row in range(5):
            table.setRowHeight(row, 82)
        return table

    def render_table(self, table: QTableWidget, numbers: list[int]) -> None:
        for row, number in enumerate(numbers):
            ball = self.balls[number]
            values = [str(number)]
            values.extend("●" if ball.step == step else "○" for step in range(4))
            values.append(self.pillar_text(ball.pillar_count))
            values.append(str(ball.score))
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                if number == self.selected_ball:
                    item.setBackground(Qt.darkYellow)
                table.setItem(row, col, item)

    def pillar_text(self, count: int) -> str:
        if count <= 0:
            return ""
        if count == 1:
            return "●"
        if count == 2:
            return "●●"
        return f"● x{count}"

    def render(self) -> None:
        red_total = sum(ball.score for ball in self.balls.values() if team_for_ball(ball.number) == "red")
        white_total = sum(ball.score for ball in self.balls.values() if team_for_ball(ball.number) == "white")
        self.red_total.setText(str(red_total))
        self.white_total.setText(str(white_total))
        self.time_label.setText(f"{self.remaining // 60:02d}:{self.remaining % 60:02d}")
        self.render_table(self.red_table, [1, 3, 5, 7, 9])
        self.render_table(self.white_table, [2, 4, 6, 8, 10])

    def announce(self, text: str) -> None:
        QApplication.beep()
        self.message.setText(text)

    def tick(self) -> None:
        if self.remaining > 0:
            self.remaining -= 1
        if self.remaining == 0:
            self.running = False
            self.time_expired = True
            self.timer.stop()
            self.announce("叮，时间到")
        self.render()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        text = event.text()
        if text in "123456789":
            self.selected_ball = int(text)
            self.announce(f"{self.selected_ball}号球")
        elif text == "0":
            self.selected_ball = 10
            self.announce("10号球")
        elif text == "+":
            if not self.running and not self.allow_scoring_when_paused and not self.time_expired:
                self.announce("暂停期间不能计分")
            else:
                self.announce(self.balls[self.selected_ball].advance())
        elif text == "-":
            self.announce(self.balls[self.selected_ball].undo())
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self.running = not self.running
            if self.running:
                self.timer.start()
                self.announce("比赛开始")
            else:
                self.timer.stop()
                self.announce("比赛暂停")
        elif text == "*":
            password, ok = QInputDialog.getText(self, "结束比赛", "输入四位密码")
            if ok and password == self.finish_password:
                self.balls = new_balls()
                self.selected_ball = 1
                self.remaining = self.duration
                self.running = False
                self.time_expired = False
                self.timer.stop()
                self.announce("进入下一场，等待开始")
            elif ok:
                QMessageBox.warning(self, "结束比赛", "密码错误")
        self.render()


def main() -> None:
    app = QApplication(sys.argv)
    window = GateballWindow()
    window.resize(1400, 850)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
