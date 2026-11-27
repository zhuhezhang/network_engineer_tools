# Network Engineer Tools

A desktop toolkit built with Python and PySide6 for network engineers and everyday network troubleshooting. It brings text comparison, IPv4 subnet calculations, batch connectivity checks, and network adapter IP configuration into one application, with support for both Chinese and English interfaces.

- GitHub: https://github.com/zhuhezhang/network_engineer_tools
- Gitee: https://gitee.com/zhuhezhang/network_engineer_tools

## Features

### Text Comparison

- Edit and compare two texts side by side to identify added, removed, and modified content.
- Display line numbers and character-level difference highlighting for precise inspection.
- Import text files using multiple character encodings.
- Search, navigate between matches, and replace text with case-sensitive, whole-word, and regular-expression options.
- Adjust text-area proportions, scale the interface font, and switch between Chinese and English.

### IP Address Calculator

- Calculate network information from an IPv4 address and subnet mask/prefix.
- Support subnet covering (aggregation) calculations and VLSM address planning.
- Validate input and present calculation results in a structured view for address planning and troubleshooting.

### Batch Ping

- Probe multiple IP addresses or hostnames concurrently and continue checking at a configurable interval.
- Display live success/failure status, packet-loss rate, and latency statistics.
- Adjust the probe concurrency (default: 50; range: 1–500).
- Highlight failed targets in light red and allow table columns to be resized as needed.

### Network Adapter IP Configuration

- View local network adapters and their IP configuration information.
- Configure IP address, subnet mask, gateway, and DNS settings, including DHCP/manual configuration workflows.
- Save commonly used configuration profiles for switching between network environments.
- Changing adapter settings on Windows may require administrator privileges. Verify all values before applying a profile.

### Interface and Usability

- Switch between Simplified Chinese and English.
- Scale the global interface font; use Ctrl (Cmd on macOS) + mouse wheel to zoom.
- Resize the sidebar and supported split areas; double-clicking a splitter restores its default proportions where available.

## Requirements

- Python 3.8 or newer
- pip
- Windows, Linux, or macOS (network adapter configuration capabilities depend on the operating system)

## Installation

From the project directory, install the dependencies:

```bash
python -m pip install PySide6 charset-normalizer icmplib
```

## Run

```bash
python main.py
```

## Usage Notes

- In Batch Ping, enter multiple targets, configure the interval, timeout, and concurrency, then start the check.
- Network adapter changes can interrupt the current connection. Record the existing configuration first and make sure the IP address, mask, gateway, and DNS values match the target network.
- To create a virtual environment on Linux, use `python3 -m venv .venv`; on Windows, use `python -m venv .venv`. Activate the environment before installing dependencies.

## Packaging

The application can be packaged with PyInstaller or Nuitka. A basic PyInstaller example is:

```bash
pyinstaller -F -w main.py
```

Nuitka can also be used to build the PySide6 application with platform-specific GUI and product settings. Single-file builds may be flagged by some security software, so test the packaged application thoroughly in the target environment before distribution.
