"""批量 Ping 页：PingInfoView 风格的表格实时统计"""
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMessageBox,
)

# 单行 IP 段展开上限（避免误输入过大区间卡死 UI）
_MAX_EXPAND_HOSTS = 1024
# 匹配整段 IPv4，其中某一/多个八位组可为 start-end
_IP_RANGE_TOKEN_RE = re.compile(
    r"^("
    r"(?:\d{1,3}|\d{1,3}-\d{1,3})\."
    r"(?:\d{1,3}|\d{1,3}-\d{1,3})\."
    r"(?:\d{1,3}|\d{1,3}-\d{1,3})\."
    r"(?:\d{1,3}|\d{1,3}-\d{1,3})"
    r")$"
)

try:
    import asyncio
    from icmplib import async_ping
    from icmplib.exceptions import NameLookupError, SocketPermissionError, ICMPLibError

    _ICMPLIB_AVAILABLE = True
except ImportError:  # pragma: no cover
    asyncio = None
    async_ping = None
    NameLookupError = Exception
    SocketPermissionError = Exception
    ICMPLibError = Exception
    _ICMPLIB_AVAILABLE = False


PAGE_TRANSLATIONS = {
    "zh": {
        "host_placeholder": (
            "每行一个 IP / 域名 / IP 段\n"
            "例如：\n"
            "8.8.8.8\n"
            "www.baidu.com\n"
            "192.168.1.1-254\n"
            "192.168.1-254.1\n"
            "192.168.1-254.1-254"
        ),
        "concurrent": "并发数",
        "interval": "间隔(秒)",
        "timeout": "超时(秒)",
        "start": "开始",
        "stop": "停止",
        "reset": "重置计数",
        "col_host": "主机",
        "col_ip": "IP",
        "col_status": "状态",
        "col_ok": "成功",
        "col_fail": "失败",
        "col_loss": "丢包率",
        "col_last": "最新时延",
        "col_min": "最小时延",
        "col_avg": "平均时延",
        "col_max": "最大时延",
        "status_idle": "待测",
        "status_ok": "成功",
        "status_fail": "失败",
        "status_resolve_fail": "解析失败",
        "status_error": "错误",
        "empty_hosts": "请先输入要 Ping 的目标地址",
        "missing_icmplib": "未安装 icmplib，请执行：pip install icmplib",
        "permission_error": "无 ICMP 权限。macOS/Linux 请确认系统允许非特权 ICMP；"
        "Linux 可检查 net.ipv4.ping_group_range。",
        "round_error": "本轮探测失败：{err}",
        "invalid_ip_range": "无效的 IP 段：{token}",
        "expand_too_many": "IP 段展开后超过 {limit} 个地址（当前约 {count}），请缩小范围",
    },
    "en": {
        "host_placeholder": (
            "One IP / hostname / IP range per line\n"
            "Example:\n"
            "8.8.8.8\n"
            "www.baidu.com\n"
            "192.168.1.1-254\n"
            "192.168.1-254.1\n"
            "192.168.1-254.1-254"
        ),
        "concurrent": "Concurrency",
        "interval": "Interval(s)",
        "timeout": "Timeout(s)",
        "start": "Start",
        "stop": "Stop",
        "reset": "Reset Counters",
        "col_host": "Host",
        "col_ip": "IP",
        "col_status": "Status",
        "col_ok": "Succeeded",
        "col_fail": "Failed",
        "col_loss": "Loss %",
        "col_last": "Latest Latency",
        "col_min": "Min Latency",
        "col_avg": "Avg Latency",
        "col_max": "Max Latency",
        "status_idle": "Idle",
        "status_ok": "OK",
        "status_fail": "Failed",
        "status_resolve_fail": "Resolve failed",
        "status_error": "Error",
        "empty_hosts": "Please enter target addresses to ping",
        "missing_icmplib": "icmplib is not installed. Run: pip install icmplib",
        "permission_error": "No ICMP permission. On macOS/Linux ensure unprivileged ICMP is allowed; "
        "on Linux check net.ipv4.ping_group_range.",
        "round_error": "Round failed: {err}",
        "invalid_ip_range": "Invalid IP range: {token}",
        "expand_too_many": "Expanded IP range exceeds {limit} hosts (about {count}). Please narrow it.",
    },
}

COLUMNS = (
    "col_host",
    "col_ip",
    "col_status",
    "col_ok",
    "col_fail",
    "col_loss",
    "col_last",
    "col_min",
    "col_avg",
    "col_max",
)

FAIL_BG = QColor(255, 220, 220)
OK_BG = QColor(0, 0, 0, 0)


@dataclass
class HostStats:
    host: str
    ip: str = ""
    sent: int = 0
    ok: int = 0
    fail: int = 0
    rtts: List[float] = field(default_factory=list)
    last_rtt: Optional[float] = None
    status: str = "idle"  # idle | ok | fail | resolve_fail | error
    last_error: str = ""

    @property
    def loss_percent(self) -> float:
        if self.sent == 0:
            return 0.0
        return 100.0 * self.fail / self.sent

    @property
    def min_rtt(self) -> Optional[float]:
        return min(self.rtts) if self.rtts else None

    @property
    def avg_rtt(self) -> Optional[float]:
        return sum(self.rtts) / len(self.rtts) if self.rtts else None

    @property
    def max_rtt(self) -> Optional[float]:
        return max(self.rtts) if self.rtts else None

    def reset_counters(self) -> None:
        self.sent = 0
        self.ok = 0
        self.fail = 0
        self.rtts.clear()
        self.last_rtt = None
        self.status = "idle"
        self.last_error = ""


@dataclass
class HostRoundResult:
    host: str
    ip: str = ""
    alive: bool = False
    rtt: Optional[float] = None
    resolve_failed: bool = False
    error: str = ""


def _parse_octet_part(part: str) -> List[int]:
    """解析八位组：单个值或 start-end（含端点，自动纠正起止顺序）。"""
    if "-" in part:
        left, right = part.split("-", 1)
        start = int(left)
        end = int(right)
        if not (0 <= start <= 255 and 0 <= end <= 255):
            raise ValueError(part)
        if start > end:
            start, end = end, start
        return list(range(start, end + 1))
    value = int(part)
    if not 0 <= value <= 255:
        raise ValueError(part)
    return [value]


def expand_host_token(token: str) -> List[str]:
    """
    展开主机输入：
    - 普通 IP / 域名原样返回
    - IP 段如 192.168.1.1-254、192.168.1-254.1 按八位组笛卡尔积展开
    """
    if not _IP_RANGE_TOKEN_RE.match(token):
        return [token]
    if "-" not in token:
        return [token]

    parts = token.split(".")
    try:
        octet_lists = [_parse_octet_part(p) for p in parts]
    except ValueError as exc:
        raise ValueError(token) from exc

    count = 1
    for lst in octet_lists:
        count *= len(lst)
        if count > _MAX_EXPAND_HOSTS:
            raise OverflowError(count)

    return [".".join(str(o) for o in combo) for combo in itertools.product(*octet_lists)]


class PingWorker(QThread):
    """在后台线程并发执行一轮 ICMP 探测（逐主机捕获解析失败）。"""

    roundFinished = Signal(list)  # List[HostRoundResult]
    roundFailed = Signal(str)

    def __init__(
        self,
        hosts: List[str],
        timeout: float,
        concurrent: int = 50,
        parent=None,
    ):
        super().__init__(parent)
        self.hosts = list(hosts)
        self.timeout = timeout
        self.concurrent = max(1, int(concurrent))

    def run(self) -> None:
        if not _ICMPLIB_AVAILABLE:
            self.roundFailed.emit("missing_icmplib")
            return
        try:
            results = asyncio.run(self._async_round())
            self.roundFinished.emit(results)
        except SocketPermissionError:
            self.roundFailed.emit("permission_error")
        except ICMPLibError as exc:
            self.roundFailed.emit(str(exc))
        except Exception as exc:  # pragma: no cover
            self.roundFailed.emit(str(exc))

    async def _async_round(self) -> List[HostRoundResult]:
        concurrent = min(self.concurrent, max(1, len(self.hosts)))
        semaphore = asyncio.Semaphore(concurrent)

        async def ping_one(host: str) -> HostRoundResult:
            async with semaphore:
                try:
                    host_obj = await async_ping(
                        host,
                        count=1,
                        interval=0.2,
                        timeout=self.timeout,
                        privileged=False,
                    )
                    rtt = None
                    if host_obj.rtts:
                        rtt = float(host_obj.rtts[-1])
                    elif host_obj.is_alive and host_obj.avg_rtt is not None:
                        rtt = float(host_obj.avg_rtt)
                    return HostRoundResult(
                        host=host,
                        ip=str(host_obj.address or ""),
                        alive=bool(host_obj.is_alive),
                        rtt=rtt,
                    )
                except NameLookupError:
                    return HostRoundResult(
                        host=host, resolve_failed=True, error="resolve_fail"
                    )
                except SocketPermissionError:
                    raise
                except Exception as exc:  # pragma: no cover
                    return HostRoundResult(host=host, error=str(exc))

        return list(await asyncio.gather(*[ping_one(h) for h in self.hosts]))


class BatchPingPage(QWidget):
    """批量 Ping 页（PingInfoView 核心统计）。"""

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self._stats: Dict[str, HostStats] = {}
        self._host_order: List[str] = []
        self._running = False
        self._stopping = False
        self._worker: Optional[PingWorker] = None
        self._schedule_timer = QTimer(self)
        self._schedule_timer.setSingleShot(True)
        self._schedule_timer.timeout.connect(self._start_round)
        self._init_ui()
        self.retranslate_ui()

    def _lang(self) -> str:
        if self.main_window and getattr(self.main_window, "current_lang", None):
            return self.main_window.current_lang
        return "zh"

    def _tr(self, key: str) -> str:
        return PAGE_TRANSLATIONS[self._lang()].get(key, key)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.host_input = QTextEdit()
        self.host_input.setMaximumHeight(120)
        layout.addWidget(self.host_input)

        controls = QHBoxLayout()
        self.concurrent_label = QLabel()
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 500)
        self.concurrent_spin.setValue(50)
        self.interval_label = QLabel()
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(1)
        self.timeout_label = QLabel()
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(0.5, 30.0)
        self.timeout_spin.setSingleStep(0.5)
        self.timeout_spin.setDecimals(1)
        self.timeout_spin.setValue(2.0)

        self.start_btn = QPushButton()
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn = QPushButton()
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        self.reset_btn = QPushButton()
        self.reset_btn.clicked.connect(self._on_reset)

        controls.addWidget(self.concurrent_label)
        controls.addWidget(self.concurrent_spin)
        controls.addWidget(self.interval_label)
        controls.addWidget(self.interval_spin)
        controls.addWidget(self.timeout_label)
        controls.addWidget(self.timeout_spin)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(self.reset_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        # Interactive：可拖动调整列宽；初始等分（不 stretch 最后一列，否则会多出一截）
        # 用户手动拖窄某列后，再打开 StretchLastSection，让最后一列补满右侧留白
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(50)
        header.sectionResized.connect(self._on_section_resized)
        self._equalizing_columns = False
        self._user_resized_columns = False
        # 等分完成前忽略 sectionResized，避免初始化/设表头时被误判为用户拖动
        self._track_column_resize = False
        layout.addWidget(self.table)

        self._set_running_ui(False)

    def retranslate_ui(self) -> None:
        self.host_input.setPlaceholderText(self._tr("host_placeholder"))
        self.concurrent_label.setText(self._tr("concurrent"))
        self.interval_label.setText(self._tr("interval"))
        self.timeout_label.setText(self._tr("timeout"))
        self.start_btn.setText(self._tr("start"))
        self.stop_btn.setText(self._tr("stop"))
        self.reset_btn.setText(self._tr("reset"))
        for col, key in enumerate(COLUMNS):
            item = self.table.horizontalHeaderItem(col)
            if item is None:
                item = QTableWidgetItem()
                self.table.setHorizontalHeaderItem(col, item)
            item.setText(self._tr(key))
        self._refresh_table()

    def _set_running_ui(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.host_input.setReadOnly(running)
        self.concurrent_spin.setEnabled(not running)
        self.interval_spin.setEnabled(not running)
        self.timeout_spin.setEnabled(not running)

    def _parse_hosts(self) -> Tuple[List[str], Optional[str]]:
        """解析输入主机列表；失败时返回 ([], 错误文案)。"""
        seen = set()
        hosts: List[str] = []
        for line in self.host_input.toPlainText().splitlines():
            token = line.strip()
            if not token or token.startswith("#"):
                continue
            try:
                expanded = expand_host_token(token)
            except OverflowError as exc:
                return [], self._tr("expand_too_many").format(
                    limit=_MAX_EXPAND_HOSTS, count=int(exc.args[0])
                )
            except ValueError:
                return [], self._tr("invalid_ip_range").format(token=token)

            for host in expanded:
                if host in seen:
                    continue
                seen.add(host)
                hosts.append(host)
        return hosts, None

    def _on_start(self) -> None:
        if not _ICMPLIB_AVAILABLE:
            QMessageBox.warning(self, "", self._tr("missing_icmplib"))
            return

        hosts, err = self._parse_hosts()
        if err:
            QMessageBox.warning(self, "", err)
            return
        if not hosts:
            QMessageBox.information(self, "", self._tr("empty_hosts"))
            return

        self._stopping = False
        self._running = True
        self._host_order = hosts
        # 保留已有主机计数；新加入的主机初始化
        existing = set(self._stats)
        for host in hosts:
            if host not in self._stats:
                self._stats[host] = HostStats(host=host)
        # 移除本次未包含的主机统计（表格只显示当前列表）
        for host in list(existing):
            if host not in set(hosts):
                del self._stats[host]

        self._set_running_ui(True)
        self._rebuild_table_rows()
        self._start_round()

    def _on_stop(self) -> None:
        self._stopping = True
        self._running = False
        self._schedule_timer.stop()
        self._set_running_ui(False)

    def _on_reset(self) -> None:
        for stats in self._stats.values():
            stats.reset_counters()
        self._refresh_table()

    def _start_round(self) -> None:
        if self._stopping or not self._running:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._worker = PingWorker(
            hosts=self._host_order,
            timeout=float(self.timeout_spin.value()),
            concurrent=int(self.concurrent_spin.value()),
            parent=self,
        )
        self._worker.roundFinished.connect(self._on_round_finished)
        self._worker.roundFailed.connect(self._on_round_failed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self) -> None:
        worker = self.sender()
        if worker is self._worker:
            self._worker = None

    def _on_round_failed(self, err_key: str) -> None:
        if err_key in ("missing_icmplib", "permission_error"):
            msg = self._tr(err_key)
        else:
            msg = self._tr("round_error").format(err=err_key)
        QMessageBox.warning(self, "", msg)
        self._on_stop()

    def _on_round_finished(self, results: list) -> None:
        if self._stopping:
            return

        for item in results:
            if not isinstance(item, HostRoundResult):
                continue
            stats = self._stats.get(item.host)
            if stats is None:
                stats = HostStats(host=item.host)
                self._stats[item.host] = stats

            stats.sent += 1
            if item.ip:
                stats.ip = item.ip

            if item.resolve_failed:
                stats.fail += 1
                stats.status = "resolve_fail"
                stats.last_rtt = None
            elif item.error:
                stats.fail += 1
                stats.status = "error"
                stats.last_error = item.error
                stats.last_rtt = None
            elif item.alive:
                stats.ok += 1
                stats.status = "ok"
                if item.rtt is not None:
                    stats.last_rtt = item.rtt
                    stats.rtts.append(item.rtt)
                else:
                    stats.last_rtt = None
            else:
                stats.fail += 1
                stats.status = "fail"
                stats.last_rtt = None

        self._refresh_table()
        if self._running and not self._stopping:
            interval_ms = int(self.interval_spin.value() * 1000)
            self._schedule_timer.start(interval_ms)

    def _rebuild_table_rows(self) -> None:
        self.table.setRowCount(len(self._host_order))
        for row, host in enumerate(self._host_order):
            for col in range(len(COLUMNS)):
                if self.table.item(row, col) is None:
                    cell = QTableWidgetItem()
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, col, cell)
            self.table.item(row, 0).setText(host)
        self._refresh_table()

    def _fmt_rtt(self, value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"{value:.2f}"

    def _status_text(self, stats: HostStats) -> str:
        key_map = {
            "idle": "status_idle",
            "ok": "status_ok",
            "fail": "status_fail",
            "resolve_fail": "status_resolve_fail",
            "error": "status_error",
        }
        text = self._tr(key_map.get(stats.status, "status_idle"))
        if stats.status == "error" and stats.last_error:
            return f"{text}: {stats.last_error}"
        return text

    def _refresh_table(self) -> None:
        if self.table.rowCount() != len(self._host_order):
            self._rebuild_table_rows()
            return

        for row, host in enumerate(self._host_order):
            stats = self._stats.get(host) or HostStats(host=host)
            values = [
                host,
                stats.ip or "-",
                self._status_text(stats),
                str(stats.ok),
                str(stats.fail),
                f"{stats.loss_percent:.1f}%",
                self._fmt_rtt(stats.last_rtt),
                self._fmt_rtt(stats.min_rtt),
                self._fmt_rtt(stats.avg_rtt),
                self._fmt_rtt(stats.max_rtt),
            ]
            failed_now = stats.status in ("fail", "resolve_fail", "error")
            brush = QBrush(FAIL_BG if failed_now else OK_BG)
            for col, text in enumerate(values):
                item = self.table.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, col, item)
                item.setText(text)
                item.setBackground(brush)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _on_section_resized(self, _logical_index: int, _old: int, _new: int) -> None:
        # 程序自动等分 / 尚未完成首次等分时忽略；用户拖动后保留其设置
        if self._equalizing_columns or not self._track_column_resize:
            return
        self._user_resized_columns = True
        # 用户调窄其他列后，由最后一列自动占满剩余宽度，避免右侧留白
        self.table.horizontalHeader().setStretchLastSection(True)

    def _equalize_column_widths(self) -> None:
        """将所有列设为完全等宽占满表格（初始阶段不 stretch 最后一列）。"""
        width = self.table.viewport().width()
        n = self.table.columnCount()
        if width <= 0 or n <= 0:
            return
        each = width // n
        remainder = width % n
        self._equalizing_columns = True
        try:
            header = self.table.horizontalHeader()
            header.setStretchLastSection(False)
            for i in range(n):
                self.table.setColumnWidth(i, each + (1 if i < remainder else 0))
        finally:
            self._equalizing_columns = False
            # 等分成功后再开始跟踪用户拖动
            self._track_column_resize = True

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._user_resized_columns:
            # 延后到布局完成后再等分，避免 width 仍为 0
            QTimer.singleShot(0, self._equalize_column_widths)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not self._user_resized_columns:
            self._equalize_column_widths()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._on_stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(2000)
        super().closeEvent(event)
