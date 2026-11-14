from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
from math import ceil, log2
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QFrame,
    QSizePolicy,
)


# ----- IPv4 计算辅助 -----


def parse_octet(text: str) -> int:
    """Parse a single IPv4 octet (0-255)."""
    value = int(text.strip())
    if not 0 <= value <= 255:
        raise ValueError(f"八位组超出范围: {value}")
    return value


def octets_to_ip(octets: List[str]) -> IPv4Address:
    """Build an IPv4Address from four octet strings."""
    if len(octets) != 4:
        raise ValueError("需要 4 个八位组")
    return IPv4Address(".".join(str(parse_octet(o)) for o in octets))


def octets_to_mask(octets: List[str]) -> int:
    """Convert dotted mask octets to a prefix length."""
    mask_ip = octets_to_ip(octets)
    try:
        return IPv4Network(f"0.0.0.0/{mask_ip}").prefixlen
    except ValueError as exc:
        raise ValueError(f"无效的子网掩码: {mask_ip}") from exc


def prefix_to_mask(prefix: int) -> IPv4Address:
    """Return the dotted-decimal mask for a prefix length."""
    if not 0 <= prefix <= 32:
        raise ValueError("子网掩码位数须在 0–32 之间")
    return IPv4Network(f"0.0.0.0/{prefix}").netmask


def prefix_to_mask_hex(prefix: int) -> str:
    """Return hexadecimal subnet mask like FF.FF.FF.00."""
    mask = int(prefix_to_mask(prefix))
    return ".".join(f"{(mask >> shift) & 0xFF:02X}" for shift in (24, 16, 8, 0))


def host_count_to_prefix(host_count: int) -> int:
    """
    Smallest prefix that can hold `host_count` addresses
    (including network and broadcast).
    """
    if host_count < 1:
        raise ValueError("地址数量须至少为 1")
    if host_count > 2**32:
        raise ValueError("地址数量过大")
    host_bits = ceil(log2(host_count)) if host_count > 1 else 0
    return 32 - host_bits


def usable_host_count(prefix: int) -> int:
    """Usable host addresses for a prefix (excludes network/broadcast when possible)."""
    if not 0 <= prefix <= 32:
        raise ValueError("子网掩码位数须在 0–32 之间")
    total = 2 ** (32 - prefix)
    if prefix >= 31:
        return total
    return total - 2


def total_address_count(prefix: int) -> int:
    if not 0 <= prefix <= 32:
        raise ValueError("子网掩码位数须在 0–32 之间")
    return 2 ** (32 - prefix)


def network_info(ip: IPv4Address, prefix: int) -> dict:
    """Compute network/broadcast/usable range for an IP + prefix."""
    if not 0 <= prefix <= 32:
        raise ValueError("子网掩码位数须在 0–32 之间")
    net = IPv4Network(f"{ip}/{prefix}", strict=False)
    hosts = list(net.hosts())
    if prefix >= 31:
        # /31 point-to-point and /32 host route: all addresses are usable
        first = net.network_address
        last = net.broadcast_address
        usable = total_address_count(prefix)
    else:
        first = hosts[0] if hosts else net.network_address
        last = hosts[-1] if hosts else net.broadcast_address
        usable = usable_host_count(prefix)
    return {
        "network": str(net.network_address),
        "broadcast": str(net.broadcast_address),
        "netmask": str(net.netmask),
        "wildcard": str(net.hostmask),
        "prefix": prefix,
        "first_usable": str(first),
        "last_usable": str(last),
        "usable_count": usable,
        "total_count": total_address_count(prefix),
    }


def ip_to_binary(ip: IPv4Address) -> str:
    value = int(ip)
    return ".".join(f"{(value >> shift) & 0xFF:08b}" for shift in (24, 16, 8, 0))


def split_by_host_sizes(
    base_ip: IPv4Address,
    host_sizes: List[int],
    base_prefix: Optional[int] = None,
) -> List[dict]:
    """
    VLSM-style split: allocate subnets for each required address count
    (counts include network + broadcast).
    """
    if not host_sizes:
        raise ValueError("请至少提供一个网络的主机数")

    # Start from the largest block that can hold all requested addresses
    # when base_prefix is not given, use the network implied by sorting needs.
    sizes = sorted(
        ((idx, size) for idx, size in enumerate(host_sizes)),
        key=lambda item: item[1],
        reverse=True,
    )

    if base_prefix is None:
        total_needed = sum(2 ** ceil(log2(max(s, 1))) for _, s in sizes)
        base_prefix = host_count_to_prefix(total_needed)

    current = IPv4Network(f"{base_ip}/{base_prefix}", strict=False).network_address
    end = int(IPv4Network(f"{base_ip}/{base_prefix}", strict=False).broadcast_address)
    results: List[Optional[dict]] = [None] * len(host_sizes)

    for orig_idx, size in sizes:
        prefix = host_count_to_prefix(size)
        net = IPv4Network(f"{current}/{prefix}", strict=False)
        if int(net.broadcast_address) > end:
            raise ValueError("地址空间不足以划分所有子网")
        info = network_info(net.network_address, prefix)
        info["required_addresses"] = size
        info["index"] = orig_idx + 1
        results[orig_idx] = info
        next_addr = int(net.broadcast_address) + 1
        if next_addr > 0xFFFFFFFF:
            if any(r is None for r in results):
                raise ValueError("地址空间不足以划分所有子网")
            break
        current = IPv4Address(next_addr)

    return [r for r in results if r is not None]


def reverse_mask_info(mask_octets: List[str]) -> dict:
    """Subnet mask reverse calculator."""
    prefix = octets_to_mask(mask_octets)
    mask = prefix_to_mask(prefix)
    return {
        "prefix": prefix,
        "netmask": str(mask),
        "wildcard": str(IPv4Network(f"0.0.0.0/{prefix}").hostmask),
        "mask_hex": prefix_to_mask_hex(prefix),
        "usable_count": usable_host_count(prefix),
        "total_count": total_address_count(prefix),
        "binary": ip_to_binary(mask),
    }


def format_network_list(networks: List[dict]) -> str:
    lines = []
    for net in networks:
        lines.append(
            f"网络 {net['index']}:\n"
            f"  需要地址: {net['required_addresses']}\n"
            f"  网络地址: {net['network']}/{net['prefix']}\n"
            f"  子网掩码: {net['netmask']}\n"
            f"  广播: {net['broadcast']}\n"
            f"  可用: {net['first_usable']} - {net['last_usable']}\n"
            f"  可用数量: {net['usable_count']}"
        )
    return "\n\n".join(lines)


class OctetRow(QWidget):
    """Four octet inputs, optionally followed by /prefix."""

    def __init__(self, defaults=("192", "168", "0", "1"), with_prefix=False, prefix_default=24, parent=None):
        super().__init__(parent)
        self._edits = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for i, default in enumerate(defaults):
            edit = QLineEdit(str(default))
            edit.setFixedWidth(52)
            edit.setAlignment(Qt.AlignCenter)
            edit.setMaxLength(3)
            self._edits.append(edit)
            layout.addWidget(edit)
            if i < 3:
                layout.addWidget(QLabel("."))

        self.prefix_spin = None
        if with_prefix:
            layout.addWidget(QLabel("/"))
            self.prefix_spin = QSpinBox()
            self.prefix_spin.setRange(0, 32)
            self.prefix_spin.setValue(prefix_default)
            self.prefix_spin.setFixedWidth(60)
            layout.addWidget(self.prefix_spin)

        layout.addStretch()

    def octets(self):
        return [e.text().strip() for e in self._edits]

    def set_octets(self, values):
        for edit, value in zip(self._edits, values):
            edit.setText(str(value))

    def prefix(self):
        return self.prefix_spin.value() if self.prefix_spin else None

    def set_prefix(self, value: int):
        if self.prefix_spin is not None:
            self.prefix_spin.setValue(value)

    def clear(self, defaults=("0", "0", "0", "0"), prefix=None):
        self.set_octets(defaults)
        if prefix is not None and self.prefix_spin is not None:
            self.prefix_spin.setValue(prefix)


SECTION_STYLE = """
QFrame#sectionBox {
    background-color: #f7f8fa;
    border: 1px solid #c5cad3;
    border-radius: 8px;
}
"""

RESULT_STYLE = """
QFrame#resultBox {
    background-color: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 4px;
}
"""


class ResultBox(QFrame):
    """Read-only result area with right-aligned labels that stay visible."""

    def __init__(self, labels=None, parent=None):
        super().__init__(parent)
        self.setObjectName("resultBox")
        self.setStyleSheet(RESULT_STYLE)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setMinimumHeight(72)
        self._fixed_labels = list(labels or [])
        self._value_labels: dict[str, QLabel] = {}
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignTop)

        self._title = QLabel("计算结果")
        self._title.setStyleSheet("font-weight: bold; color: #374151;")
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._layout.addWidget(self._title, 0, Qt.AlignTop | Qt.AlignLeft)

        self._form = QFormLayout()
        self._form.setContentsMargins(0, 0, 0, 0)
        self._form.setHorizontalSpacing(12)
        self._form.setVerticalSpacing(2)
        self._form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self._layout.addLayout(self._form)

        self._freeform = QLabel()
        self._freeform.setWordWrap(True)
        self._freeform.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._freeform.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._freeform.hide()
        self._layout.addWidget(self._freeform)

        # 占满剩余高度，避免空结果时标题垂直居中
        self._layout.addStretch(1)

        self._rebuild_fixed_rows()

    def _clear_form(self):
        while self._form.rowCount():
            self._form.removeRow(0)
        self._value_labels.clear()

    def _make_key_label(self, label: str) -> QLabel:
        key = QLabel(f"{label}:")
        key.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return key

    def _make_value_label(self, value="") -> QLabel:
        val = QLabel(str(value) if value is not None else "")
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        val.setWordWrap(True)
        val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return val

    def _add_row(self, label: str, value=""):
        key = self._make_key_label(label)
        val = self._make_value_label(value)
        self._form.addRow(key, val)
        self._value_labels[label] = val
        return val

    def _rebuild_fixed_rows(self):
        """Always show the predefined labels (empty values until calculated)."""
        self._clear_form()
        for label in self._fixed_labels:
            self._add_row(label, "")

    def set_rows(self, rows):
        """Show aligned label/value pairs. Each item is (label, value)."""
        self._freeform.hide()
        self._freeform.clear()
        self._title.setText("计算结果")
        row_map = {label: value for label, value in rows}
        if self._fixed_labels:
            if not self._value_labels:
                self._rebuild_fixed_rows()
            for label in self._fixed_labels:
                widget = self._value_labels.get(label)
                if widget is not None:
                    widget.setText(str(row_map.get(label, "")))
            return
        # No fixed schema: rebuild from provided rows
        self._fixed_labels = [label for label, _ in rows]
        self._rebuild_fixed_rows()
        for label, value in rows:
            self._value_labels[label].setText(str(value))

    def set_sections(self, sections):
        """Show multiple blocks. Each item is (heading, [(label, value), ...])."""
        self._clear_form()
        self._freeform.hide()
        self._freeform.clear()
        self._title.setText("计算结果")
        for heading, rows in sections:
            head = QLabel(heading)
            head.setStyleSheet("font-weight: bold; color: #1f2937; padding-top: 4px;")
            head.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._form.addRow(head)
            for label, value in rows:
                self._add_row(label, value)

    def set_result(self, text: str):
        """Free-form text (errors, etc.); keep fixed labels visible."""
        self._title.setText("计算结果")
        if self._fixed_labels:
            self._rebuild_fixed_rows()
        else:
            self._clear_form()
        body = text
        if body.startswith("计算结果\n"):
            body = body[len("计算结果\n") :]
        body = body.lstrip("\n")
        if not body:
            self._freeform.hide()
            self._freeform.clear()
            return
        self._freeform.setText(body)
        self._freeform.show()

    def clear(self):
        self._freeform.hide()
        self._freeform.clear()
        self._title.setText("计算结果")
        if self._fixed_labels:
            self._rebuild_fixed_rows()
        else:
            self._clear_form()


def _btn_row(*buttons):
    row = QHBoxLayout()
    for btn in buttons:
        row.addWidget(btn)
    row.addStretch()
    return row


def _make_section(title: str):
    """带边框分区：标题放在框内顶部。"""
    box = QFrame()
    box.setObjectName("sectionBox")
    box.setStyleSheet(SECTION_STYLE)
    outer = QVBoxLayout(box)
    outer.setContentsMargins(14, 12, 14, 12)
    outer.setSpacing(8)

    heading = QLabel(title)
    heading.setObjectName("sectionTitle")
    heading.setStyleSheet(
        "QLabel#sectionTitle {"
        "font-size: 14px; font-weight: bold; color: #1f2937;"
        "padding-bottom: 6px;"
        "border-bottom: 1px solid #d0d5dd;"
        "}"
    )
    heading.setWordWrap(True)
    outer.addWidget(heading)

    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.WrapLongRows)
    form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
    form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
    outer.addLayout(form)
    return box, form


class IpCalculatorPage(QWidget):
    """IP 地址计算页（多工具分区，可滚动）。"""

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        root.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        # 左右贴边；上下与左侧导航栏边距一致（nav_layout top/bottom = 10）
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(12)

        # 左右两列独立堆叠，高度互不影响（不按行对齐抬高）
        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(10)

        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(10)
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(10)

        left_sections = [
            self._build_network_ip_section(),
            self._build_prefix_mask_section(),
            self._build_host_count_section(),
            self._build_vlsm_section(),
        ]
        right_sections = [
            self._build_mask_converter_section(),
            self._build_mask_reverse_section(),
        ]
        for section in left_sections:
            section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            left_col.addWidget(section)
        for section in right_sections:
            section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            right_col.addWidget(section)
        left_col.addStretch()
        right_col.addStretch()

        columns.addLayout(left_col, 1)
        columns.addLayout(right_col, 1)
        layout.addLayout(columns)

    # ----- 1. 网络和IP地址计算器 -----
    def _build_network_ip_section(self) -> QFrame:
        box, form = _make_section("网络和 IP 地址计算器")

        self.net_ip_row = OctetRow(("192", "168", "0", "1"), with_prefix=True, prefix_default=24)
        form.addRow("IP / 子网掩码位数:", self.net_ip_row)

        calc = QPushButton("计算")
        clear = QPushButton("清除重算")
        calc.clicked.connect(self._calc_network_ip)
        clear.clicked.connect(self._clear_network_ip)
        form.addRow(_btn_row(calc, clear))

        self.net_ip_result = ResultBox(
            ["可用地址", "子网掩码", "网络地址", "第一个可用", "最后可用", "广播"]
        )
        form.addRow(self.net_ip_result)
        return box

    def _calc_network_ip(self):
        try:
            ip = octets_to_ip(self.net_ip_row.octets())
            prefix = self.net_ip_row.prefix()
            info = network_info(ip, prefix)
            self.net_ip_result.set_rows(
                [
                    ("可用地址", info["usable_count"]),
                    ("子网掩码", info["netmask"]),
                    ("网络地址", info["network"]),
                    ("第一个可用", info["first_usable"]),
                    ("最后可用", info["last_usable"]),
                    ("广播", info["broadcast"]),
                ]
            )
        except Exception as exc:
            self.net_ip_result.set_result(f"错误：{exc}")

    def _clear_network_ip(self):
        self.net_ip_row.clear(("192", "168", "0", "1"), prefix=24)
        self.net_ip_result.clear()

    # ----- 2. 通过子网掩码位数计算子网掩码 -----
    def _build_prefix_mask_section(self) -> QFrame:
        box, form = _make_section("通过子网掩码位数计算子网掩码")

        row = QHBoxLayout()
        row.addWidget(QLabel("/"))
        self.prefix_mask_spin = QSpinBox()
        self.prefix_mask_spin.setRange(0, 32)
        self.prefix_mask_spin.setValue(27)
        self.prefix_mask_spin.setFixedWidth(60)
        row.addWidget(self.prefix_mask_spin)
        row.addStretch()
        form.addRow("子网掩码位数:", row)

        calc = QPushButton("计算")
        clear = QPushButton("清除重算")
        calc.clicked.connect(self._calc_prefix_mask)
        clear.clicked.connect(self._clear_prefix_mask)
        form.addRow(_btn_row(calc, clear))

        self.prefix_mask_result = ResultBox(
            ["可用地址的数量", "地址总数", "子网掩码"]
        )
        form.addRow(self.prefix_mask_result)
        return box

    def _calc_prefix_mask(self):
        try:
            prefix = self.prefix_mask_spin.value()
            self.prefix_mask_result.set_rows(
                [
                    ("可用地址的数量", usable_host_count(prefix)),
                    ("地址总数", total_address_count(prefix)),
                    ("子网掩码", prefix_to_mask(prefix)),
                ]
            )
        except Exception as exc:
            self.prefix_mask_result.set_result(f"错误：{exc}")

    def _clear_prefix_mask(self):
        self.prefix_mask_spin.setValue(27)
        self.prefix_mask_result.clear()

    # ----- 3. 通过主机数量计算子网掩码 -----
    def _build_host_count_section(self) -> QFrame:
        box, form = _make_section("通过主机数量计算子网掩码")

        self.host_count_spin = QSpinBox()
        self.host_count_spin.setRange(1, 2**31 - 1)
        self.host_count_spin.setValue(5)
        self.host_count_spin.setMaximumWidth(120)
        form.addRow("需要地址的数量:", self.host_count_spin)

        calc = QPushButton("计算")
        clear = QPushButton("清除重算")
        calc.clicked.connect(self._calc_host_count)
        clear.clicked.connect(self._clear_host_count)
        form.addRow(_btn_row(calc, clear))

        self.host_count_result = ResultBox(["子网掩码位数", "子网掩码"])
        form.addRow(self.host_count_result)
        return box

    def _calc_host_count(self):
        try:
            count = self.host_count_spin.value()
            prefix = host_count_to_prefix(count)
            self.host_count_result.set_rows(
                [
                    ("子网掩码位数", f"/{prefix}"),
                    ("子网掩码", prefix_to_mask(prefix)),
                ]
            )
        except Exception as exc:
            self.host_count_result.set_result(f"错误：{exc}")

    def _clear_host_count(self):
        self.host_count_spin.setValue(5)
        self.host_count_result.clear()

    # ----- 4. IP地址子网掩码计算器（VLSM / 网络列表） -----
    def _build_vlsm_section(self) -> QFrame:
        box, form = _make_section("IP 地址子网掩码计算器")

        self.vlsm_ip_row = OctetRow(("192", "168", "0", "0"), with_prefix=True, prefix_default=24)
        form.addRow("TCP/IP 地址:", self.vlsm_ip_row)

        note = QLabel("网络列表 — 每个网络的节点/主机数（含网络和广播地址），每行一个数字：")
        note.setWordWrap(True)
        form.addRow(note)

        self.vlsm_hosts = QTextEdit()
        self.vlsm_hosts.setPlaceholderText("例如：\n30\n14\n6")
        self.vlsm_hosts.setFixedHeight(90)
        self.vlsm_hosts.setPlainText("30\n14\n6")
        form.addRow(self.vlsm_hosts)

        calc = QPushButton("网络列表")
        clear = QPushButton("清除重算")
        calc.clicked.connect(self._calc_vlsm)
        clear.clicked.connect(self._clear_vlsm)
        form.addRow(_btn_row(calc, clear))

        self.vlsm_result = ResultBox(
            ["需要地址", "网络地址", "子网掩码", "广播", "可用", "可用数量"]
        )
        form.addRow(self.vlsm_result)
        return box

    def _calc_vlsm(self):
        try:
            ip = octets_to_ip(self.vlsm_ip_row.octets())
            prefix = self.vlsm_ip_row.prefix()
            sizes = []
            for line in self.vlsm_hosts.toPlainText().splitlines():
                line = line.strip()
                if not line:
                    continue
                sizes.append(int(line))
            networks = split_by_host_sizes(ip, sizes, base_prefix=prefix)
            sections = []
            for net in networks:
                sections.append(
                    (
                        f"网络 {net['index']}",
                        [
                            ("需要地址", net["required_addresses"]),
                            ("网络地址", f"{net['network']}/{net['prefix']}"),
                            ("子网掩码", net["netmask"]),
                            ("广播", net["broadcast"]),
                            ("可用", f"{net['first_usable']} - {net['last_usable']}"),
                            ("可用数量", net["usable_count"]),
                        ],
                    )
                )
            self.vlsm_result.set_sections(sections)
        except Exception as exc:
            self.vlsm_result.set_result(f"错误：{exc}")

    def _clear_vlsm(self):
        self.vlsm_ip_row.clear(("192", "168", "0", "0"), prefix=24)
        self.vlsm_hosts.setPlainText("30\n14\n6")
        self.vlsm_result.clear()

    # ----- 5. 子网掩码换算器 -----
    def _build_mask_converter_section(self) -> QFrame:
        box, form = _make_section("子网掩码换算器")

        self.mask_conv_row = OctetRow(("255", "255", "255", "0"))
        form.addRow("十进制子网掩码:", self.mask_conv_row)

        prefix_row = QHBoxLayout()
        prefix_row.addWidget(QLabel("/"))
        self.mask_conv_prefix = QSpinBox()
        self.mask_conv_prefix.setRange(0, 32)
        self.mask_conv_prefix.setValue(24)
        self.mask_conv_prefix.setFixedWidth(60)
        prefix_row.addWidget(self.mask_conv_prefix)
        prefix_row.addStretch()
        form.addRow("子网掩码位数:", prefix_row)

        to_prefix = QPushButton("子网掩码 → 位数")
        to_mask = QPushButton("位数 → 子网掩码")
        clear = QPushButton("清除重算")
        to_prefix.clicked.connect(self._mask_to_prefix)
        to_mask.clicked.connect(self._prefix_to_mask_conv)
        clear.clicked.connect(self._clear_mask_converter)
        form.addRow(_btn_row(to_prefix, to_mask, clear))

        self.mask_conv_result = ResultBox(["十进制子网掩码", "子网掩码位数"])
        form.addRow(self.mask_conv_result)
        return box

    def _mask_to_prefix(self):
        try:
            prefix = octets_to_mask(self.mask_conv_row.octets())
            self.mask_conv_prefix.setValue(prefix)
            self.mask_conv_result.set_rows(
                [
                    ("十进制子网掩码", ".".join(self.mask_conv_row.octets())),
                    ("子网掩码位数", f"/{prefix}"),
                ]
            )
        except Exception as exc:
            self.mask_conv_result.set_result(f"错误：{exc}")

    def _prefix_to_mask_conv(self):
        try:
            prefix = self.mask_conv_prefix.value()
            mask = prefix_to_mask(prefix)
            self.mask_conv_row.set_octets(str(mask).split("."))
            self.mask_conv_result.set_rows(
                [
                    ("子网掩码位数", f"/{prefix}"),
                    ("十进制子网掩码", mask),
                ]
            )
        except Exception as exc:
            self.mask_conv_result.set_result(f"错误：{exc}")

    def _clear_mask_converter(self):
        self.mask_conv_row.clear(("255", "255", "255", "0"))
        self.mask_conv_prefix.setValue(24)
        self.mask_conv_result.clear()

    # ----- 6. 子网掩码逆算器 -----
    def _build_mask_reverse_section(self) -> QFrame:
        box, form = _make_section("子网掩码逆算器")

        self.rev_mask_row = OctetRow(("255", "255", "255", "0"))
        form.addRow("子网掩码:", self.rev_mask_row)

        calc = QPushButton("计算")
        clear = QPushButton("清除重算")
        calc.clicked.connect(self._calc_mask_reverse)
        clear.clicked.connect(self._clear_mask_reverse)
        form.addRow(_btn_row(calc, clear))

        self.rev_mask_result = ResultBox(
            [
                "子网掩码位数",
                "子网掩码",
                "十六进制子网掩码",
                "反掩码",
                "二进制子网掩码",
                "可用地址数量",
                "地址总数",
            ]
        )
        form.addRow(self.rev_mask_result)
        return box

    def _calc_mask_reverse(self):
        try:
            info = reverse_mask_info(self.rev_mask_row.octets())
            self.rev_mask_result.set_rows(
                [
                    ("子网掩码位数", f"/{info['prefix']}"),
                    ("子网掩码", info["netmask"]),
                    ("十六进制子网掩码", info["mask_hex"]),
                    ("反掩码", info["wildcard"]),
                    ("二进制子网掩码", info["binary"]),
                    ("可用地址数量", info["usable_count"]),
                    ("地址总数", info["total_count"]),
                ]
            )
        except Exception as exc:
            self.rev_mask_result.set_result(f"错误：{exc}")

    def _clear_mask_reverse(self):
        self.rev_mask_row.clear(("255", "255", "255", "0"))
        self.rev_mask_result.clear()
