"""网卡信息页：查看本机网卡 IPv4 配置（含自动/手动来源），并支持修改配置"""
from __future__ import annotations

import base64
import json
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QWidget,
    QApplication,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QComboBox,
    QInputDialog,
    QMessageBox,
)

PAGE_TRANSLATIONS = {
    "zh": {
        "label_interface": "网卡名称",
        "label_saved_profile": "已保存配置模板",
        "profile_none": "请选择已保存配置模板",
        "btn_save_profile": "保存当前配置模板",
        "btn_delete_profile": "删除当前配置模板",
        "profile_name_title": "保存配置模板",
        "profile_name_prompt": "请输入该套配置模板的名称",
        "profile_delete_title": "确认删除配置模板",
        "profile_delete_prompt": "确定删除配置模板「{name}」吗？",
        "profile_name_exists": "该配置模板名称已存在，请使用其他名称",
        "profile_empty_fields": "请先填写要保存的 IP/DNS 配置",
        "label_ip_mode": "IP 获取方式",
        "label_dns_mode": "DNS 获取方式",
        "label_ip": "IP 地址",
        "label_mask": "子网掩码",
        "label_gateway": "网关",
        "label_dns": "DNS 服务器",
        "btn_refresh": "刷新",
        "btn_apply": "应用配置",
        "group_config": "修改配置",
        "mode_dhcp": "自动获取 (DHCP)",
        "mode_static": "手动设置",
        "mode_none": "未配置",
        "mode_unknown": "未知",
        "not_configured": "未配置",
        "unknown_interface": "未知网卡",
        "dns_placeholder": "多个 DNS 用逗号分隔",
        "hint_select": "选择网卡以查看当前网络配置",
        "hint_loading": "正在读取网卡配置...",
        "hint_loaded": "当前配置已载入。调整需要修改的项目后点击「应用配置」写入",
        "hint_empty": "未检测到可用的 IPv4 网卡",
        "hint_error": "读取网卡配置失败：{err}",
        "err_no_interface": "请先选择网卡",
        "err_invalid_ip": "无效的 IP 地址：{value}",
        "err_invalid_mask": "无效的子网掩码：{value}",
        "err_invalid_gateway": "无效的网关地址：{value}",
        "err_invalid_dns": "无效的 DNS 服务器：{value}",
        "err_dns_required": "手动设置 DNS 时请至少填写一个 DNS 服务器",
        "err_not_windows": "当前系统暂不支持写入网卡配置",
        "err_admin": "修改网络配置需要管理员权限，请以管理员身份重新运行本程序",
        "err_root_required": "需要 root 权限：请以 sudo 启动本程序，或安装 pkexec 后重试",
        "err_no_connection": "未找到网卡「{name}」对应的 NetworkManager 连接，无法写入配置",
        "err_no_service": "未找到网卡「{name}」对应的 macOS 网络服务，无法写入配置",
        "err_write": "写入配置失败（退出码 {code}）\n\n{output}",
        "elevate_title": "需要管理员权限",
        "elevate_text": "修改网络配置需要管理员权限。是否以管理员身份重新启动程序（将弹出 UAC 提示）？",
        "elevate_failed": "未能启动管理员进程，可能已取消 UAC 授权",
        "hint_applying": "正在应用配置...",
        "confirm_title": "确认修改",
        "confirm_text": "即将修改网卡「{name}」的配置：\n\n{summary}\n\n应用过程中网络可能短暂中断，是否继续？",
        "success_title": "配置已应用",
        "success_text": "网卡「{name}」的配置已提交。若信息未立即刷新，请稍后点击「刷新」",
    },
    "en": {
        "label_interface": "Interface",
        "label_saved_profile": "Saved Configuration Template",
        "profile_none": "Select a saved configuration template",
        "btn_save_profile": "Save Current Configuration Template",
        "btn_delete_profile": "Delete Current Configuration Template",
        "profile_name_title": "Save Current Configuration Template",
        "profile_name_prompt": "Enter a name for this configuration template",
        "profile_delete_title": "Confirm Delete Template",
        "profile_delete_prompt": "Delete configuration template \"{name}\"?",
        "profile_name_exists": "That configuration template name already exists. Please use another name",
        "profile_empty_fields": "Enter the IP/DNS settings to save first",
        "label_ip_mode": "IP Assignment",
        "label_dns_mode": "DNS Assignment",
        "label_ip": "IP Address",
        "label_mask": "Subnet Mask",
        "label_gateway": "Gateway",
        "label_dns": "DNS Servers",
        "btn_refresh": "Refresh",
        "btn_apply": "Apply",
        "group_config": "Modify Configuration",
        "mode_dhcp": "Automatic (DHCP)",
        "mode_static": "Manual",
        "mode_none": "Not configured",
        "mode_unknown": "Unknown",
        "not_configured": "Not configured",
        "unknown_interface": "Unknown interface",
        "dns_placeholder": "Separate multiple DNS servers with commas",
        "hint_select": "Select an interface to view its current network configuration",
        "hint_loading": "Reading interface configuration...",
        "hint_loaded": "Current settings are loaded. Adjust the fields you want to change and click Apply",
        "hint_empty": "No IPv4 interfaces detected",
        "hint_error": "Failed to read interface configuration: {err}",
        "err_no_interface": "Please select an interface first",
        "err_invalid_ip": "Invalid IP address: {value}",
        "err_invalid_mask": "Invalid subnet mask: {value}",
        "err_invalid_gateway": "Invalid gateway address: {value}",
        "err_invalid_dns": "Invalid DNS server: {value}",
        "err_dns_required": "Enter at least one DNS server when using manual DNS",
        "err_not_windows": "Writing interface settings is not supported on this system",
        "err_admin": "Changing network settings requires administrator privileges. Please restart this program as administrator",
        "err_root_required": "Root privileges are required. Run this program with sudo, or install pkexec and retry",
        "err_no_connection": "No NetworkManager connection found for \"{name}\"; cannot apply settings",
        "err_no_service": "No macOS network service found for \"{name}\"; cannot apply settings",
        "err_write": "Failed to write configuration (exit code {code})\n\n{output}",
        "elevate_title": "Administrator Required",
        "elevate_text": "Changing network settings requires administrator privileges. Restart the program as administrator (a UAC prompt will appear)?",
        "elevate_failed": "Failed to start the elevated process. The UAC authorization may have been cancelled",
        "hint_applying": "Applying configuration...",
        "confirm_title": "Confirm Changes",
        "confirm_text": "About to change the configuration of \"{name}\":\n\n{summary}\n\nThe network may briefly drop during the change. Continue?",
        "success_title": "Configuration Applied",
        "success_text": "Configuration for \"{name}\" has been submitted. If the info is not updated yet, click Refresh later",
    },
}

_MODE_KEYS = {
    "dhcp": "mode_dhcp",
    "static": "mode_static",
    "none": "mode_none",
    "unknown": "mode_unknown",
}

_CREATE_NO_WINDOW = 0x08000000


class ConfigError(ValueError):
    """携带翻译键的输入校验错误"""

    def __init__(self, key: str, **params):
        self.key = key
        self.params = params
        super().__init__(key)


class _InterfaceLoadWorker(QObject):
    loaded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, page):
        super().__init__()
        self.page = page

    @Slot()
    def run(self):
        try:
            if platform.system() == "Windows":
                interfaces = self.page._windows_interfaces()
            else:
                interfaces = self.page._unix_interfaces()
        except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
            self.failed.emit(str(exc))
        else:
            self.loaded.emit(interfaces)
        finally:
            self.finished.emit()


class NetworkIpSetupPage(QWidget):
    """查看并修改本机网卡 IPv4 地址、掩码、网关和 DNS 配置"""

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self._interfaces = []
        self._loaded = False
        self._state = "idle"
        self._last_error = ""
        self._elevated_pending = None
        self._elevated_iface = ""
        self._load_thread = None
        self._load_worker = None
        self._init_ui()
        self.retranslate_ui()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            # 延迟到界面完成首帧绘制后再执行 PowerShell，避免窗口卡在启动阶段
            self._state = "loading"
            self._set_controls_enabled(False)
            self.hint_label.setText(self._tr("hint_loading"))
            QTimer.singleShot(0, self._load_interfaces)

    @staticmethod
    def _profile_file_path() -> Path:
        if sys.platform == "win32":
            base_dir = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        elif sys.platform == "darwin":
            base_dir = str(Path.home() / "Library" / "Application Support")
        else:
            base_dir = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        return Path(base_dir) / "network_engineer_tools" / "ip_profiles.json"

    @staticmethod
    def _parse_profiles(raw):
        try:
            profiles = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, json.JSONDecodeError):
            profiles = {}
        return profiles if isinstance(profiles, dict) else {}

    def _load_profiles(self):
        profile_path = self._profile_file_path()
        try:
            with profile_path.open("r", encoding="utf-8") as profile_file:
                profiles = self._parse_profiles(profile_file.read())
        except (OSError, json.JSONDecodeError):
            profiles = {}
        self._profiles = profiles
        self._refresh_profile_combo()

    def _save_profiles(self, profiles=None):
        if profiles is None:
            profiles = self._profiles
        profile_path = self._profile_file_path()
        try:
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            with profile_path.open("w", encoding="utf-8") as profile_file:
                json.dump(profiles, profile_file, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _refresh_profile_combo(self):
        selected = self.saved_profile_combo.currentData() if hasattr(self, "saved_profile_combo") else None
        self.saved_profile_combo.blockSignals(True)
        self.saved_profile_combo.clear()
        self.saved_profile_combo.addItem(self._tr("profile_none"), None)
        for name in sorted(self._profiles, key=str.casefold):
            self.saved_profile_combo.addItem(name, name)
        index = self.saved_profile_combo.findData(selected) if selected else 0
        self.saved_profile_combo.setCurrentIndex(max(index, 0))
        self.saved_profile_combo.blockSignals(False)
        self.delete_profile_btn.setEnabled(bool(self.saved_profile_combo.currentData()))

    def _on_profile_selected(self, _index=None):
        self.delete_profile_btn.setEnabled(bool(self.saved_profile_combo.currentData()))
        name = self.saved_profile_combo.currentData()
        profile = self._profiles.get(name) if name else None
        if not profile:
            return
        self.config_ip_mode_combo.setCurrentIndex(
            0 if profile.get("ip_mode") == "dhcp" else 1
        )
        self.config_dns_mode_combo.setCurrentIndex(
            0 if profile.get("dns_mode") == "dhcp" else 1
        )
        self.cfg_ip_edit.setText(profile.get("ip", ""))
        self.cfg_mask_edit.setText(profile.get("mask", ""))
        self.cfg_gateway_edit.setText(profile.get("gateway", ""))
        self.cfg_dns_edit.setText(profile.get("dns", ""))
        self._update_config_state()

    def _save_profile(self):
        current_name = self.saved_profile_combo.currentData()
        name, accepted = QInputDialog.getText(
            self,
            self._tr("profile_name_title"),
            self._tr("profile_name_prompt"),
            QLineEdit.EchoMode.Normal,
            current_name or "",
        )
        name = name.strip()
        if not accepted or not name:
            return
        if name in self._profiles and name != current_name:
            QMessageBox.warning(self, "", self._tr("profile_name_exists"))
            return
        profile = {
            "ip_mode": self.config_ip_mode_combo.currentData(),
            "ip": self.cfg_ip_edit.text().strip(),
            "mask": self.cfg_mask_edit.text().strip(),
            "gateway": self.cfg_gateway_edit.text().strip(),
            "dns_mode": self.config_dns_mode_combo.currentData(),
            "dns": self.cfg_dns_edit.text().strip(),
        }
        if profile["ip_mode"] == "static" and not profile["ip"]:
            QMessageBox.warning(self, "", self._tr("profile_empty_fields"))
            return
        if profile["dns_mode"] == "static" and not profile["dns"]:
            QMessageBox.warning(self, "", self._tr("profile_empty_fields"))
            return
        if current_name and current_name != name:
            self._profiles.pop(current_name, None)
        self._profiles[name] = profile
        self._save_profiles()
        self._refresh_profile_combo()
        self.saved_profile_combo.setCurrentIndex(self.saved_profile_combo.findData(name))

    def _delete_profile(self):
        name = self.saved_profile_combo.currentData()
        if not name:
            return
        answer = QMessageBox.question(
            self,
            self._tr("profile_delete_title"),
            self._tr("profile_delete_prompt").format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._profiles.pop(name, None)
        self._save_profiles()
        self._refresh_profile_combo()
        if self.interface_combo.currentData():
            self._show_selected_interface()
        else:
            self._clear_view_fields()

    def _lang(self) -> str:
        if self.main_window and getattr(self.main_window, "current_lang", None):
            return self.main_window.current_lang
        return "zh"

    def _tr(self, key: str) -> str:
        return PAGE_TRANSLATIONS[self._lang()].get(key, key)

    def _mode_text(self, mode: str) -> str:
        return self._tr(_MODE_KEYS.get(mode, "mode_unknown"))

    # ----- 界面 -----

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        self.interface_combo = QComboBox()
        self.interface_combo.currentIndexChanged.connect(self._on_interface_changed)
        self.interface_label = QLabel()
        form.addRow(self.interface_label, self.interface_combo)

        self.saved_profile_label = QLabel()
        self.saved_profile_combo = QComboBox()
        self.saved_profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        form.addRow(self.saved_profile_label, self.saved_profile_combo)

        self.config_ip_mode_label = QLabel()
        self.config_ip_mode_combo = QComboBox()
        self.config_ip_mode_combo.addItem("", "dhcp")
        self.config_ip_mode_combo.addItem("", "static")
        self.config_ip_mode_combo.currentIndexChanged.connect(self._update_config_state)
        form.addRow(self.config_ip_mode_label, self.config_ip_mode_combo)

        self.cfg_ip_edit = QLineEdit()
        self.cfg_mask_edit = QLineEdit()
        self.cfg_gateway_edit = QLineEdit()
        self.config_ip_label = QLabel()
        self.config_mask_label = QLabel()
        self.config_gateway_label = QLabel()
        form.addRow(self.config_ip_label, self.cfg_ip_edit)
        form.addRow(self.config_mask_label, self.cfg_mask_edit)
        form.addRow(self.config_gateway_label, self.cfg_gateway_edit)

        self.config_dns_mode_label = QLabel()
        self.config_dns_mode_combo = QComboBox()
        self.config_dns_mode_combo.addItem("", "dhcp")
        self.config_dns_mode_combo.addItem("", "static")
        self.config_dns_mode_combo.currentIndexChanged.connect(self._update_config_state)
        form.addRow(self.config_dns_mode_label, self.config_dns_mode_combo)

        self.cfg_dns_edit = QLineEdit()
        self.config_dns_label = QLabel()
        form.addRow(self.config_dns_label, self.cfg_dns_edit)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.delete_profile_btn = QPushButton()
        self.delete_profile_btn.clicked.connect(self._delete_profile)
        actions.addWidget(self.delete_profile_btn)
        self.save_profile_btn = QPushButton()
        self.save_profile_btn.clicked.connect(self._save_profile)
        actions.addWidget(self.save_profile_btn)
        actions.addStretch()
        self.refresh_btn = QPushButton()
        self.refresh_btn.clicked.connect(lambda: self._load_interfaces())
        actions.addWidget(self.refresh_btn)
        self.apply_btn = QPushButton()
        self.apply_btn.clicked.connect(self._apply_config)
        actions.addWidget(self.apply_btn)
        layout.addLayout(actions)

        self._load_profiles()

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.hint_label)
        layout.addStretch()

    def retranslate_ui(self) -> None:
        tr = self._tr
        self.interface_label.setText(tr("label_interface"))
        self.saved_profile_label.setText(tr("label_saved_profile"))
        if self.saved_profile_combo.count():
            self.saved_profile_combo.setItemText(0, tr("profile_none"))
        self.delete_profile_btn.setText(tr("btn_delete_profile"))
        self.save_profile_btn.setText(tr("btn_save_profile"))
        self.config_ip_mode_label.setText(tr("label_ip_mode"))
        self.config_ip_label.setText(tr("label_ip"))
        self.config_mask_label.setText(tr("label_mask"))
        self.config_gateway_label.setText(tr("label_gateway"))
        self.config_dns_mode_label.setText(tr("label_dns_mode"))
        self.config_dns_label.setText(tr("label_dns"))
        self.cfg_dns_edit.setPlaceholderText(tr("dns_placeholder"))
        self.refresh_btn.setText(tr("btn_refresh"))
        self.apply_btn.setText(tr("btn_apply"))
        self.config_ip_mode_combo.setItemText(0, tr("mode_dhcp"))
        self.config_ip_mode_combo.setItemText(1, tr("mode_static"))
        self.config_dns_mode_combo.setItemText(0, tr("mode_dhcp"))
        self.config_dns_mode_combo.setItemText(1, tr("mode_static"))

        if self._state == "loaded" and self.interface_combo.currentData():
            self._show_selected_interface()
        elif self._state == "empty":
            self.hint_label.setText(tr("hint_empty"))
        elif self._state == "error":
            self.hint_label.setText(tr("hint_error").format(err=self._last_error))
        elif self._state == "loading":
            self.hint_label.setText(tr("hint_loading"))
        else:
            self.hint_label.setText(tr("hint_select"))

    # ----- 数据采集 -----

    @staticmethod
    def _prefix_to_mask(prefix) -> str:
        prefix = max(0, min(32, int(prefix)))
        return str(IPv4Address((0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF))

    @staticmethod
    def _split_values(value) -> list:
        if value is None:
            return []
        parts = value if isinstance(value, list) else str(value).split(",")
        return [str(part).strip() for part in parts if str(part).strip()]

    @staticmethod
    def _decode_console(data: bytes) -> str:
        if not data:
            return ""
        for encoding in ("utf-8", "gbk", "mbcs", "latin-1"):
            try:
                return data.decode(encoding).strip()
            except (UnicodeDecodeError, LookupError):
                continue
        return data.decode("utf-8", errors="replace").strip()

    @staticmethod
    def _run_powershell(
        script: str, timeout: int = 30, check: bool = False, env=None
    ) -> subprocess.CompletedProcess:
        # -EncodedCommand 避免引号/中文网卡名被外部 shell 二次解析
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        kwargs = {}
        if platform.system() == "Windows":
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True, timeout=timeout, check=check, env=env, **kwargs,
        )

    def _windows_interfaces(self):
        # ConvertTo-Json 的结果先写入 UTF-8 临时文件，避免重定向时控制台代码页损坏中文网卡名
        script = (
            "$ErrorActionPreference='Stop'; "
            "$guidByIndex=@{}; "
            "Get-NetAdapter -IncludeHidden | ForEach-Object { $guidByIndex[[int]$_.ifIndex]=$_.InterfaceGuid }; "
            "$dhcpByIndex=@{}; "
            "Get-NetIPInterface -AddressFamily IPv4 | ForEach-Object { "
            "$dhcpByIndex[[int]$_.InterfaceIndex]=($_.Dhcp -eq 'Enabled') }; "
            "$dnsByIndex=@{}; "
            "Get-DnsClientServerAddress -AddressFamily IPv4 | ForEach-Object { "
            "$dnsByIndex[[int]$_.InterfaceIndex]=@($_.ServerAddresses) }; "
            "$items = @(foreach ($cfg in Get-NetIPConfiguration) { "
            "$idx=[int]$cfg.InterfaceIndex; "
            "$addrs=@(); "
            "foreach ($a in @($cfg.IPv4Address) | Where-Object { "
            "$_.IPAddress -notlike '169.254.*' -and $_.IPAddress -notlike '127.*' }) { if ($a) { "
            "$addrs += [pscustomobject]@{IPAddress=$a.IPAddress; PrefixLength=$a.PrefixLength} } }; "
            "$gw=@($cfg.IPv4DefaultGateway | ForEach-Object { $_.NextHop } | Where-Object { $_ }); "
            "$staticDns=@(); "
            "$guid=$guidByIndex[$idx]; "
            "if ($guid) { "
            "$regPath=\"HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces\\$guid\"; "
            "if (Test-Path $regPath) { "
            "$p=Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue; "
            "if ($p.NameServer) { $staticDns=@($p.NameServer -split '[,\\s]+' | Where-Object { $_ }) } } }; "
            "$servers=@($dnsByIndex[$idx] | Where-Object { $_ }); "
            "$dnsMode=if ($staticDns.Count -gt 0) { 'Static' } "
            "elseif ($servers.Count -gt 0) { 'Dhcp' } else { 'None' }; "
            "$ipMode=if ($addrs.Count -eq 0) { 'None' } "
            "elseif ($dhcpByIndex.ContainsKey($idx) -and $dhcpByIndex[$idx]) { 'Dhcp' } else { 'Static' }; "
            "[pscustomobject]@{InterfaceAlias=$cfg.InterfaceAlias; InterfaceIndex=$idx; "
            "IPv4Address=$addrs; Gateway=$gw; DNSServers=$servers; IPMode=$ipMode; DNSMode=$dnsMode} }); "
            "$json=ConvertTo-Json -InputObject $items -Depth 5 -Compress; "
            "[System.IO.File]::WriteAllText($env:NET_TOOL_INFO_FILE, $json, [System.Text.Encoding]::UTF8)"
        )
        fd, info_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        env = dict(os.environ, NET_TOOL_INFO_FILE=info_path)
        try:
            self._run_powershell(script, timeout=30, env=env, check=True)
            with open(info_path, encoding="utf-8-sig") as info_file:
                raw = info_file.read().strip() or "[]"
        finally:
            try:
                os.remove(info_path)
            except OSError:
                pass

        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]

        interfaces = []
        for item in data:
            addresses = item.get("IPv4Address") or []
            if isinstance(addresses, dict):
                addresses = [addresses]
            ips, masks = [], []
            for addr in addresses:
                if addr.get("IPAddress"):
                    ips.append(str(addr["IPAddress"]).strip())
                if addr.get("PrefixLength") is not None:
                    masks.append(self._prefix_to_mask(addr["PrefixLength"]))
            interfaces.append({
                "name": item.get("InterfaceAlias") or self._tr("unknown_interface"),
                "index": item.get("InterfaceIndex"),
                "ips": ips,
                "masks": masks,
                "ip": ", ".join(ips),
                "mask": ", ".join(masks),
                "gateway": ", ".join(self._split_values(item.get("Gateway"))),
                "dns": ", ".join(self._split_values(item.get("DNSServers"))),
                "ip_mode": str(item.get("IPMode") or "unknown").lower(),
                "dns_mode": str(item.get("DNSMode") or "unknown").lower(),
            })
        return interfaces

    @classmethod
    def _unix_interfaces(cls):
        if platform.system() == "Darwin":
            return cls._macos_interfaces()
        return cls._linux_interfaces()

    @staticmethod
    def _ioctl_address(name: str):
        import fcntl
        import struct

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            request = struct.pack("256s", name.encode()[:15])
            ip = socket.inet_ntoa(fcntl.ioctl(sock.fileno(), 0x8915, request)[20:24])
            mask = socket.inet_ntoa(fcntl.ioctl(sock.fileno(), 0x891B, request)[20:24])
            return ip, mask
        except OSError:
            return None
        finally:
            sock.close()

    @staticmethod
    def _resolv_dns() -> list:
        try:
            with open("/etc/resolv.conf", encoding="utf-8") as resolv:
                return [line.split()[1] for line in resolv if line.strip().startswith("nameserver ")]
        except OSError:
            return []

    @classmethod
    def _linux_interfaces(cls):
        import struct

        gateways = {}
        try:
            # 默认路由即 0.0.0.0/0，Destination 为 00000000
            with open("/proc/net/route", encoding="ascii") as routes:
                next(routes, None)
                for row in routes:
                    columns = row.split()
                    if len(columns) > 3 and columns[1] == "00000000":
                        gateways[columns[0]] = socket.inet_ntoa(
                            struct.pack("<I", int(columns[2], 16))
                        )
        except OSError:
            pass

        resolv_dns = cls._resolv_dns()
        conn_by_dev = {}
        if shutil.which("nmcli"):
            try:
                out = subprocess.run(
                    ["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
                    capture_output=True, text=True, timeout=10,
                ).stdout
                for line in out.splitlines():
                    if ":" not in line:
                        continue
                    conn, device = line.split(":", 1)
                    conn_by_dev[device.strip()] = conn.replace("\\:", ":")
            except (OSError, subprocess.SubprocessError):
                pass

        interfaces = []
        for _, name in socket.if_nameindex():
            address = cls._ioctl_address(name)
            if not address:
                continue
            ip, mask = address
            conn = conn_by_dev.get(name, "")
            ip_mode, dns_mode = "unknown", "unknown"
            dns_servers = []
            if conn:
                method, ignore_auto, dns_conf = cls._nmcli_ipv4_settings(conn)
                if method == "manual":
                    ip_mode = "static"
                elif method == "auto":
                    ip_mode = "dhcp"
                dns_servers = [server for server in re.split(r"[,\s]+", dns_conf) if server]
                if ignore_auto == "yes" and dns_servers:
                    dns_mode = "static"
                elif method == "auto" or ignore_auto == "no":
                    dns_mode = "dhcp"
                elif dns_servers:
                    dns_mode = "static"
                else:
                    dns_mode = "none"
            interfaces.append({
                "name": name,
                "index": None,
                "connection": conn,
                "ips": [ip],
                "masks": [mask],
                "ip": ip,
                "mask": mask,
                "gateway": gateways.get(name, ""),
                "dns": ", ".join(dns_servers or resolv_dns),
                "ip_mode": ip_mode,
                "dns_mode": dns_mode,
            })
        return interfaces

    @staticmethod
    def _nmcli_ipv4_settings(conn: str):
        try:
            out = subprocess.run(
                ["nmcli", "-t", "-f", "ipv4.method,ipv4.ignore-auto-dns,ipv4.dns",
                 "connection", "show", conn],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return "", "", ""
        parts = out.split(":", 2)
        while len(parts) < 3:
            parts.append("")
        return parts[0].strip(), parts[1].strip(), parts[2].strip()

    @classmethod
    def _macos_interfaces(cls):
        resolv_dns = cls._resolv_dns()
        services = {}
        try:
            out = subprocess.run(
                ["networksetup", "-listnetworkserviceorder"],
                capture_output=True, text=True, timeout=10,
            ).stdout
            pending = None
            for line in out.splitlines():
                match = re.match(r"^\(\d+\)\s+(.*)$", line.strip())
                if match:
                    pending = match.group(1).strip()
                    continue
                match = re.search(r"Device:\s*([^)]+)\)", line)
                if match and pending:
                    services[match.group(1).strip()] = pending
                    pending = None
        except (OSError, subprocess.SubprocessError):
            pass

        default_by_iface = {}
        try:
            current_iface = None
            out = subprocess.run(
                ["route", "-n", "get", "default"], capture_output=True, text=True, timeout=10
            ).stdout
            for line in out.splitlines():
                text = line.strip()
                if text.startswith("interface:"):
                    current_iface = text.split(":", 1)[1].strip()
                elif text.startswith("gateway:") and current_iface:
                    default_by_iface[current_iface] = text.split(":", 1)[1].strip()
        except (OSError, subprocess.SubprocessError):
            pass

        interfaces = []
        for _, name in socket.if_nameindex():
            address = cls._ioctl_address(name)
            if not address:
                continue
            ip, mask = address
            service = services.get(name, "")
            gateway = ""
            ip_mode, dns_mode = "unknown", "unknown"
            dns_servers = []
            if service:
                gateway, ip_mode = cls._macos_service_info(service)
                dns_servers, dns_mode = cls._macos_dns_info(service, name)
            if not gateway:
                gateway = default_by_iface.get(name, "")
            interfaces.append({
                "name": name,
                "index": None,
                "service": service,
                "ips": [ip],
                "masks": [mask],
                "ip": ip,
                "mask": mask,
                "gateway": gateway,
                "dns": ", ".join(dns_servers or resolv_dns),
                "ip_mode": ip_mode,
                "dns_mode": dns_mode,
            })
        return interfaces

    @staticmethod
    def _macos_service_info(service: str):
        gateway, ip_mode = "", "unknown"
        try:
            out = subprocess.run(
                ["networksetup", "-getinfo", service], capture_output=True, text=True, timeout=10
            ).stdout
            for line in out.splitlines():
                text = line.strip()
                low = text.lower()
                if low.startswith("manual configuration"):
                    ip_mode = "static"
                elif low.startswith("dhcp configuration"):
                    ip_mode = "dhcp"
                elif low.startswith("router:"):
                    gateway = text.split(":", 1)[1].strip()
        except (OSError, subprocess.SubprocessError):
            pass
        return gateway, ip_mode

    @staticmethod
    def _macos_dns_info(service: str, device: str):
        try:
            out = subprocess.run(
                ["networksetup", "-getdnsservers", service], capture_output=True, text=True, timeout=10
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return [], "unknown"
        servers = [
            line.strip()
            for line in out.splitlines()
            if line.strip() and "aren't any" not in line.lower()
            and "dns servers" not in line.lower()
        ]
        if servers:
            return servers, "static"
        try:
            packet = subprocess.run(
                ["ipconfig", "getpacket", device], capture_output=True, text=True, timeout=10
            ).stdout
        except (OSError, subprocess.SubprocessError):
            packet = ""
        if "domain_name_server" in packet:
            match = re.search(r"domain_name_server[^{]*\{([^}]*)\}", packet)
            dns = re.findall(r"\d+\.\d+\.\d+\.\d+", match.group(1)) if match else []
            return dns, "dhcp"
        return [], "none"

    # ----- 界面更新 -----

    def _set_controls_enabled(self, enabled: bool) -> None:
        controls = (
            self.interface_combo,
            self.saved_profile_combo,
            self.config_ip_mode_combo,
            self.cfg_ip_edit,
            self.cfg_mask_edit,
            self.cfg_gateway_edit,
            self.config_dns_mode_combo,
            self.cfg_dns_edit,
            self.delete_profile_btn,
            self.save_profile_btn,
            self.refresh_btn,
            self.apply_btn,
        )
        for control in controls:
            control.setEnabled(enabled)
        if enabled:
            self._update_config_state()

    def _load_interfaces(self, select_name=None):
        if self._load_thread is not None and self._load_thread.isRunning():
            return
        if select_name is None and self.interface_combo.currentData():
            select_name = self.interface_combo.currentData()["name"]

        self._pending_select_name = select_name
        self._state = "loading"
        self._set_controls_enabled(False)
        self.hint_label.setText(self._tr("hint_loading"))

        self._load_thread = QThread(self)
        self._load_worker = _InterfaceLoadWorker(self)
        self._load_worker.moveToThread(self._load_thread)
        self._load_thread.started.connect(self._load_worker.run)
        self._load_worker.loaded.connect(self._on_interfaces_loaded)
        self._load_worker.failed.connect(self._on_interfaces_load_failed)
        self._load_worker.finished.connect(self._load_thread.quit)
        self._load_worker.finished.connect(self._load_worker.deleteLater)
        self._load_thread.finished.connect(self._on_load_thread_finished)
        self._load_thread.finished.connect(self._load_thread.deleteLater)
        self._load_thread.start()

    @Slot(object)
    def _on_interfaces_loaded(self, interfaces):
        select_name = getattr(self, "_pending_select_name", None)
        self._interfaces = interfaces
        self.interface_combo.blockSignals(True)
        self.interface_combo.clear()
        for item in interfaces:
            self.interface_combo.addItem(item["name"], item)
        if select_name:
            target = self.interface_combo.findText(select_name)
            if target >= 0:
                self.interface_combo.setCurrentIndex(target)
        self.interface_combo.blockSignals(False)

        if interfaces:
            if self.interface_combo.currentIndex() < 0:
                self.interface_combo.setCurrentIndex(0)
            self._show_selected_interface()
        else:
            self._clear_view_fields()
            self._state = "empty"
            self.hint_label.setText(self._tr("hint_empty"))
        self._maybe_apply_pending()

    @Slot(str)
    def _on_interfaces_load_failed(self, error):
        self._interfaces = []
        self.interface_combo.clear()
        self._clear_view_fields()
        self._state = "error"
        self._last_error = error
        self.hint_label.setText(self._tr("hint_error").format(err=error))

    @Slot()
    def _on_load_thread_finished(self):
        self._set_controls_enabled(True)
        self._load_worker = None
        self._load_thread = None

    def _clear_view_fields(self):
        self.cfg_ip_edit.clear()
        self.cfg_mask_edit.clear()
        self.cfg_gateway_edit.clear()
        self.cfg_dns_edit.clear()
        self.config_ip_mode_combo.setCurrentIndex(0)
        self.config_dns_mode_combo.setCurrentIndex(0)
        self._update_config_state()

    def _on_interface_changed(self, _index=None):
        self.saved_profile_combo.blockSignals(True)
        self.saved_profile_combo.setCurrentIndex(0)
        self.saved_profile_combo.blockSignals(False)
        self.delete_profile_btn.setEnabled(False)
        self._show_selected_interface()

    def _show_selected_interface(self, _index=None):
        item = self.interface_combo.currentData()
        if not item:
            return
        self._state = "loaded"
        self._fill_config_from(item)
        self.hint_label.setText(self._tr("hint_loaded"))

    def _fill_config_from(self, item: dict) -> None:
        self.config_ip_mode_combo.setCurrentIndex(0 if item["ip_mode"] != "static" else 1)
        self.config_dns_mode_combo.setCurrentIndex(0 if item["dns_mode"] != "static" else 1)
        ips = item.get("ips") or []
        masks = item.get("masks") or []
        self.cfg_ip_edit.setText(ips[0] if ips else "")
        self.cfg_mask_edit.setText(masks[0] if masks else "")
        self.cfg_gateway_edit.setText(item["gateway"])
        self.cfg_dns_edit.setText(item["dns"])
        self._update_config_state()

    def _update_config_state(self, _index=None) -> None:
        ip_static = self.config_ip_mode_combo.currentData() == "static"
        dns_static = self.config_dns_mode_combo.currentData() == "static"
        for widget in (self.cfg_ip_edit, self.cfg_mask_edit, self.cfg_gateway_edit):
            widget.setEnabled(ip_static)
        self.cfg_dns_edit.setEnabled(dns_static)

    # ----- 写入配置 -----

    @staticmethod
    def _is_admin() -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def _show_error(self, key: str, **params) -> None:
        QMessageBox.warning(self, "", self._tr(key).format(**params))

    def _validate_ip_config(self):
        ip = self.cfg_ip_edit.text().strip()
        mask = self.cfg_mask_edit.text().strip()
        gateway = self.cfg_gateway_edit.text().strip()
        try:
            IPv4Address(ip)
        except ValueError as exc:
            raise ConfigError("err_invalid_ip", value=ip or "-") from exc
        try:
            mask = str(IPv4Network(f"0.0.0.0/{mask}").netmask)
        except ValueError as exc:
            raise ConfigError("err_invalid_mask", value=mask or "-") from exc
        if gateway:
            try:
                IPv4Address(gateway)
            except ValueError as exc:
                raise ConfigError("err_invalid_gateway", value=gateway) from exc
        return ip, mask, gateway

    def _validate_dns_config(self) -> list:
        raw = (
            self.cfg_dns_edit.text()
            .replace("，", ",")
            .replace("；", ",")
            .replace(";", ",")
        )
        servers = [part.strip() for chunk in raw.split(",") for part in chunk.split()]
        servers = [server for server in servers if server]
        if not servers:
            raise ConfigError("err_dns_required")
        for server in servers:
            try:
                IPv4Address(server)
            except ValueError as exc:
                raise ConfigError("err_invalid_dns", value=server) from exc
        return servers

    def _apply_config(self):
        item = self.interface_combo.currentData()
        if not item:
            self._show_error("err_no_interface")
            return
        system = platform.system()
        if system not in ("Windows", "Linux", "Darwin"):
            self._show_error("err_not_windows")
            return

        ip_mode = self.config_ip_mode_combo.currentData()
        dns_mode = self.config_dns_mode_combo.currentData()
        try:
            ip, mask, gateway = self._validate_ip_config() if ip_mode == "static" else ("", "", "")
            dns_servers = self._validate_dns_config() if dns_mode == "static" else []
        except ConfigError as exc:
            QMessageBox.warning(self, "", self._tr(exc.key).format(**exc.params))
            return

        summary = self._config_summary(item["name"], ip_mode, ip, mask, gateway, dns_mode, dns_servers)
        answer = QMessageBox.question(
            self,
            self._tr("confirm_title"),
            self._tr("confirm_text").format(name=item["name"], summary=summary),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        config = {
            "name": item["name"],
            "connection": item.get("connection", ""),
            "service": item.get("service", ""),
            "ip_mode": ip_mode,
            "ip": ip,
            "mask": mask,
            "gateway": gateway,
            "dns_mode": dns_mode,
            "dns_servers": dns_servers,
        }
        self.apply_btn.setEnabled(False)
        self._state = "applying"
        self.hint_label.setText(self._tr("hint_applying"))
        QApplication.processEvents()
        try:
            if system == "Windows" and not self._is_admin():
                self._elevate_windows(config)
                return
            proc = self._write_system_config(config)
        except PermissionError as exc:
            self._show_error("err_root_required")
            self.apply_btn.setEnabled(True)
            self._state = "loaded"
            return
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            self._show_error("err_write", code="-", output=str(exc))
            self.apply_btn.setEnabled(True)
            self._state = "loaded"
            return

        self.apply_btn.setEnabled(True)
        self._state = "loaded"
        if proc.returncode != 0:
            output = self._decode_console(proc.stdout) or self._decode_console(proc.stderr)
            self._show_error("err_write", code=proc.returncode, output=output or "-")
            return

        QMessageBox.information(
            self, self._tr("success_title"), self._tr("success_text").format(name=item["name"])
        )
        self._state = "loading"
        self.hint_label.setText(self._tr("hint_loading"))
        QTimer.singleShot(1500, lambda: self._load_interfaces(item["name"]))

    def _write_system_config(self, config):
        system = platform.system()
        if system == "Windows":
            script = self._build_apply_script(
                config["name"], config["ip_mode"], config["ip"], config["mask"],
                config["gateway"], config["dns_mode"], config["dns_servers"],
            )
            return self._run_powershell(script, timeout=60)
        if system == "Linux":
            return self._write_linux_config(config)
        if system == "Darwin":
            return self._write_macos_config(config)
        raise OSError(self._tr("err_not_windows"))

    @staticmethod
    def _run_command(args, timeout=60):
        kwargs = {"capture_output": True, "text": False, "timeout": timeout}
        if platform.system() == "Windows":
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        return subprocess.run(args, **kwargs)

    def _elevate_windows(self, config):
        answer = QMessageBox.question(
            self,
            self._tr("elevate_title"),
            self._tr("elevate_text"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.apply_btn.setEnabled(True)
            self._state = "loaded"
            return

        payload = base64.urlsafe_b64encode(
            json.dumps(config, ensure_ascii=True).encode("utf-8")
        ).decode("ascii")
        launched = self._relaunch_as_admin(["--page", "network_ip", "--elevated-config", payload])
        if not launched:
            self._show_error("elevate_failed")
            self.apply_btn.setEnabled(True)
            self._state = "loaded"
            return
        QApplication.instance().quit()

    def _relaunch_as_admin(self, arguments) -> bool:
        main_module = sys.modules.get("main")
        if main_module is not None and hasattr(main_module, "relaunch_as_admin"):
            try:
                return bool(main_module.relaunch_as_admin(arguments))
            except (OSError, AttributeError):
                return False
        if platform.system() != "Windows":
            return False
        try:
            import ctypes

            if getattr(sys, "frozen", False):
                file_name = sys.executable
                parameters = subprocess.list2cmdline(list(arguments))
            else:
                script = os.path.abspath(sys.argv[0])
                file_name = sys.executable
                parameters = subprocess.list2cmdline([script, *arguments])
            return ctypes.windll.shell32.ShellExecuteW(
                None, "runas", file_name, parameters, None, 1
            ) > 32
        except (OSError, AttributeError):
            return False

    def apply_elevated_config(self, config):
        """由重新启动后的管理员实例调用：记录待写入配置，界面加载完成后自动执行。"""
        self._elevated_pending = config

    def _maybe_apply_pending(self):
        if not self._elevated_pending:
            return
        config = self._elevated_pending
        self._elevated_pending = None

        # 选中目标网卡
        iface = config.get("name")
        index = self.interface_combo.findText(iface) if iface else -1
        if index >= 0:
            self.interface_combo.setCurrentIndex(index)
            item = self.interface_combo.currentData()
            if item:
                self._show_selected_interface()

        # 用待写入的值回填配置区，再直接执行（用户在提权前已确认）
        self.config_ip_mode_combo.setCurrentIndex(0 if config["ip_mode"] != "static" else 1)
        self.config_dns_mode_combo.setCurrentIndex(0 if config["dns_mode"] != "static" else 1)
        self.cfg_ip_edit.setText(config["ip"])
        self.cfg_mask_edit.setText(config["mask"])
        self.cfg_gateway_edit.setText(config["gateway"])
        self.cfg_dns_edit.setText(", ".join(config["dns_servers"]))
        self._update_config_state()
        self._elevated_iface = iface or ""

        # 写入脚本
        system = platform.system()
        if system == "Windows":
            proc = self._run_powershell(
                self._build_apply_script(
                    config["name"], config["ip_mode"], config["ip"], config["mask"],
                    config["gateway"], config["dns_mode"], config["dns_servers"],
                ),
                timeout=60,
            )
        elif system == "Linux":
            proc = self._write_linux_config(config)
        elif system == "Darwin":
            proc = self._write_macos_config(config)
        else:
            proc = None

        self._elevated_apply_finished(proc)

    def _elevated_apply_finished(self, proc):
        if proc is None:
            return
        if proc.returncode == 0:
            name = getattr(self, "_elevated_iface", "")
            QMessageBox.information(
                self,
                self._tr("success_title"),
                self._tr("success_text").format(name=name),
            )
            self.hint_label.setText(self._tr("hint_loaded"))
            QTimer.singleShot(1500, lambda: self._load_interfaces())
        else:
            output = self._decode_console(proc.stdout) or self._decode_console(proc.stderr)
            self._show_error("err_write", code=proc.returncode, output=output or "-")


    def _write_linux_config(self, config):
        if not shutil.which("nmcli"):
            raise OSError("nmcli is not installed; install NetworkManager first.")
        conn = config.get("connection")
        if not conn:
            raise OSError(self._tr("err_no_connection").format(name=config["name"]))

        args = ["nmcli", "connection", "modify", conn]
        if config["ip_mode"] == "dhcp":
            args.extend(["ipv4.method", "auto", "ipv4.addresses", "", "ipv4.gateway", ""])
        else:
            prefix = IPv4Network("0.0.0.0/" + config["mask"]).prefixlen
            address = f"{config['ip']}/{prefix}"
            args.extend(["ipv4.method", "manual", "ipv4.addresses", address,
                         "ipv4.gateway", config["gateway"]])
        if config["dns_mode"] == "dhcp":
            args.extend(["ipv4.ignore-auto-dns", "no", "ipv4.dns", ""])
        else:
            args.extend(["ipv4.ignore-auto-dns", "yes", "ipv4.dns", ",".join(config["dns_servers"])])

        if os.geteuid() != 0:
            if not shutil.which("pkexec"):
                raise PermissionError(self._tr("err_root_required"))
            args = ["pkexec"] + args
        proc = self._run_command(args)
        if proc.returncode == 0:
            up_args = ["nmcli", "connection", "up", conn]
            if os.geteuid() != 0:
                up_args = ["pkexec"] + up_args
            proc = self._run_command(up_args)
        return proc

    def _write_macos_config(self, config):
        service = config.get("service")
        if not service:
            raise OSError(self._tr("err_no_service").format(name=config["name"]))
        commands = []
        if config["ip_mode"] == "dhcp":
            commands.append(["networksetup", "-setdhcp", service])
        else:
            commands.append([
                "networksetup", "-setmanual", service, config["ip"], config["mask"], config["gateway"]
            ])
        if config["dns_mode"] == "dhcp":
            commands.append(["networksetup", "-setdnsservers", service, "empty"])
        else:
            commands.append(["networksetup", "-setdnsservers", service] + config["dns_servers"])

        if os.geteuid() != 0:
            quoted = " ".join(shlex.quote(arg) for command in commands for arg in command)
            script = " ".join(shlex.quote(arg) for arg in commands[0])
            script += " && " + " && ".join(
                " ".join(shlex.quote(arg) for arg in command) for command in commands[1:]
            )
            escaped = script.replace("\\", "\\\\").replace('"', '\\"')
            proc = self._run_command([
                "osascript", "-e", f'do shell script "{escaped}" with administrator privileges'
            ])
            return proc
        proc = None
        for command in commands:
            proc = self._run_command(command)
            if proc.returncode != 0:
                return proc
        return proc


    def _config_summary(self, name, ip_mode, ip, mask, gateway, dns_mode, dns_servers) -> str:
        lines = []
        if ip_mode == "dhcp":
            lines.append(f"{self._tr('label_ip_mode')}: {self._tr('mode_dhcp')}")
        else:
            lines.append(f"{self._tr('label_ip')}: {ip}")
            lines.append(f"{self._tr('label_mask')}: {mask}")
            lines.append(f"{self._tr('label_gateway')}: {gateway or '-'}")
        if dns_mode == "dhcp":
            lines.append(f"{self._tr('label_dns_mode')}: {self._tr('mode_dhcp')}")
        else:
            lines.append(f"{self._tr('label_dns')}: {', '.join(dns_servers)}")
        return "\n".join(lines)

    @staticmethod
    def _ps_quote(value: str) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    def _build_apply_script(
        self, alias, ip_mode, ip, mask, gateway, dns_mode, dns_servers
    ) -> str:
        name = f"name={self._ps_quote(alias)}"
        lines = ["$ErrorActionPreference='Continue'"]
        if ip_mode == "dhcp":
            lines.append(f"netsh interface ipv4 set address {name} source=dhcp")
        else:
            target = f"{name} source=static address={ip} mask={mask} gateway={gateway or 'none'}"
            lines.append(f"netsh interface ipv4 set address {target}")
        lines.append("if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }")

        if dns_mode == "dhcp":
            lines.append(f"netsh interface ipv4 set dnsservers {name} source=dhcp")
        else:
            primary, *rest = dns_servers
            lines.append(
                f"netsh interface ipv4 set dnsservers {name} source=static "
                f"address={primary} register=primary validate=no"
            )
            lines.append("if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }")
            for index, server in enumerate(rest, start=2):
                lines.append(
                    f"netsh interface ipv4 add dnsservers {name} address={server} "
                    f"index={index} validate=no"
                )
                lines.append("if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }")
        return "\n".join(lines)
