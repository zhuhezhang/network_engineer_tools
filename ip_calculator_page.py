from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
from math import ceil, log2
from typing import Callable, List, Optional

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
    QMessageBox,
)


PAGE_TRANSLATIONS = {
    "zh": {
        "section_network_ip": "网络和 IP 地址计算",
        "section_covering": "计算最小包含地址范围",
        "section_vlsm": "根据主机数划分子网",
        "label_ip": "IP 地址:",
        "label_mask": "子网掩码:",
        "label_wildcard": "反掩码:",
        "btn_calc": "开始计算",
        "btn_clear": "清除重算",
        "result_title": "计算结果",
        "result_total_count": "地址总数",
        "result_network": "网络地址",
        "result_usable_range": "可用地址范围",
        "result_broadcast": "广播地址",
        "result_min_cidr": "最小网段",
        "result_mask": "子网掩码",
        "result_addr_range": "地址范围",
        "result_required": "所需地址数",
        "result_host_count": "主机地址数",
        "result_host_range": "主机地址范围",
        "covering_note": (
            "每行输入一个 IP、CIDR 或「IP 地址 子网掩码」（无掩码默认 /32），"
            "仅支持换行分隔，计算能包含它们的最小网段"
        ),
        "covering_placeholder": "例如：\n192.168.0.0\n192.168.0.9/29\n192.0.0.1 255.255.255.0",
        "vlsm_note": (
            "输入每个子网的所需地址数（含网络和广播地址），"
            "支持换行、逗号、空格或中文逗号分隔"
        ),
        "vlsm_placeholder": "例如：\n30\n14\n6\n或：30, 14, 6",
        "network_heading": "网络 {index}",
        "calc_error_title": "计算错误",
        "err_octet_empty": "八位组不能为空",
        "err_octet_invalid": "无效的八位组: {value}",
        "err_octet_range": "八位组超出范围: {value}",
        "err_need_four_octets": "需要 4 个八位组",
        "err_invalid_mask": "无效的子网掩码: {value}",
        "err_prefix_range": "子网掩码位数须在 0–32 之间",
        "err_invalid_wildcard": "无效的反掩码: {value}",
        "err_host_count_min": "地址数量须至少为 1",
        "err_host_count_max": "地址数量过大",
        "err_need_host_sizes": "请至少提供一个网络的主机数",
        "err_insufficient_space": "地址空间不足以划分所有子网",
        "err_addr_empty": "地址不能为空",
        "err_invalid_ip_cidr": "无效的 IP/网段: {value}",
        "err_need_one_ip": "请至少输入一个 IP 地址或地址段",
        "err_cannot_cover": "无法计算包含这些地址的范围",
        "err_invalid_host_count": "无效的主机数: {value}",
    },
    "en": {
        "section_network_ip": "Network & IP Address Calculator",
        "section_covering": "Minimal Covering Network",
        "section_vlsm": "Subnet by Host Count (VLSM)",
        "label_ip": "IP Address:",
        "label_mask": "Subnet Mask:",
        "label_wildcard": "Wildcard Mask:",
        "btn_calc": "Calculate",
        "btn_clear": "Clear",
        "result_title": "Result",
        "result_total_count": "Total Addresses",
        "result_network": "Network Address",
        "result_usable_range": "Usable Range",
        "result_broadcast": "Broadcast Address",
        "result_min_cidr": "Minimal CIDR",
        "result_mask": "Subnet Mask",
        "result_addr_range": "Address Range",
        "result_required": "Required Addresses",
        "result_host_count": "Usable Hosts",
        "result_host_range": "Host Range",
        "covering_note": (
            "Enter one IP, CIDR, or \"IP dotted-mask\" per line (bare IP defaults to /32). "
            "Newlines only. Computes the smallest network that covers them all."
        ),
        "covering_placeholder": "Example:\n192.168.0.0\n192.168.0.9/29\n192.0.0.1 255.255.255.0",
        "vlsm_note": (
            "Enter required address counts per subnet (including network and broadcast). "
            "Separated by newlines, commas, spaces, or Chinese commas."
        ),
        "vlsm_placeholder": "Example:\n30\n14\n6\nor: 30, 14, 6",
        "network_heading": "Network {index}",
        "calc_error_title": "Calculation Error",
        "err_octet_empty": "Octet cannot be empty",
        "err_octet_invalid": "Invalid octet: {value}",
        "err_octet_range": "Octet out of range: {value}",
        "err_need_four_octets": "Four octets are required",
        "err_invalid_mask": "Invalid subnet mask: {value}",
        "err_prefix_range": "Prefix length must be between 0 and 32",
        "err_invalid_wildcard": "Invalid wildcard mask: {value}",
        "err_host_count_min": "Address count must be at least 1",
        "err_host_count_max": "Address count is too large",
        "err_need_host_sizes": "Provide at least one host-count requirement",
        "err_insufficient_space": "Address space is insufficient for all subnets",
        "err_addr_empty": "Address cannot be empty",
        "err_invalid_ip_cidr": "Invalid IP/CIDR: {value}",
        "err_need_one_ip": "Enter at least one IP address or network",
        "err_cannot_cover": "Unable to compute a covering range for these addresses",
        "err_invalid_host_count": "Invalid host count: {value}",
    },
}


class IpCalcError(ValueError):
    """Raised with a translation key so the UI can localize the message."""

    def __init__(self, key: str, **params):
        self.key = key
        self.params = params
        super().__init__(key)


# ----- IPv4 计算辅助 -----


def parse_octet(text: str) -> int:
    """Parse a single IPv4 octet (0-255)."""
    text = text.strip()
    if not text:
        raise IpCalcError("err_octet_empty")
    try:
        value = int(text)
    except ValueError as exc:
        raise IpCalcError("err_octet_invalid", value=text) from exc
    if not 0 <= value <= 255:
        raise IpCalcError("err_octet_range", value=value)
    return value


def octets_to_ip(octets: List[str]) -> IPv4Address:
    """Build an IPv4Address from four octet strings."""
    if len(octets) != 4:
        raise IpCalcError("err_need_four_octets")
    return IPv4Address(".".join(str(parse_octet(o)) for o in octets))


def octets_to_mask(octets: List[str]) -> int:
    """Convert dotted mask octets to a prefix length."""
    mask_ip = octets_to_ip(octets)
    try:
        return IPv4Network(f"0.0.0.0/{mask_ip}").prefixlen
    except ValueError as exc:
        raise IpCalcError("err_invalid_mask", value=mask_ip) from exc


def prefix_to_mask(prefix: int) -> IPv4Address:
    """Return the dotted-decimal mask for a prefix length."""
    if not 0 <= prefix <= 32:
        raise IpCalcError("err_prefix_range")
    return IPv4Network(f"0.0.0.0/{prefix}").netmask


def prefix_to_wildcard(prefix: int) -> IPv4Address:
    """Return the dotted-decimal wildcard (host) mask for a prefix length."""
    if not 0 <= prefix <= 32:
        raise IpCalcError("err_prefix_range")
    return IPv4Network(f"0.0.0.0/{prefix}").hostmask


def octets_to_wildcard_prefix(octets: List[str]) -> int:
    """Convert dotted wildcard-mask octets to a prefix length."""
    wildcard_ip = octets_to_ip(octets)
    mask_ip = IPv4Address((~int(wildcard_ip)) & 0xFFFFFFFF)
    try:
        return IPv4Network(f"0.0.0.0/{mask_ip}").prefixlen
    except ValueError as exc:
        raise IpCalcError("err_invalid_wildcard", value=wildcard_ip) from exc


def host_count_to_prefix(host_count: int) -> int:
    """
    Smallest prefix that can hold `host_count` addresses
    (including network and broadcast).
    """
    if host_count < 1:
        raise IpCalcError("err_host_count_min")
    if host_count > 2**32:
        raise IpCalcError("err_host_count_max")
    host_bits = ceil(log2(host_count)) if host_count > 1 else 0
    return 32 - host_bits


def usable_host_count(prefix: int) -> int:
    """Usable host addresses for a prefix (excludes network/broadcast when possible)."""
    if not 0 <= prefix <= 32:
        raise IpCalcError("err_prefix_range")
    total = 2 ** (32 - prefix)
    if prefix >= 31:
        return total
    return total - 2


def total_address_count(prefix: int) -> int:
    if not 0 <= prefix <= 32:
        raise IpCalcError("err_prefix_range")
    return 2 ** (32 - prefix)


def network_info(ip: IPv4Address, prefix: int) -> dict:
    """Compute network/broadcast/usable range for an IP + prefix."""
    if not 0 <= prefix <= 32:
        raise IpCalcError("err_prefix_range")
    net = IPv4Network(f"{ip}/{prefix}", strict=False)
    if prefix >= 31:
        # /31 point-to-point and /32 host route: all addresses are usable
        first = net.network_address
        last = net.broadcast_address
        usable = total_address_count(prefix)
    else:
        # Avoid list(net.hosts()) — it enumerates every address and freezes on large nets
        first = IPv4Address(int(net.network_address) + 1)
        last = IPv4Address(int(net.broadcast_address) - 1)
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
        raise IpCalcError("err_need_host_sizes")

    # Start from the largest block that can hold all requested addresses
    # when base_prefix is not given, use the network implied by sorting needs
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
            raise IpCalcError("err_insufficient_space")
        info = network_info(net.network_address, prefix)
        info["required_addresses"] = size
        info["index"] = orig_idx + 1
        results[orig_idx] = info
        next_addr = int(net.broadcast_address) + 1
        if next_addr > 0xFFFFFFFF:
            if any(r is None for r in results):
                raise IpCalcError("err_insufficient_space")
            break
        current = IPv4Address(next_addr)

    return [r for r in results if r is not None]


def format_network_list(networks: List[dict], tr: Optional[Callable[[str], str]] = None) -> str:
    def _t(key: str) -> str:
        if tr is not None:
            return tr(key)
        return PAGE_TRANSLATIONS["zh"].get(key, key)

    lines = []
    for net in networks:
        lines.append(
            f"{_t('network_heading').format(index=net['index'])}:\n"
            f"  {_t('result_required')}: {net['required_addresses']}\n"
            f"  {_t('result_network')}: {net['network']}/{net['prefix']}\n"
            f"  {_t('result_mask')}: {net['netmask']}\n"
            f"  {_t('result_broadcast')}: {net['broadcast']}\n"
            f"  {_t('result_usable_range')}: {net['first_usable']} - {net['last_usable']}\n"
            f"  {_t('result_host_count')}: {net['usable_count']}"
        )
    return "\n\n".join(lines)


def parse_ip_or_cidr(token: str) -> IPv4Network:
    """
    Parse a single line: bare IP, CIDR, or "IP dotted-mask".
    Bare IP (no mask) defaults to /32.
    Examples: 192.168.0.1 / 192.168.0.1/24 / 192.168.0.1 255.255.255.0
    """
    token = token.strip()
    if not token:
        raise IpCalcError("err_addr_empty")
    parts = token.split()
    if len(parts) == 2:
        ip_part, mask_part = parts
        if "/" in ip_part:
            raise IpCalcError("err_invalid_ip_cidr", value=token)
        try:
            return IPv4Network(f"{ip_part}/{mask_part}", strict=False)
        except ValueError as exc:
            raise IpCalcError("err_invalid_ip_cidr", value=token) from exc
    if len(parts) != 1:
        raise IpCalcError("err_invalid_ip_cidr", value=token)
    entry = parts[0]
    if "/" not in entry:
        entry = f"{entry}/32"
    try:
        return IPv4Network(entry, strict=False)
    except ValueError as exc:
        raise IpCalcError("err_invalid_ip_cidr", value=entry) from exc


def parse_ip_cidr_list(text: str) -> List[IPv4Network]:
    """
    Parse multiple IPs/CIDRs, one entry per line (newline-separated only).
    Each line may be a bare IP, CIDR, or "IP dotted-mask".
    """
    networks: List[IPv4Network] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = line.strip()
        if line:
            networks.append(parse_ip_or_cidr(line))
    if not networks:
        raise IpCalcError("err_need_one_ip")
    return networks


def minimal_covering_network(networks: List[IPv4Network]) -> IPv4Network:
    """
    Smallest single CIDR that fully contains every given network.
    """
    if not networks:
        raise IpCalcError("err_need_one_ip")
    first = min(int(n.network_address) for n in networks)
    last = max(int(n.broadcast_address) for n in networks)
    xor = first ^ last
    prefix = 32 - xor.bit_length() if xor else 32
    while prefix >= 0:
        net = IPv4Network((first, prefix), strict=False)
        if int(net.network_address) <= first and int(net.broadcast_address) >= last:
            return net
        prefix -= 1
    raise IpCalcError("err_cannot_cover")


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

    def connect_changed(self, slot):
        """Connect a callback to octet (and optional prefix) changes."""
        for edit in self._edits:
            edit.textChanged.connect(slot)
        if self.prefix_spin is not None:
            self.prefix_spin.valueChanged.connect(slot)


# 功能分区最小宽度：窗口更窄时由外层滚动区出现横向滚动条
SECTION_MIN_WIDTH = 420

SECTION_STYLE = """
QFrame#sectionBox {
    background-color: #f7f8fa;
    border: 1px solid #c5cad3;
    border-radius: 0px;
}
"""

RESULT_STYLE = """
QFrame#resultBox {
    background-color: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 0px;
}
"""


class ResultBox(QFrame):
    """Read-only result area with right-aligned labels that stay visible"""

    def __init__(self, label_keys=None, parent=None):
        super().__init__(parent)
        self.setObjectName("resultBox")
        self.setStyleSheet(RESULT_STYLE)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setMinimumHeight(72)
        self._fixed_keys = list(label_keys or [])
        self._value_labels: dict[str, QLabel] = {}
        self._key_labels: dict[str, QLabel] = {}
        self._tr: Callable[[str], str] = lambda key: key
        self._mode = "fixed"  # fixed | rows | sections
        self._cached_rows: Optional[list] = None
        self._cached_sections: Optional[list] = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignTop)

        self._title = QLabel()
        self._title.setStyleSheet("font-weight: bold; color: #374151;")
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._layout.addWidget(self._title, 0, Qt.AlignTop | Qt.AlignLeft)

        self._form = QFormLayout()
        self._form.setContentsMargins(0, 0, 0, 0)
        self._form.setHorizontalSpacing(10)
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

    def set_translator(self, tr: Callable[[str], str]):
        self._tr = tr

    def retranslate(self):
        self._title.setText(self._tr("result_title"))
        if self._mode == "sections" and self._cached_sections is not None:
            self.set_sections(self._cached_sections)
        elif self._mode == "rows" and self._cached_rows is not None:
            self.set_rows(self._cached_rows)
        else:
            self._rebuild_fixed_rows()

    def _clear_form(self):
        while self._form.rowCount():
            self._form.removeRow(0)
        self._value_labels.clear()
        self._key_labels.clear()

    def _make_key_label(self, label: str) -> QLabel:
        key = QLabel(f"{label}:")
        key.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return key

    def _make_value_label(self, value="") -> QLabel:
        val = QLabel(str(value) if value is not None else "")
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # wordWrap=True 会让 sizeHint 过窄，长文本换行后第二行被行高裁掉
        val.setWordWrap(False)
        val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        val.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return val

    @staticmethod
    def _apply_value_text(widget: QLabel, value) -> None:
        text = str(value) if value is not None else ""
        widget.setText(text)
        # 按完整文本占位，避免可用地址范围等长串被裁切
        text_width = widget.fontMetrics().horizontalAdvance(text) if text else 0
        widget.setMinimumWidth(text_width + 4)

    def _add_row(self, key: str, value=""):
        label_text = self._tr(key)
        key_widget = self._make_key_label(label_text)
        val = self._make_value_label(value)
        self._apply_value_text(val, value)
        self._form.addRow(key_widget, val)
        self._key_labels[key] = key_widget
        self._value_labels[key] = val
        return val

    def _rebuild_fixed_rows(self):
        """Always show the predefined labels (empty values until calculated)."""
        self._clear_form()
        for key in self._fixed_keys:
            self._add_row(key, "")

    def set_rows(self, rows):
        """Show aligned label/value pairs. Each item is (label_key, value)."""
        self._mode = "rows"
        self._cached_rows = list(rows)
        self._cached_sections = None
        self._freeform.hide()
        self._freeform.clear()
        self._title.setText(self._tr("result_title"))
        row_map = {key: value for key, value in rows}
        keys = self._fixed_keys or [key for key, _ in rows]
        if self._fixed_keys:
            if not self._value_labels:
                self._rebuild_fixed_rows()
            for key in self._fixed_keys:
                key_widget = self._key_labels.get(key)
                if key_widget is not None:
                    key_widget.setText(f"{self._tr(key)}:")
                widget = self._value_labels.get(key)
                if widget is not None:
                    self._apply_value_text(widget, row_map.get(key, ""))
            self.updateGeometry()
            return
        # No fixed schema: rebuild from provided rows
        self._fixed_keys = list(keys)
        self._rebuild_fixed_rows()
        for key, value in rows:
            self._apply_value_text(self._value_labels[key], value)
        self.updateGeometry()

    def _heading_text(self, heading) -> str:
        """heading 可为纯文本，或 (translation_key, format_kwargs)。"""
        if isinstance(heading, tuple) and len(heading) == 2 and isinstance(heading[0], str):
            key, params = heading
            return self._tr(key).format(**(params or {}))
        return str(heading)

    def set_sections(self, sections):
        """Show multiple blocks. Each item is (heading, [(label_key, value), ...])."""
        self._mode = "sections"
        self._cached_sections = list(sections)
        self._cached_rows = None
        self._clear_form()
        self._freeform.hide()
        self._freeform.clear()
        self._title.setText(self._tr("result_title"))
        for heading, rows in sections:
            head = QLabel(self._heading_text(heading))
            head.setStyleSheet("font-weight: bold; color: #1f2937; padding-top: 4px;")
            head.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._form.addRow(head)
            for key, value in rows:
                self._add_row(key, value)
        self.updateGeometry()

    def clear(self):
        self._mode = "fixed"
        self._cached_rows = None
        self._cached_sections = None
        self._freeform.hide()
        self._freeform.clear()
        self._title.setText(self._tr("result_title"))
        if self._fixed_keys:
            self._rebuild_fixed_rows()
        else:
            self._clear_form()


def _btn_row(*buttons):
    row = QHBoxLayout()
    for btn in buttons:
        row.addWidget(btn)
    row.addStretch()
    return row


def _make_section(title: str = ""):
    """带边框分区：标题放在框内顶部"""
    box = QFrame()
    box.setObjectName("sectionBox")
    box.setStyleSheet(SECTION_STYLE)
    outer = QVBoxLayout(box)
    outer.setContentsMargins(10, 10, 10, 10)
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
    return box, form, heading


class IpCalculatorPage(QWidget):
    """IP 地址计算页（多工具分区，可滚动）"""

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self._init_ui()
        self.retranslate_ui()

    def _lang(self) -> str:
        if self.main_window and getattr(self.main_window, "current_lang", None):
            return self.main_window.current_lang
        return "zh"

    def _tr(self, key: str) -> str:
        return PAGE_TRANSLATIONS[self._lang()].get(key, key)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        root.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

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
            self._build_covering_section(),
        ]
        right_sections = [
            self._build_vlsm_section(),
        ]
        for section in left_sections:
            section.setMinimumWidth(SECTION_MIN_WIDTH)
            section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            left_col.addWidget(section)
        for section in right_sections:
            section.setMinimumWidth(SECTION_MIN_WIDTH)
            section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            right_col.addWidget(section)
        left_col.addStretch()
        right_col.addStretch()

        columns.addLayout(left_col, 1)
        columns.addLayout(right_col, 1)
        layout.addLayout(columns)

        # 保证两列最小宽度不被压缩；更窄时由 scroll 出现横向滚动条
        container.setMinimumWidth(SECTION_MIN_WIDTH * 2 + columns.spacing())

    def retranslate_ui(self) -> None:
        tr = self._tr
        self.net_ip_title.setText(tr("section_network_ip"))
        self.net_ip_label.setText(tr("label_ip"))
        self.net_ip_mask_label.setText(tr("label_mask"))
        self.net_ip_wildcard_label.setText(tr("label_wildcard"))
        self.net_ip_calc_btn.setText(tr("btn_calc"))
        self.net_ip_clear_btn.setText(tr("btn_clear"))
        self.net_ip_result.set_translator(tr)
        self.net_ip_result.retranslate()

        self.covering_title.setText(tr("section_covering"))
        self.covering_note.setText(tr("covering_note"))
        self.covering_input.setPlaceholderText(tr("covering_placeholder"))
        self.covering_calc_btn.setText(tr("btn_calc"))
        self.covering_clear_btn.setText(tr("btn_clear"))
        self.covering_result.set_translator(tr)
        self.covering_result.retranslate()

        self.vlsm_title.setText(tr("section_vlsm"))
        self.vlsm_ip_label.setText(tr("label_ip"))
        self.vlsm_mask_label.setText(tr("label_mask"))
        self.vlsm_wildcard_label.setText(tr("label_wildcard"))
        self.vlsm_note.setText(tr("vlsm_note"))
        self.vlsm_hosts.setPlaceholderText(tr("vlsm_placeholder"))
        self.vlsm_calc_btn.setText(tr("btn_calc"))
        self.vlsm_clear_btn.setText(tr("btn_clear"))
        self.vlsm_result.set_translator(tr)
        self.vlsm_result.retranslate()

    # ----- 1. 网络和IP地址计算 -----
    def _build_network_ip_section(self) -> QFrame:
        box, form, self.net_ip_title = _make_section()

        self.net_ip_row = OctetRow(("192", "168", "0", "1"))
        self.net_ip_label = QLabel()
        form.addRow(self.net_ip_label, self.net_ip_row)

        mask_row = QHBoxLayout()
        mask_row.setContentsMargins(0, 0, 0, 0)
        mask_row.setSpacing(4)
        self.net_ip_mask_row = OctetRow(("255", "255", "255", "0"))
        mask_row.addWidget(self.net_ip_mask_row)
        mask_row.addSpacing(10)
        mask_row.addWidget(QLabel("/"))
        self.net_ip_prefix = QSpinBox()
        self.net_ip_prefix.setRange(0, 32)
        self.net_ip_prefix.setValue(24)
        self.net_ip_prefix.setFixedWidth(60)
        mask_row.addWidget(self.net_ip_prefix)
        mask_row.addStretch()
        self.net_ip_mask_label = QLabel()
        form.addRow(self.net_ip_mask_label, mask_row)

        self.net_ip_wildcard_row = OctetRow(("0", "0", "0", "255"))
        self.net_ip_wildcard_label = QLabel()
        form.addRow(self.net_ip_wildcard_label, self.net_ip_wildcard_row)

        self._net_ip_mask_syncing = False
        self.net_ip_prefix.valueChanged.connect(self._sync_net_ip_prefix_to_others)
        self.net_ip_mask_row.connect_changed(self._sync_net_ip_mask_to_others)
        self.net_ip_wildcard_row.connect_changed(self._sync_net_ip_wildcard_to_others)

        self.net_ip_calc_btn = QPushButton()
        self.net_ip_clear_btn = QPushButton()
        self.net_ip_calc_btn.clicked.connect(self._calc_network_ip)
        self.net_ip_clear_btn.clicked.connect(self._clear_network_ip)
        form.addRow(_btn_row(self.net_ip_calc_btn, self.net_ip_clear_btn))

        self.net_ip_result = ResultBox(
            [
                "result_total_count",
                "result_network",
                "result_usable_range",
                "result_broadcast",
            ]
        )
        form.addRow(self.net_ip_result)
        return box

    def _sync_net_ip_prefix_to_others(self, prefix: int):
        if self._net_ip_mask_syncing:
            return
        self._net_ip_mask_syncing = True
        try:
            mask = prefix_to_mask(prefix)
            wildcard = prefix_to_wildcard(prefix)
            self.net_ip_mask_row.set_octets(str(mask).split("."))
            self.net_ip_wildcard_row.set_octets(str(wildcard).split("."))
        finally:
            self._net_ip_mask_syncing = False

    def _sync_net_ip_mask_to_others(self, *_args):
        if self._net_ip_mask_syncing:
            return
        self._net_ip_mask_syncing = True
        try:
            prefix = octets_to_mask(self.net_ip_mask_row.octets())
            self.net_ip_prefix.setValue(prefix)
            wildcard = prefix_to_wildcard(prefix)
            self.net_ip_wildcard_row.set_octets(str(wildcard).split("."))
        except Exception:
            pass
        finally:
            self._net_ip_mask_syncing = False

    def _sync_net_ip_wildcard_to_others(self, *_args):
        if self._net_ip_mask_syncing:
            return
        self._net_ip_mask_syncing = True
        try:
            prefix = octets_to_wildcard_prefix(self.net_ip_wildcard_row.octets())
            self.net_ip_prefix.setValue(prefix)
            mask = prefix_to_mask(prefix)
            self.net_ip_mask_row.set_octets(str(mask).split("."))
        except Exception:
            pass
        finally:
            self._net_ip_mask_syncing = False

    def _format_error(self, exc: Exception) -> str:
        if isinstance(exc, IpCalcError):
            return self._tr(exc.key).format(**exc.params)
        return str(exc)

    def _show_calc_error(self, message):
        text = self._format_error(message) if isinstance(message, Exception) else str(message)
        QMessageBox.critical(self, self._tr("calc_error_title"), text)

    def _calc_network_ip(self):
        try:
            ip = octets_to_ip(self.net_ip_row.octets())
            prefix = self.net_ip_prefix.value()
            info = network_info(ip, prefix)
            self.net_ip_result.set_rows(
                [
                    ("result_total_count", info["total_count"]),
                    ("result_network", info["network"]),
                    ("result_usable_range", f"{info['first_usable']} - {info['last_usable']}"),
                    ("result_broadcast", info["broadcast"]),
                ]
            )
        except Exception as exc:
            self._show_calc_error(exc)

    def _clear_network_ip(self):
        self.net_ip_row.clear(("192", "168", "0", "1"))
        self.net_ip_prefix.setValue(24)
        self.net_ip_mask_row.clear(("255", "255", "255", "0"))
        self.net_ip_wildcard_row.clear(("0", "0", "0", "255"))
        self.net_ip_result.clear()

    # ----- 2. 最小包含地址范围 -----
    def _build_covering_section(self) -> QFrame:
        box, form, self.covering_title = _make_section()

        self.covering_note = QLabel()
        self.covering_note.setWordWrap(True)
        form.addRow(self.covering_note)

        self.covering_input = QTextEdit()
        self.covering_input.setFixedHeight(90)
        self.covering_input.setPlainText(
            "192.168.0.0\n192.168.0.9/29\n192.0.0.1 255.255.255.0"
        )
        form.addRow(self.covering_input)

        self.covering_calc_btn = QPushButton()
        self.covering_clear_btn = QPushButton()
        self.covering_calc_btn.clicked.connect(self._calc_covering)
        self.covering_clear_btn.clicked.connect(self._clear_covering)
        form.addRow(_btn_row(self.covering_calc_btn, self.covering_clear_btn))

        self.covering_result = ResultBox(
            ["result_min_cidr", "result_mask", "result_addr_range", "result_total_count"]
        )
        form.addRow(self.covering_result)
        return box

    def _calc_covering(self):
        try:
            networks = parse_ip_cidr_list(self.covering_input.toPlainText())
            cover = minimal_covering_network(networks)
            self.covering_result.set_rows(
                [
                    ("result_min_cidr", f"{cover.network_address}/{cover.prefixlen}"),
                    ("result_mask", str(cover.netmask)),
                    (
                        "result_addr_range",
                        f"{cover.network_address} - {cover.broadcast_address}",
                    ),
                    ("result_total_count", cover.num_addresses),
                ]
            )
        except Exception as exc:
            self._show_calc_error(exc)

    def _clear_covering(self):
        self.covering_input.setPlainText(
            "192.168.0.0\n192.168.0.9/29\n192.0.0.1 255.255.255.0"
        )
        self.covering_result.clear()

    # ----- 3. 根据主机数划分子网 -----
    def _build_vlsm_section(self) -> QFrame:
        box, form, self.vlsm_title = _make_section()

        self.vlsm_ip_row = OctetRow(("192", "168", "0", "0"))
        self.vlsm_ip_label = QLabel()
        form.addRow(self.vlsm_ip_label, self.vlsm_ip_row)

        mask_row = QHBoxLayout()
        mask_row.setContentsMargins(0, 0, 0, 0)
        mask_row.setSpacing(4)
        self.vlsm_mask_row = OctetRow(("255", "255", "255", "0"))
        mask_row.addWidget(self.vlsm_mask_row)
        mask_row.addSpacing(10)
        mask_row.addWidget(QLabel("/"))
        self.vlsm_prefix = QSpinBox()
        self.vlsm_prefix.setRange(0, 32)
        self.vlsm_prefix.setValue(24)
        self.vlsm_prefix.setFixedWidth(60)
        mask_row.addWidget(self.vlsm_prefix)
        mask_row.addStretch()
        self.vlsm_mask_label = QLabel()
        form.addRow(self.vlsm_mask_label, mask_row)

        self.vlsm_wildcard_row = OctetRow(("0", "0", "0", "255"))
        self.vlsm_wildcard_label = QLabel()
        form.addRow(self.vlsm_wildcard_label, self.vlsm_wildcard_row)

        self._vlsm_mask_syncing = False
        self.vlsm_prefix.valueChanged.connect(self._sync_vlsm_prefix_to_others)
        self.vlsm_mask_row.connect_changed(self._sync_vlsm_mask_to_others)
        self.vlsm_wildcard_row.connect_changed(self._sync_vlsm_wildcard_to_others)

        self.vlsm_note = QLabel()
        self.vlsm_note.setWordWrap(True)
        form.addRow(self.vlsm_note)

        self.vlsm_hosts = QTextEdit()
        self.vlsm_hosts.setFixedHeight(90)
        self.vlsm_hosts.setPlainText("30\n14\n6")
        form.addRow(self.vlsm_hosts)

        self.vlsm_calc_btn = QPushButton()
        self.vlsm_clear_btn = QPushButton()
        self.vlsm_calc_btn.clicked.connect(self._calc_vlsm)
        self.vlsm_clear_btn.clicked.connect(self._clear_vlsm)
        form.addRow(_btn_row(self.vlsm_calc_btn, self.vlsm_clear_btn))

        self.vlsm_result = ResultBox(
            [
                "result_required",
                "result_network",
                "result_mask",
                "result_host_count",
                "result_host_range",
                "result_broadcast",
            ]
        )
        form.addRow(self.vlsm_result)
        return box

    def _sync_vlsm_prefix_to_others(self, prefix: int):
        if self._vlsm_mask_syncing:
            return
        self._vlsm_mask_syncing = True
        try:
            mask = prefix_to_mask(prefix)
            wildcard = prefix_to_wildcard(prefix)
            self.vlsm_mask_row.set_octets(str(mask).split("."))
            self.vlsm_wildcard_row.set_octets(str(wildcard).split("."))
        finally:
            self._vlsm_mask_syncing = False

    def _sync_vlsm_mask_to_others(self, *_args):
        if self._vlsm_mask_syncing:
            return
        self._vlsm_mask_syncing = True
        try:
            prefix = octets_to_mask(self.vlsm_mask_row.octets())
            self.vlsm_prefix.setValue(prefix)
            wildcard = prefix_to_wildcard(prefix)
            self.vlsm_wildcard_row.set_octets(str(wildcard).split("."))
        except Exception:
            pass
        finally:
            self._vlsm_mask_syncing = False

    def _sync_vlsm_wildcard_to_others(self, *_args):
        if self._vlsm_mask_syncing:
            return
        self._vlsm_mask_syncing = True
        try:
            prefix = octets_to_wildcard_prefix(self.vlsm_wildcard_row.octets())
            self.vlsm_prefix.setValue(prefix)
            mask = prefix_to_mask(prefix)
            self.vlsm_mask_row.set_octets(str(mask).split("."))
        except Exception:
            pass
        finally:
            self._vlsm_mask_syncing = False

    def _calc_vlsm(self):
        try:
            ip = octets_to_ip(self.vlsm_ip_row.octets())
            prefix = self.vlsm_prefix.value()
            sizes = []
            cleaned = (
                self.vlsm_hosts.toPlainText()
                .replace("，", ",")
                .replace("；", ";")
                .replace("\r", "\n")
                .replace(";", "\n")
                .replace(",", "\n")
            )
            for line in cleaned.splitlines():
                for part in line.split():
                    part = part.strip()
                    if not part:
                        continue
                    try:
                        sizes.append(int(part))
                    except ValueError as exc:
                        raise IpCalcError("err_invalid_host_count", value=part) from exc
            networks = split_by_host_sizes(ip, sizes, base_prefix=prefix)
            sections = []
            for net in networks:
                sections.append(
                    (
                        ("network_heading", {"index": net["index"]}),
                        [
                            ("result_required", net["required_addresses"]),
                            ("result_network", f"{net['network']}/{net['prefix']}"),
                            ("result_mask", net["netmask"]),
                            ("result_host_count", net["usable_count"]),
                            ("result_host_range", f"{net['first_usable']} - {net['last_usable']}"),
                            ("result_broadcast", net["broadcast"]),
                        ],
                    )
                )
            self.vlsm_result.set_sections(sections)
        except Exception as exc:
            self._show_calc_error(exc)

    def _clear_vlsm(self):
        self.vlsm_ip_row.clear(("192", "168", "0", "0"))
        self.vlsm_prefix.setValue(24)
        self.vlsm_mask_row.clear(("255", "255", "255", "0"))
        self.vlsm_wildcard_row.clear(("0", "0", "0", "255"))
        self.vlsm_hosts.setPlainText("30\n14\n6")
        self.vlsm_result.clear()
