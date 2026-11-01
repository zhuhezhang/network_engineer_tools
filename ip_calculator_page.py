from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFormLayout, QLineEdit, QPushButton


class IpCalculatorPage(QWidget):
    """IP 地址计算页。"""

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("IP 地址计算")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)

        form = QFormLayout()
        self.ip_edit = QLineEdit("192.168.1.10")
        self.mask_edit = QLineEdit("255.255.255.0")
        form.addRow("IP 地址", self.ip_edit)
        form.addRow("子网掩码", self.mask_edit)
        layout.addLayout(form)

        self.calc_btn = QPushButton("计算")
        self.calc_btn.clicked.connect(self._calculate)
        layout.addWidget(self.calc_btn)

        self.result_label = QLabel("网络地址：\n广播地址：\n可用主机范围：")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        layout.addStretch()

    def _calculate(self):
        try:
            ip = self.ip_edit.text().strip()
            mask = self.mask_edit.text().strip()
            parts = ip.split('.')
            if len(parts) != 4 or any(not p.isdigit() for p in parts):
                raise ValueError("IP 地址格式错误")
            mask_parts = mask.split('.')
            if len(mask_parts) != 4 or any(not p.isdigit() for p in mask_parts):
                raise ValueError("子网掩码格式错误")

            octets = [int(p) for p in parts]
            mask_octets = [int(p) for p in mask_parts]
            network = [a & b for a, b in zip(octets, mask_octets)]
            broadcast = [a | (255 - b) for a, b in zip(octets, mask_octets)]
            prefix = sum(bin(m).count('1') for m in mask_octets)
            result = (
                f"网络地址：{'.'.join(map(str, network))}\n"
                f"广播地址：{'.'.join(map(str, broadcast))}\n"
                f"前缀长度：/{prefix}\n"
                f"可用主机范围：{'.'.join(map(str, network[:3]))}.1 - {'.'.join(map(str, broadcast[:3]))}.254"
            )
            self.result_label.setText(result)
        except Exception as exc:  # pragma: no cover - simple demo page
            self.result_label.setText(f"错误：{exc}")
