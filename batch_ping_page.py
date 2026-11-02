from subprocess import run
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QTextEdit, QPushButton


class BatchPingPage(QWidget):
    """批量 Ping 页。"""

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.host_input = QTextEdit()
        self.host_input.setPlaceholderText("每行一个 IP / 域名\n例如：\n8.8.8.8\nwww.baidu.com")
        layout.addWidget(self.host_input)

        self.run_btn = QPushButton("开始 Ping")
        self.run_btn.clicked.connect(self._run_ping)
        layout.addWidget(self.run_btn)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    def _run_ping(self):
        hosts = [line.strip() for line in self.host_input.toPlainText().splitlines() if line.strip()]
        if not hosts:
            self.output.setPlainText("请先输入要 Ping 的目标地址。")
            return

        result_lines = []
        for host in hosts:
            result_lines.append(f"--- {host} ---")
            try:
                completed = run(["ping", "-c", "2", host], capture_output=True, text=True, check=False)
                output = completed.stdout or completed.stderr or "无输出"
                result_lines.append(output.strip() or "无输出")
            except Exception as exc:  # pragma: no cover - simple demo page
                result_lines.append(f"执行失败：{exc}")
        self.output.setPlainText("\n\n".join(result_lines))
