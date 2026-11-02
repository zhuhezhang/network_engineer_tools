from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFormLayout, QLineEdit, QPushButton


class NetworkIpSetupPage(QWidget):
    """网卡 IP 设置页。"""

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        self.interface_edit = QLineEdit("en0")
        self.ip_edit = QLineEdit("192.168.1.10")
        self.mask_edit = QLineEdit("255.255.255.0")
        self.gateway_edit = QLineEdit("192.168.1.1")
        form.addRow("网卡名称", self.interface_edit)
        form.addRow("IP 地址", self.ip_edit)
        form.addRow("子网掩码", self.mask_edit)
        form.addRow("网关", self.gateway_edit)
        layout.addLayout(form)

        self.apply_btn = QPushButton("应用配置")
        self.apply_btn.clicked.connect(self._apply_config)
        layout.addWidget(self.apply_btn)

        self.result_label = QLabel("此功能为示例页，可扩展为实际网卡配置逻辑。")
        layout.addWidget(self.result_label)
        layout.addStretch()

    def _apply_config(self):
        iface = self.interface_edit.text().strip() or "未指定"
        ip = self.ip_edit.text().strip() or "0.0.0.0"
        mask = self.mask_edit.text().strip() or "255.255.255.0"
        gateway = self.gateway_edit.text().strip() or "0.0.0.0"
        self.result_label.setText(
            f"网卡：{iface}\nIP：{ip}\n掩码：{mask}\n网关：{gateway}\n\n配置已提交（示例页面）。"
        )
