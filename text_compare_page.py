from __future__ import annotations
from difflib import SequenceMatcher
from sys import platform
from typing import List, Optional
from charset_normalizer import from_bytes
from PySide6.QtCore import Qt, Signal, QRegularExpression, QTimer, QSize
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QTextCursor,
    QTextCharFormat,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QSplitterHandle,
    QTextEdit,
    QWidget,
    QVBoxLayout,
)

TRANSLATIONS = {
    "zh": {
        "win_title": "网络工程师工具",
        "menu_file": "文件",
        "action_open_left": "打开左侧文件",
        "action_open_right": "打开右侧文件",
        "action_exit": "退出",
        "menu_edit": "编辑",
        "action_find": "查找",
        "action_find_next": "查找下一个",
        "action_find_prev": "查找上一个",
        "action_replace": "替换",
        "menu_compare": "比较",
        "action_compare": "开始比较",
        "menu_view": "视图",
        "action_zoom_in": "放大",
        "action_zoom_out": "缩小",
        "action_zoom_reset": "重置缩放",
        "menu_lang": "语言/Language",
        "menu_help": "帮助",
        "action_about": "关于",
        "placeholder_orig": "原始文本",
        "placeholder_mod": "修改后的文本",
        "placeholder_result_of_orig": "原始文本比较结果（对齐后）",
        "placeholder_result_of_mod": "修改后文本的比较结果（对齐后）",
        "status_ready": "就绪",
        "status_comp_done": "比较完成",
        "open_text_file": "打开文本文件",
        "open_text_file_mode": "文本文件 (*.txt *.log);;所有文件 (*.*)",
        "error": "错误",
        "status_open_file": "无法读取文件:\n{e}",
        "status_loading": "已加载(编码: {enc}): {path}",
        "find_title": "查找和替换",
        "find_label": "查找(&N):",
        "replace_label": "替换为(&P):",
        "case_match": "大小写匹配(&C)",
        "whole_word": "全词匹配(&W)",
        "regex": "正则表达式(&E)",
        "btn_replace_all": "全部替换(&A)",
        "btn_replace": "替换(&R)",
        "btn_find_prev": "查找上一个(&B)",
        "btn_find_next": "查找下一个(&F)",
        "btn_close": "关闭",
        "msg_not_found": "未找到: {text}",
        "msg_index": "第 {idx}/{total} 项",
        "msg_replace_done": "已成功替换 {count} 处",
        "regex_error": "正则语法错误: {err}",
        "nav_text_compare": "文本对比",
        "nav_ip_calculator": "IP地址计算",
        "nav_batch_ping": "批量ping",
        "nav_network_ip_set": "网卡IP地址设置",
        "placeholder_page": "该功能正在开发中，敬请期待。",
    },
    "en": {
        "win_title": "Network Engineer Tools",
        "menu_file": "File",
        "action_open_left": "Open Left File",
        "action_open_right": "Open Right File",
        "action_exit": "Exit",
        "menu_edit": "Edit",
        "action_find": "Find",
        "action_find_next": "Find Next",
        "action_find_prev": "Find Previous",
        "action_replace": "Replace",
        "menu_compare": "Compare",
        "action_compare": "Start Compare",
        "menu_view": "View",
        "action_zoom_in": "Zoom In",
        "action_zoom_out": "Zoom Out",
        "action_zoom_reset": "Zoom Reset",
        "menu_lang": "Language/语言",
        "menu_help": "Help",
        "action_about": "About",
        "placeholder_orig": "Original Text",
        "placeholder_mod": "Modified Text",
        "placeholder_result_of_orig": "Comparison Result Of Original Text (Aligned)",
        "placeholder_result_of_mod": "Comparison Result Of Modified Text (Aligned)",
        "status_ready": "Ready",
        "status_comp_done": "Comparison Complete",
        "open_text_file": "Open Text File",
        "open_text_file_mode": "Text Files (*.txt *.log);;All Files (*.*)",
        "error": "Error",
        "status_open_file": "Can't Read File:\n{e}",
        "status_loading": "Loaded (Encoding: {enc}): {path}",
        "find_title": "Find and Replace",
        "find_label": "Find(&N):",
        "replace_label": "Replace With(&P):",
        "case_match": "Match Case(&C)",
        "whole_word": "Whole Word(&W)",
        "regex": "Regular Expression(&E)",
        "btn_replace_all": "Replace All(&A)",
        "btn_replace": "Replace(&R)",
        "btn_find_prev": "Find Previous(&B)",
        "btn_find_next": "Find Next(&F)",
        "btn_close": "Close",
        "msg_not_found": "Not Found: {text}",
        "msg_index": "Item {idx}/{total}",
        "msg_replace_done": "Successfully replaced {count} occurrence(s)",
        "regex_error": "Regex Error: {err}",
        "nav_text_compare": "Text Compare",
        "nav_ip_calculator": "IP Calculator",
        "nav_batch_ping": "Batch Ping",
        "nav_network_ip_set": "NIC IP Settings",
        "placeholder_page": "This feature is under development, please stay tuned.",
    },
}

DEFAULT_FONT_SIZE = 10
if platform == "darwin":
    DEFAULT_FONT_SIZE = 15
MIN_FONT_SIZE = 5
MAX_FONT_SIZE = 25


class ResetHandle(QSplitterHandle):
    """支持双击分割条重置比例"""

    def mouseDoubleClickEvent(self, event):
        s = self.splitter()
        if isinstance(s, ResetSplitter):
            s.reset_layout()


class ResetSplitter(QSplitter):
    """支持比例重置的分割器"""

    def __init__(self, orientation, weights=None, parent=None):
        super().__init__(orientation, parent)
        self.weights = weights if weights else [1, 1]

    def createHandle(self):
        return ResetHandle(self.orientation(), self)

    def reset_layout(self):
        total_size = sum(self.sizes())
        if total_size <= 0:
            return
        total_weight = sum(self.weights)
        new_sizes = [int(total_size * w / total_weight) for w in self.weights]
        self.setSizes(new_sizes)


class LineNumberPlainTextEdit(QPlainTextEdit):
    """带行号的文本编辑器。"""

    focusReceived = Signal(object)

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font_style = QFont()
        font_style.setPointSize(DEFAULT_FONT_SIZE)
        self.setFont(font_style)
        self.diff_selections = []
        self.search_selections = []

        p = self.palette()
        p.setColor(p.ColorGroup.Inactive, p.ColorRole.Highlight,
                   p.color(p.ColorGroup.Active, p.ColorRole.Highlight))
        p.setColor(p.ColorGroup.Inactive, p.ColorRole.HighlightedText,
                   p.color(p.ColorGroup.Active, p.ColorRole.HighlightedText))
        self.setPalette(p)

        self.line_number_area = LineNumberArea(self)
        self.document().blockCountChanged.connect(self.update_line_number_width)
        self.verticalScrollBar().valueChanged.connect(lambda v: self.line_number_area.update())
        self.textChanged.connect(self.update_line_number_width)
        self.update_line_number_width()

    def set_diff_selections(self, selections: List[QTextEdit.ExtraSelection]):
        self.diff_selections = selections
        self.setExtraSelections(self.diff_selections + self.search_selections)

    def highlight_search_text(self, text: str, case_sensitive: bool, whole_word: bool, use_regex: bool) -> List[QTextCursor]:
        self.search_selections.clear()
        match_cursors = []
        if text:
            doc = self.document()
            cursor = QTextCursor(doc)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(135, 206, 235))
            fmt.setForeground(Qt.black)

            if use_regex:
                options = QRegularExpression.PatternOption.NoPatternOption
                if not case_sensitive:
                    options |= QRegularExpression.PatternOption.CaseInsensitiveOption
                pattern = text
                if whole_word:
                    pattern = f"\\b{text}\\b"
                regex = QRegularExpression(pattern, options)
                current_pos = 0
                while True:
                    match = regex.match(doc.toPlainText(), current_pos)
                    if not match.hasMatch():
                        break
                    match_cursor = QTextCursor(doc)
                    match_cursor.setPosition(match.capturedStart())
                    match_cursor.setPosition(match.capturedEnd(), QTextCursor.MoveMode.KeepAnchor)
                    selection = QTextEdit.ExtraSelection()
                    selection.cursor = match_cursor
                    selection.format = fmt
                    self.search_selections.append(selection)
                    match_cursors.append(match_cursor)
                    current_pos = match.capturedEnd()
                    if match.capturedLength() == 0:
                        current_pos += 1
            else:
                flags = QTextDocument.FindFlag(0)
                if case_sensitive:
                    flags |= QTextDocument.FindFlag.FindCaseSensitively
                if whole_word:
                    flags |= QTextDocument.FindFlag.FindWholeWords
                while True:
                    cursor = doc.find(text, cursor, flags)
                    if cursor.isNull():
                        break
                    selection = QTextEdit.ExtraSelection()
                    selection.cursor = cursor
                    selection.format = fmt
                    self.search_selections.append(selection)
                    match_cursors.append(QTextCursor(cursor))

        self.setExtraSelections(self.diff_selections + self.search_selections)
        return match_cursors

    def _line_number_width(self):
        digits = len(str(self.document().blockCount()))
        return 10 + self.fontMetrics().horizontalAdvance('9') * digits

    def update_line_number_width(self):
        self.setViewportMargins(self._line_number_width(), 0, 0, 0)
        self.line_number_area.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(cr.left(), cr.top(), self._line_number_width(), cr.height())

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.line_number_area.scroll(0, dy)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focusReceived.emit(self)

    def wheelEvent(self, event):
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            delta = event.angleDelta().y()
            if delta > 0:
                self.main_window.zoom_in()
            else:
                self.main_window.zoom_out()
        else:
            super().wheelEvent(event)


class LineNumberArea(QWidget):
    """行号区域"""

    def __init__(self, editor: LineNumberPlainTextEdit):
        super().__init__(editor)
        self.editor = editor

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(240, 240, 240))
        block = self.editor.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
        bottom = top + self.editor.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(Qt.darkGray)
                painter.drawText(
                    0, int(top), self.width() - 2,
                    self.editor.fontMetrics().height(),
                    Qt.AlignRight, number,
                )
            block = block.next()
            top = bottom
            bottom = top + self.editor.blockBoundingRect(block).height()
            block_number += 1
        painter.end()


class FindReplaceDialog(QDialog):
    """查找/替换对话框"""

    def __init__(self, text_compare_tool):
        super().__init__(text_compare_tool)
        self.text_compare_tool = text_compare_tool
        self.setWindowTitle("查找和替换")
        self.setModal(False)
        self.editor: Optional[LineNumberPlainTextEdit] = None
        self.current_matches: List[QTextCursor] = []
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setSizeGripEnabled(True)
        self.regex_error_flag = False

        self.find_label = QLabel("查找(&N):")
        self.find_edit = QLineEdit()
        self.find_label.setBuddy(self.find_edit)

        self.replace_label = QLabel("替换为(&P):")
        self.replace_edit = QLineEdit()
        self.replace_label.setBuddy(self.replace_edit)

        self.case_check = QCheckBox("大小写匹配(&C)")
        self.whole_check = QCheckBox("全词匹配(&W)")
        self.regex_check = QCheckBox("正则表达式(&E)")

        self.replace_all_btn = QPushButton("全部替换(&A)")
        self.replace_all_btn.setAutoDefault(False)
        self.replace_btn = QPushButton("替换(&R)")
        self.replace_btn.setAutoDefault(False)
        self.find_prev_btn = QPushButton("查找上一个(&B)")
        self.find_prev_btn.setAutoDefault(False)
        self.find_next_btn = QPushButton("查找下一个(&F)")
        self.find_next_btn.setAutoDefault(False)
        self.close_btn = QPushButton("关闭")
        self.close_btn.setAutoDefault(False)

        grid = QGridLayout()
        grid.addWidget(self.find_label, 0, 0)
        grid.addWidget(self.find_edit, 0, 1, 1, 3)
        grid.addWidget(self.replace_label, 1, 0)
        grid.addWidget(self.replace_edit, 1, 1, 1, 3)

        options_layout = QHBoxLayout()
        options_layout.addWidget(self.case_check)
        options_layout.addWidget(self.whole_check)
        options_layout.addWidget(self.regex_check)
        options_layout.addStretch()
        grid.addLayout(options_layout, 2, 0, 1, 4)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.replace_all_btn)
        btn_layout.addWidget(self.replace_btn)
        btn_layout.addWidget(self.find_prev_btn)
        btn_layout.addWidget(self.find_next_btn)
        btn_layout.addWidget(self.close_btn)
        grid.addLayout(btn_layout, 3, 0, 1, 4)
        self.setLayout(grid)

        self.default_palette = self.find_edit.palette()
        self.error_palette = self.find_edit.palette()
        self.error_palette.setColor(self.error_palette.ColorRole.Text, QColor(220, 50, 50))

        self.replace_all_btn.clicked.connect(self.replace_all)
        self.replace_btn.clicked.connect(self.replace)
        self.find_prev_btn.clicked.connect(self.find_prev)
        self.find_next_btn.clicked.connect(self.find_next)
        self.close_btn.clicked.connect(self.close)
        self.find_edit.returnPressed.connect(self.find_next)
        self.replace_edit.returnPressed.connect(self.replace)
        self.find_edit.textChanged.connect(self._update_highlights)
        self.case_check.stateChanged.connect(self._update_highlights)
        self.whole_check.stateChanged.connect(self._update_highlights)
        self.regex_check.stateChanged.connect(self._update_highlights)

        self._update_button_state()
        self.retranslate_ui()
        self.resize(520, 180)
        # self.setMinimumSize(420, 180)
        # self.setFixedSize(self.sizeHint().expandedTo(QSize(420, 180)))

    # def lock_size(self):
    #     self.setFixedSize(self.size())
    #     self.setMinimumSize(self.size())
    #     self.setMaximumSize(self.size())

    def retranslate_ui(self):
        tr = TRANSLATIONS[self.text_compare_tool.current_lang]
        self.setWindowTitle(tr["find_title"])
        self.find_label.setText(tr["find_label"])
        self.replace_label.setText(tr["replace_label"])
        self.case_check.setText(tr["case_match"])
        self.whole_check.setText(tr["whole_word"])
        self.regex_check.setText(tr["regex"])
        self.replace_all_btn.setText(tr["btn_replace_all"])
        self.replace_btn.setText(tr["btn_replace"])
        self.find_prev_btn.setText(tr["btn_find_prev"])
        self.find_next_btn.setText(tr["btn_find_next"])
        self.close_btn.setText(tr["btn_close"])

    def set_editor(self, editor: QPlainTextEdit):
        if self.editor and self.editor != editor:
            if hasattr(self.editor, 'highlight_search_text'):
                self.editor.highlight_search_text("", False, False, False)
            try:
                self.editor.textChanged.disconnect(self._update_highlights)
            except Exception:
                pass
        if isinstance(editor, QPlainTextEdit):
            self.editor = editor
            self._update_highlights()
            self.editor.textChanged.connect(self._update_highlights)
        else:
            self.editor = None
        self._update_button_state()

    def _update_highlights(self):
        if (self.editor is None) or (not hasattr(self.editor, 'highlight_search_text')) or (not self.isVisible()):
            self._update_statusbar_according_to_matches(0, 0)
            return

        text = self.find_edit.text()
        use_regex = self.regex_check.isChecked()

        if use_regex and text:
            re_test = QRegularExpression(text)
            if not re_test.isValid():
                self.regex_error_flag = True
                self.find_edit.setPalette(self.error_palette)
                for btn in [self.replace_all_btn, self.replace_btn, self.find_prev_btn, self.find_next_btn]:
                    btn.setEnabled(False)
                for action in [self.text_compare_tool.action_find_next, self.text_compare_tool.action_find_prev]:
                    action.setEnabled(False)
                error_msg = re_test.errorString()
                if hasattr(self.text_compare_tool, 'status_bar'):
                    msg = TRANSLATIONS[self.text_compare_tool.current_lang]["regex_error"].format(err=error_msg)
                    self.text_compare_tool.status_bar.showMessage(msg, 5000)
                self.current_matches = []
                self.editor.highlight_search_text("", False, False, False)
                return

        self.regex_error_flag = False
        self.find_edit.setPalette(self.default_palette)
        for btn in [self.replace_all_btn, self.replace_btn, self.find_prev_btn, self.find_next_btn]:
            btn.setEnabled(True)
        for action in [self.text_compare_tool.action_find_next, self.text_compare_tool.action_find_prev]:
            action.setEnabled(True)

        case_sens = self.case_check.isChecked()
        whole_word = self.whole_check.isChecked()
        self.current_matches = self.editor.highlight_search_text(text, case_sens, whole_word, use_regex)
        self.refresh_status_index()

    def refresh_status_index(self):
        total = len(self.current_matches)
        if total == 0:
            self._update_statusbar_according_to_matches(0, 0)
            return
        current_cursor = self.editor.textCursor()
        curr_pos = current_cursor.selectionStart()

        index = 0
        for i, m_cursor in enumerate(self.current_matches):
            if m_cursor.selectionStart() >= curr_pos:
                index = i + 1
                break
        if index == 0 and total > 0:
            index = total
        self._update_statusbar_according_to_matches(index, total)

    def _update_statusbar_according_to_matches(self, index, total):
        tr = TRANSLATIONS[self.text_compare_tool.current_lang]
        if self.find_edit.text() != "":
            if total == 0:
                msg = tr["msg_not_found"].format(text=self.find_edit.text())
            else:
                msg = tr["msg_index"].format(idx=index, total=total)
            if hasattr(self.text_compare_tool, 'status_bar'):
                self.text_compare_tool.status_bar.showMessage(msg, 5000)

    def _update_button_state(self):
        if self.editor is not None:
            enable = not self.editor.isReadOnly()
        else:
            enable = False
        self.replace_btn.setEnabled(enable)
        self.replace_all_btn.setEnabled(enable)
        self.replace_label.setEnabled(enable)
        self.replace_edit.setEnabled(enable)
        if self.regex_error_flag:
            self.replace_all_btn.setEnabled(False)
            self.replace_btn.setEnabled(False)

    def setVisible(self, visible: bool):
        super().setVisible(visible)
        if visible:
            self._update_highlights()
        else:
            if self.editor and hasattr(self.editor, 'highlight_search_text'):
                self.editor.highlight_search_text("", False, False, False)
                if hasattr(self.text_compare_tool, 'status_bar'):
                    self.text_compare_tool.status_bar.clearMessage()
            if self.editor is not None:
                cursor = self.editor.textCursor()
                cursor.clearSelection()
                self.editor.setTextCursor(cursor)

    def find_next(self):
        if self.editor is None:
            return
        text = self.find_edit.text()
        if not text:
            return

        case_sens = self.case_check.isChecked()
        whole_word = self.whole_check.isChecked()
        use_regex = self.regex_check.isChecked()
        if use_regex:
            curr_pos = self.editor.textCursor().position()
            target_cursor = None
            for m_cursor in self.current_matches:
                if m_cursor.selectionStart() > curr_pos:
                    target_cursor = m_cursor
                    break
            if target_cursor is None and self.current_matches:
                target_cursor = self.current_matches[0]
            if target_cursor:
                self.editor.setTextCursor(target_cursor)
        else:
            flags = QTextDocument.FindFlag(0)
            if case_sens:
                flags |= QTextDocument.FindFlag.FindCaseSensitively
            if whole_word:
                flags |= QTextDocument.FindFlag.FindWholeWords
            if not self.editor.find(text, flags):
                cursor = self.editor.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                self.editor.setTextCursor(cursor)
                self.editor.find(text, flags)
        self.refresh_status_index()

    def find_prev(self):
        if self.editor is None:
            return
        text = self.find_edit.text()
        if not text:
            return

        use_regex = self.regex_check.isChecked()
        if use_regex:
            curr_pos = self.editor.textCursor().selectionStart()
            target_cursor = None
            for m_cursor in reversed(self.current_matches):
                if m_cursor.selectionEnd() < curr_pos:
                    target_cursor = m_cursor
                    break
            if target_cursor is None and self.current_matches:
                target_cursor = self.current_matches[-1]
            if target_cursor:
                self.editor.setTextCursor(target_cursor)
        else:
            flags = QTextDocument.FindFlag.FindBackward
            if self.case_check.isChecked():
                flags |= QTextDocument.FindFlag.FindCaseSensitively
            if self.whole_check.isChecked():
                flags |= QTextDocument.FindFlag.FindWholeWords
            if not self.editor.find(text, flags):
                cursor = self.editor.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.editor.setTextCursor(cursor)
                self.editor.find(text, flags)
        self.refresh_status_index()

    def replace(self):
        if self.editor is None or self.editor.isReadOnly():
            return
        find_text = self.find_edit.text()
        if not find_text:
            return

        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            selected = cursor.selectedText()
            use_regex = self.regex_check.isChecked()
            if use_regex:
                options = QRegularExpression.PatternOption.NoPatternOption
                if not self.case_check.isChecked():
                    options |= QRegularExpression.PatternOption.CaseInsensitiveOption
                pattern = find_text
                if self.whole_check.isChecked():
                    pattern = f"\\b{find_text}\\b"
                regex = QRegularExpression(f"^{pattern}$", options)
                match = regex.match(selected).hasMatch()
            else:
                if self.case_check.isChecked():
                    match = (selected == find_text)
                else:
                    match = (selected.lower() == find_text.lower())
            if match:
                cursor.insertText(self.replace_edit.text())

        self.find_next()
        self._update_highlights()

    def replace_all(self):
        if self.editor is None or self.editor.isReadOnly():
            return
        find_text = self.find_edit.text()
        replace_text = self.replace_edit.text()
        if not find_text:
            return
        self._update_highlights()
        if not self.current_matches:
            return

        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        count = len(self.current_matches)
        for m_cursor in reversed(self.current_matches):
            m_cursor.insertText(replace_text)
        cursor.endEditBlock()

        if hasattr(self.text_compare_tool, 'status_bar'):
            msg = TRANSLATIONS[self.text_compare_tool.current_lang]["msg_replace_done"].format(count=count)
            self.text_compare_tool.status_bar.showMessage(msg)

        QTimer.singleShot(3000, self._update_highlights)


class TextComparePage(QWidget):
    """文本比较功能页"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_font_size = DEFAULT_FONT_SIZE
        self.current_editor = None
        self.find_dialog = FindReplaceDialog(self.main_window)
        self._init_ui()
        self._setup_context_menus()
        self._connect_focus_signals()
        self._sync_scrollbars()
        self.retranslate_ui()

    def _init_ui(self):
        self.compare_layout = QVBoxLayout(self)
        self.compare_layout.setContentsMargins(0, 0, 0, 0)

        vertical_splitter = ResetSplitter(Qt.Vertical, weights=[1, 2])
        input_splitter = ResetSplitter(Qt.Horizontal, weights=[1, 1])
        self.text_left_input = LineNumberPlainTextEdit(self.main_window)
        self.text_right_input = LineNumberPlainTextEdit(self.main_window)
        input_splitter.addWidget(self.text_left_input)
        input_splitter.addWidget(self.text_right_input)

        result_splitter = ResetSplitter(Qt.Horizontal, weights=[1, 1])
        self.text_left_result = LineNumberPlainTextEdit(self.main_window)
        self.text_right_result = LineNumberPlainTextEdit(self.main_window)
        for editor in (self.text_left_result, self.text_right_result):
            editor.setReadOnly(True)
        result_splitter.addWidget(self.text_left_result)
        result_splitter.addWidget(self.text_right_result)

        vertical_splitter.addWidget(input_splitter)
        vertical_splitter.addWidget(result_splitter)
        vertical_splitter.setStretchFactor(0, 1)
        vertical_splitter.setStretchFactor(1, 2)
        self.compare_layout.addWidget(vertical_splitter)

    def retranslate_ui(self):
        tr = TRANSLATIONS[self.main_window.current_lang]
        self.text_left_input.setPlaceholderText(tr["placeholder_orig"])
        self.text_right_input.setPlaceholderText(tr["placeholder_mod"])
        self.text_left_result.setPlaceholderText(tr["placeholder_result_of_orig"])
        self.text_right_result.setPlaceholderText(tr["placeholder_result_of_mod"])
        self.text_left_input.setToolTip(tr["placeholder_orig"])
        self.text_right_input.setToolTip(tr["placeholder_mod"])
        self.text_left_result.setToolTip(tr["placeholder_result_of_orig"])
        self.text_right_result.setToolTip(tr["placeholder_result_of_mod"])
        for editor in [self.text_left_input, self.text_right_input, self.text_left_result, self.text_right_result]:
            editor.viewport().update()

    def _setup_context_menus(self):
        editors = [self.text_left_input, self.text_right_input, self.text_left_result, self.text_right_result]
        for editor in editors:
            editor.setContextMenuPolicy(Qt.CustomContextMenu)
            editor.customContextMenuRequested.connect(lambda pos, e=editor: self._show_editor_context_menu(e, pos))

    def _show_editor_context_menu(self, editor: QPlainTextEdit, pos):
        tr = TRANSLATIONS[self.main_window.current_lang]
        menu = editor.createStandardContextMenu()
        menu.addSeparator()
        find_action = menu.addAction(tr["action_find"])
        find_action.triggered.connect(lambda: self._show_find_dialog(editor))
        if not editor.isReadOnly():
            replace_action = menu.addAction(tr["action_replace"])
            replace_action.triggered.connect(lambda: self._show_replace_dialog(editor))
        menu.exec(editor.mapToGlobal(pos))

    def _connect_focus_signals(self):
        editors = [self.text_left_input, self.text_right_input, self.text_left_result, self.text_right_result]
        for editor in editors:
            editor.focusReceived.connect(self._on_editor_focused)

    def _on_editor_focused(self, editor: QPlainTextEdit):
        if isinstance(editor, QPlainTextEdit):
            self.current_editor = editor
            if self.find_dialog.isVisible():
                self.find_dialog.set_editor(editor)

    def _sync_scrollbars(self):
        left_ver_scroll = self.text_left_result.verticalScrollBar()
        left_hor_scroll = self.text_left_result.horizontalScrollBar()
        right_ver_scroll = self.text_right_result.verticalScrollBar()
        right_hor_scroll = self.text_right_result.horizontalScrollBar()

        def sync_ver_left(value):
            if value != right_ver_scroll.value():
                right_ver_scroll.setValue(value)

        def sync_hor_left(value):
            if value != right_hor_scroll.value():
                right_hor_scroll.setValue(value)

        def sync_ver_right(value):
            if value != left_ver_scroll.value():
                left_ver_scroll.setValue(value)

        def sync_hor_right(value):
            if value != left_hor_scroll.value():
                left_hor_scroll.setValue(value)

        left_ver_scroll.valueChanged.connect(sync_ver_left)
        left_hor_scroll.valueChanged.connect(sync_hor_left)
        right_ver_scroll.valueChanged.connect(sync_ver_right)
        right_hor_scroll.valueChanged.connect(sync_hor_right)

    def _apply_font_size_to_all_editors(self, size: int):
        editors = [self.text_left_input, self.text_right_input, self.text_left_result, self.text_right_result]
        for editor in editors:
            font = editor.font()
            font.setPointSize(size)
            editor.setFont(font)
            editor.update_line_number_width()
        self.current_font_size = size

    def zoom_in(self):
        new_size = min(MAX_FONT_SIZE, self.current_font_size + 1)
        self._apply_font_size_to_all_editors(new_size)

    def zoom_out(self):
        new_size = max(MIN_FONT_SIZE, self.current_font_size - 1)
        self._apply_font_size_to_all_editors(new_size)

    def _zoom_reset(self):
        self._apply_font_size_to_all_editors(DEFAULT_FONT_SIZE)

    def _open_file(self, text_edit: QPlainTextEdit):
        tr = TRANSLATIONS[self.main_window.current_lang]
        file_path, _ = QFileDialog.getOpenFileName(self, tr["open_text_file"], "", tr["open_text_file_mode"])
        if not file_path:
            return
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            results = from_bytes(raw_data)
            best_match = results.best()
            if best_match:
                content = str(best_match)
                text_edit.setPlainText(content)
                self.main_window.status_bar.showMessage(tr["status_loading"].format(enc=best_match.encoding.upper(), path=file_path))
        except Exception as e:
            QMessageBox.critical(self, tr["error"], tr["status_open_file"].format(e=e))

    def _show_find_dialog(self, editor=None):
        self._show_find_replace_dialog(editor)
        self.find_dialog.find_edit.setFocus()

    def _show_replace_dialog(self, editor=None):
        self._show_find_replace_dialog(editor)
        self.find_dialog.replace_edit.setFocus()

    def _show_find_replace_dialog(self, editor: QPlainTextEdit):
        target = self._ensure_valid_editor(editor)
        self.find_dialog.set_editor(target)
        cursor = target.textCursor()
        if cursor.hasSelection():
            self.find_dialog.find_edit.setText(cursor.selectedText())
        self.find_dialog.show()
        self.find_dialog.raise_()
        self.find_dialog.activateWindow()

    def _find_next(self):
        if self.find_dialog.isVisible():
            self.find_dialog.find_next()
        else:
            if self.find_dialog.find_edit.text():
                target = self._ensure_valid_editor(self.current_editor)
                self.find_dialog.set_editor(target)
                self.find_dialog.find_next()
            else:
                self._show_find_dialog()

    def _find_prev(self):
        if self.find_dialog.isVisible():
            self.find_dialog.find_prev()
        else:
            if self.find_dialog.find_edit.text():
                target = self._ensure_valid_editor(self.current_editor)
                self.find_dialog.set_editor(target)
                self.find_dialog.find_prev()
            else:
                self._show_find_dialog()

    def _ensure_valid_editor(self, editor: QPlainTextEdit):
        if isinstance(editor, QPlainTextEdit):
            return editor
        if isinstance(self.current_editor, QPlainTextEdit):
            return self.current_editor
        return self.text_left_input

    def show_find_dialog(self):
        self._show_find_dialog()

    def show_replace_dialog(self):
        self._show_replace_dialog()

    def find_next(self):
        self._find_next()

    def find_prev(self):
        self._find_prev()

    def _compare_texts(self):
        left_text = self.text_left_input.toPlainText()
        right_text = self.text_right_input.toPlainText()
        left_lines = left_text.splitlines()
        right_lines = right_text.splitlines()
        matcher = SequenceMatcher(None, left_lines, right_lines)
        opcodes = matcher.get_opcodes()
        left_aligned = []
        right_aligned = []

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                for k in range(i2 - i1):
                    left_aligned.append(left_lines[i1 + k])
                    right_aligned.append(right_lines[j1 + k])
            elif tag == 'replace':
                left_block = left_lines[i1:i2]
                right_block = right_lines[j1:j2]
                max_len = max(len(left_block), len(right_block))
                for k in range(max_len):
                    left_aligned.append(left_block[k] if k < len(left_block) else "")
                    right_aligned.append(right_block[k] if k < len(right_block) else "")
            elif tag == 'delete':
                for k in range(i1, i2):
                    left_aligned.append(left_lines[k])
                    right_aligned.append("")
            elif tag == 'insert':
                for k in range(j1, j2):
                    left_aligned.append("")
                    right_aligned.append(right_lines[k])

        left_result_text = "\n".join(left_aligned)
        right_result_text = "\n".join(right_aligned)
        self.text_left_result.setPlainText(left_result_text)
        self.text_right_result.setPlainText(right_result_text)

        self.text_left_result.set_diff_selections([])
        self.text_right_result.set_diff_selections([])
        left_selections = []
        right_selections = []
        delete_format = QTextCharFormat()
        delete_format.setBackground(QColor(220, 50, 50))
        delete_format.setForeground(Qt.white)
        insert_format = QTextCharFormat()
        insert_format.setBackground(QColor(50, 180, 50))
        insert_format.setForeground(Qt.black)
        replace_format = QTextCharFormat()
        replace_format.setBackground(QColor(250, 200, 50))
        replace_format.setForeground(Qt.black)

        for line_idx, (l_line, r_line) in enumerate(zip(left_aligned, right_aligned)):
            if not l_line and not r_line:
                continue
            if l_line and not r_line:
                self._add_line_selection(True, line_idx, l_line, delete_format, left_selections)
                continue
            if not l_line and r_line:
                self._add_line_selection(False, line_idx, r_line, insert_format, right_selections)
                continue

            line_matcher = SequenceMatcher(None, l_line, r_line)
            for op, a_start, a_end, b_start, b_end in line_matcher.get_opcodes():
                if op == 'equal':
                    continue
                if op in ('delete', 'replace'):
                    self._add_char_selection(True, line_idx, a_start, a_end - a_start,
                                             delete_format if op == 'delete' else replace_format, left_selections)
                if op in ('insert', 'replace'):
                    self._add_char_selection(False, line_idx, b_start, b_end - b_start,
                                             insert_format if op == 'insert' else replace_format, right_selections)

        self.text_left_result.set_diff_selections(left_selections)
        self.text_right_result.set_diff_selections(right_selections)
        self.main_window.status_bar.showMessage(TRANSLATIONS[self.main_window.current_lang]["status_comp_done"], 3000)

    def _add_line_selection(self, flag: bool, line_idx: int, line_text: str, format1: QTextCharFormat,
                            selections_list: List[QTextEdit.ExtraSelection]):
        editor = self.text_left_result if flag else self.text_right_result
        doc = editor.document()
        block = doc.findBlockByNumber(line_idx)
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(line_text))
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format = format1
        selections_list.append(selection)

    def _add_char_selection(self, flag: bool, line_idx: int, col_start: int, length: int, format1: QTextCharFormat,
                            selections_list: List[QTextEdit.ExtraSelection]):
        if length <= 0:
            return
        editor = self.text_left_result if flag else self.text_right_result
        doc = editor.document()
        block = doc.findBlockByNumber(line_idx)
        if not block.isValid():
            return
        start_pos = block.position() + col_start
        cursor = QTextCursor(doc)
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format = format1
        selections_list.append(selection)
