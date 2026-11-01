"""
@Time        : 2026/02/12
@Author      : zhuhezhang
@Version     : v1
@Description : 基于 PySide6 和 difflib 实现的文本差异对比工具。
                1.所有编辑区均显示行号，结果区滚动条会同步滚动，便于对比查看；
                2.支持从多种编码格式的文本文件导入对比文本，编辑文本不会同步至文件保存；
                3.支持字体缩放、比较结果支持字符级高亮显示（红色-删除、绿色-新增、黄色-修改）；
                4.可以通过拖动分割条调整四个文本区域的大小，双击分割条后可恢复至默认比例；
                5.除了菜单栏显示的快捷键，还支持 Ctrl/Cmd 鼠标滚轮缩放字体；
                6.支持搜索替换，搜索替换对象为焦点所在。选中文本时打开搜索替换框，选中的内容会自动粘贴到搜素框，搜索替换结果会显示在下方的状态栏。
                  当焦点在搜索输入框时按回车会执行查找下一个，焦点在替换输入框时按回车会执行替换；
                7.查找替换模式支持大小写匹配、全词匹配、正则表达式，使用正则表达式并且输入的正则表达式错误时，错误原因会显示在状态栏，搜索框文本
                  同步变红。
@Update      : 2026/03/09 V1.1 优化搜索替换体验。当输入的正则表达式错误，搜索替换的按钮和菜单均为变为不可用
             : 2026/03/22 V1.2 支持切换中英文界面
Linux安装pip和venv虚拟环境：sudo apt-get install python3-pip、sudo apt install python3.13-venv
Linux创建虚拟环境：python3 -m venv .venv
Windows/Linux进入虚拟环境：.venv/Scripts/activate、source .venv/bin/activate

以下nuitka打包命令是打包成一个独立运行的程序，同时不显示cmd控制窗口、清理打包生成的临时文件、指定产品名称、指定产品版本。
对于 PySide6 程序，建议加上 --nofollow-import-to=tkinter 减小打包体积，因为 PySide6 有时会误带入不必要的 Tkinter 依赖，
同时要 pip install zstandard 来压缩--onefile模式生成可执行文件的大小。但是用nuitka打包成单个文件容易被识别为病毒，所以用nuitka的话不建议--onefile模式
Windows nuitka打包：python -m nuitka --standalone --onefile --remove-output --enable-plugin=pyside6 --windows-console-mode=disable --nofollow-import-to=tkinter --product-name=文本对比工具 --product-version=1.2 main.py
Linux nuitka打包：python -m nuitka --standalone --onefile --remove-output --enable-plugin=pyside6 --nofollow-import-to=tkinter --product-name=文本对比工具 --product-version=1.2 main.py

Windows/Linux pyinstaller打包：pyinstaller -F -w main.py
"""
from sys import exit, argv, platform
from difflib import SequenceMatcher
from typing import List, Optional
from charset_normalizer import from_bytes
from PySide6.QtCore import Qt, Signal, QRegularExpression, QTimer
from PySide6.QtGui import (
    QFont, QTextCursor, QTextCharFormat, QAction, QPainter, QColor,
    QKeySequence, QTextDocument, QGuiApplication
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QTextEdit, QFileDialog, QLabel, QSplitter, QStatusBar,
    QMessageBox, QDialog, QLineEdit, QCheckBox, QPushButton, QGridLayout, QSplitterHandle
)

# --- 语言配置字典 ---
TRANSLATIONS = {
    "zh": {
        "win_title": "文本对比工具",
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
        "about_msg": ("作者: zhuhezhang\n"
                      "时间: 2026年3月22日\n"
                      "版本: V1.2\n"
                      "介绍: 基于 PySide6 和 difflib 实现的文本差异对比工具\n"
                      "  1. 所有编辑区均显示行号，结果区滚动条会同步滚动，便于对比查看；\n"
                      "  2. 支持从多种编码格式的文本文件导入对比文本，编辑文本不会同步至文件保存；\n"
                      "  3. 支持字体缩放、比较结果支持字符级高亮显示（红色-删除、绿色-新增、黄色-修改）；\n"
                      "  4. 可以通过拖动分割条调整四个文本区域的大小，双击分割条后可恢复至默认比例；\n"
                      "  5. 除了菜单栏显示的快捷键，还支持 {shortcut} + 鼠标滚轮缩放字体；\n"
                      "  6. 支持搜索替换，搜索替换对象为焦点所在。选中文本时打开搜索替换框，选中的内容会自动粘贴到搜素框，搜索替换结果会显示在下方的状态栏。"
                      "当焦点在搜索输入框时按回车会执行查找下一个，焦点在替换输入框时按回车会执行替换；\n"
                      "  7. 查找替换模式支持大小写匹配、全词匹配、正则表达式，使用正则表达式并且输入的正则表达式错误时，"
                      "错误原因会显示在状态栏、搜索框文本同步变红、搜索替换按钮和菜单变为不可用；\n"
                      "  8. 支持切换中英文界面。")
    },
    "en": {
        "win_title": "Text Comparison Tool",
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
        "about_msg": ("Author: zhuhezhang\n"
                      "Date: March 22, 2026\n"
                      "Version: V1.2\n"
                      "Description: A text difference comparison tool based on PySide6 and difflib\n"
                      " 1. Line numbers are displayed in all editing areas, and the scrollbars in the result area sync for easier comparison;\n"
                      " 2. Supports importing comparison text from files in various encoding formats; editing the text does not sync back to the file for saving;\n"
                      " 3. Supports font scaling; comparison results feature character-level highlighting (red for deletions, green for additions, yellow for modifications);\n"
                      " 4. Allows resizing the four text areas by dragging the splitters; double-clicking a splitter restores the default proportions;\n"
                      " 5. In addition to the shortcuts displayed in the menu bar, supports {shortcut} + mouse wheel for font scaling;\n"
                      " 6. Supports search and replace, targeting the focused area. When text is selected, opening the search and replace box will automatically"
                      "paste the selected content into the search field; search and replace results are displayed in the status bar at the bottom. "
                      "Pressing Enter while focused on the search input performs a search for the next occurrence; pressing Enter while focused on the replace input performs a replacement;\n"
                      " 7. The search and replace mode supports case matching, whole word matching, and regular expressions. When using regular expressions and an invalid expression is entered, "
                      "the error message will be displayed in the status bar, the search box text will turn red simultaneously, and the search/replace buttons and menu items will become disabled.\n"
                      " 8. Supports switching between Chinese and English interfaces.")
    }
}

DEFAULT_FONT_SIZE = 10  # 默认字体大小
if platform == "darwin":
    DEFAULT_FONT_SIZE = 15
MIN_FONT_SIZE = 5  # 最小字体大小
MAX_FONT_SIZE = 25  # 最大字体大小


# 视口理解：想象你面前有一张巨大的世界地图（这就是文档），但你手上只有一个小相框（这就是视口）。
# 你只能通过这个相框看到地图的一部分。当你移动相框（即滚动），你看到的地图区域就会变化。
# 也就是说视口就是你当前看到的窗口


class ResetHandle(QSplitterHandle):
    """自定义分割条句柄，支持双击重置。在 GUI 交互中，单点击分割条通常用于准备拖动，因此最合理的操作是双击分割条句柄（Handle）来重置比例。\n

    分割器和分割条句柄之间的关系:\n
    简单来说，QSplitter（分割器）是整个容器的“大脑”，而 QSplitterHandle（分割条句柄）则是它伸出去的“触角”或者说是“把手”。\n
    可以把它们的关系理解为 “框架”与“零件” 的关系：\n

    1. 形象的比喻：滑轨门\n
    QSplitter（分割器）： 相当于整套滑轨门系统。它负责规划空间，决定门（子控件）是横着排还是竖着排，以及每扇门能开多大。\n
    QSplitterHandle（分割条句柄）： 相当于门与门之间的那个缝隙里的拉手。你手摸到的、拽动的那个实实体就是句柄。\n

    2. 它们的核心关系\n
    包含关系：谁是谁的谁？\n
    每个 QSplitter 内部会自动管理句柄。如果你在分割器里放了 N 个按钮，它就会自动创建 N-1 个句柄插在它们中间。\n
    句柄不能脱离分割器独立存在，它的唯一使命就是为了让用户能通过它来操作分割器。\n
    分工合作：谁在干活？\n
    句柄（Handle）负责感知：它专门监听鼠标的“压下”、“拖拽”和“双击”事件。\n
    分割器（Splitter）负责计算：当句柄被拖动了 10 个像素时，它会告诉分割器：“老板，用户往左拽了 10 像素。”分割器接着就会重新计算左边控件和右边控件的宽度，并刷新显示。\n

    3. 为什么在代码里要分别重写它们？\n
    QSplitter 本身并不会直接告诉你“用户双击了分割线”。\n
    为什么要自定义 Handle？ 因为“双击”这个动作发生在“把手”上，而不是发生在背景板上。所以我们需要定制一个 ResetHandle 来专门捕捉这个双击信号。\n
    为什么要自定义 Splitter？ 当 Handle 捕捉到双击后，它需要找人去“重置比例”。虽然 Handle 知情，但它没有权限去改动其他控件的大小。
    它必须回头调用父类 ResetSplitter 里的 reset_layout 方法，让“大脑”来执行真正的尺寸分配。\n

    技术小细节\n
    在 Qt 的源码里，QSplitter 有一个虚函数叫 createHandle()。每当分割器需要一个新的分割条时，它都会调用这个函数。
    这就是为什么我们重写 createHandle() 就能把官方默认的“死板把手”换成我们支持双击的“智能把手”的原因。"""

    def mouseDoubleClickEvent(self, event):
        """当双击分割条时，触发父级 splitter 的重置方法。
        这里也可以直接使用self.splitter().reset_layout()这一行代码就行，但是IDE会提示reset_layout方法不存在。
        这是因为IDE 看到的是：“你从一个普通的 QSplitter 里调用了一个它没有的方法！”所以它会发出警告。但因为 Python 是动态语言，
        在程序实际运行时，这个 splitter() 返回的确实是定义的 ResetSplitter 实例，所以功能完全正常。\n

        这就像是你手里拿着一个“水果篮子”（QSplitter），IDE 只知道它是篮子。你非要从篮子里拿出一个“苹果”（reset_layout），
        IDE 怕你拿不到会尴尬，所以提醒你。通过上面的修改，你告诉 IDE：“放心，这个篮子是我定制的苹果专供篮子（ResetSplitter）。”
        """
        s = self.splitter()  # 获取 splitter 对象，使用类型检查在 ResetHandle 中显式指定类型
        if isinstance(s, ResetSplitter):  # 告诉 IDE：虽然官方说这是 QSplitter，但我敢保证它是 ResetSplitter才不会有警告
            s.reset_layout()


class ResetSplitter(QSplitter):
    """支持比例重置的分割器"""

    def __init__(self, orientation, weights=None, parent=None):
        super().__init__(orientation, parent)
        self.weights = weights if weights else [1, 1]  # 存储默认权重比例，例如 [1, 1] 或 [1, 2]

    def createHandle(self):
        """覆盖此方法以使用自定义句柄。\n
        句柄劫持：通过 createHandle 替换了原生的分割线对象，这是 Qt 中深度定制 QSplitter 的标准做法"""
        return ResetHandle(self.orientation(), self)

    def reset_layout(self):
        """根据初始权重重新计算各部分尺寸。\n
        比例自适应：reset_layout 方法会获取当前窗口的总像素高度/宽度，
        并根据设置的 weights（如 1:2）动态计算像素值，确保无论窗口多大都能完美恢复比例"""
        total_size = sum(self.sizes())
        if total_size <= 0:
            return

        total_weight = sum(self.weights)
        new_sizes = [int(total_size * w / total_weight) for w in self.weights]  # 按权重分配像素大小
        self.setSizes(new_sizes)


class TextCompareTool(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.current_lang = "zh"  # 默认语言-中文
        self.resize(1300, 800)
        self.current_font_size = DEFAULT_FONT_SIZE  # 当前界面字号
        self.current_editor = None  # 保存当前搜索查找的对象，始终存储 QPlainTextEdit 实例或 None
        self.find_dialog = FindReplaceDialog(self)  # 搜索替换对话框
        self.status_bar = None  # 状态栏
        self._init_ui()  # 主界面UI构建
        self._center()  # 使主界面屏幕居中
        self._setup_context_menus()  # 设置右键菜单

    def _init_ui(self):
        """主界面UI构建"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        menubar = self.menuBar()  # 菜单栏（文件、编辑、比较、视图、语言、帮助）

        # 文件菜单
        self.menu_file = menubar.addMenu("")
        self.action_open_left = QAction("", self)
        self.action_open_left.triggered.connect(lambda: self._open_file(self.text_left_input))  # noqa 忽略告警Cannot find reference 'connect' in 'Signal | function'
        self.action_open_right = QAction("", self)
        self.action_open_right.triggered.connect(lambda: self._open_file(self.text_right_input))  # noqa
        self.action_exit = QAction("", self)
        self.action_exit.setMenuRole(QAction.MenuRole.NoRole)  # 禁用默认行为，避免在macOS中出现不符合代码本身的不可控行为
        self.action_exit.triggered.connect(self.close)  # noqa
        self.menu_file.addAction(self.action_open_left)
        self.menu_file.addAction(self.action_open_right)
        self.menu_file.addSeparator()  # 添加菜单子项之间的横线
        self.menu_file.addAction(self.action_exit)

        # 编辑菜单
        self.menu_edit = menubar.addMenu("")
        self.action_find = QAction("", self)
        self.action_find.triggered.connect(self._show_find_dialog)  # noqa
        self.action_find.setShortcut(QKeySequence.Find)  # 快捷键设置
        self.action_find_next = QAction("", self)
        self.action_find_next.triggered.connect(self._find_next)  # noqa
        self.action_find_next.setShortcut(QKeySequence.FindNext)
        self.action_find_prev = QAction("", self)
        self.action_find_prev.triggered.connect(self._find_prev)  # noqa
        self.action_find_prev.setShortcut(QKeySequence.FindPrevious)
        self.action_replace = QAction("", self)
        self.action_replace.triggered.connect(self._show_replace_dialog)  # noqa
        if platform == "darwin":  # 默认的替换快捷键Cmd+H在MacOS中冲突，需要定义成其他
            self.action_replace.setShortcut("Ctrl+T")
        else:
            self.action_replace.setShortcut(QKeySequence.Replace)
        self.menu_edit.addAction(self.action_find)
        self.menu_edit.addAction(self.action_find_next)
        self.menu_edit.addAction(self.action_find_prev)
        self.menu_edit.addSeparator()
        self.menu_edit.addAction(self.action_replace)

        # 比较菜单
        self.menu_compare = menubar.addMenu("")
        self.action_compare = QAction("", self)
        self.action_compare.triggered.connect(self._compare_texts)  # noqa
        self.action_compare.setShortcut("Ctrl+R")
        self.menu_compare.addAction(self.action_compare)

        # 视图菜单（字体缩放）
        self.menu_view = menubar.addMenu("")
        self.action_zoom_in = QAction("", self)
        self.action_zoom_in.triggered.connect(self.zoom_in)  # noqa
        self.action_zoom_in.setShortcut("Ctrl+=")  # Ctrl+= / Cmd+=
        self.action_zoom_out = QAction("", self)
        self.action_zoom_out.triggered.connect(self.zoom_out)  # noqa
        self.action_zoom_out.setShortcut(QKeySequence.ZoomOut)  # Ctrl+- / Cmd+-
        self.action_zoom_reset = QAction("", self)
        self.action_zoom_reset.triggered.connect(self._zoom_reset)  # noqa
        self.action_zoom_reset.setShortcut("Ctrl+0")
        self.menu_view.addAction(self.action_zoom_in)
        self.menu_view.addAction(self.action_zoom_out)
        self.menu_view.addAction(self.action_zoom_reset)

        # 语言菜单
        self.menu_lang = menubar.addMenu("")
        self.action_lang_zh = QAction("简体中文", self)
        self.action_lang_en = QAction("English", self)
        self.action_lang_zh.triggered.connect(lambda: self._switch_language("zh"))  # noqa
        self.action_lang_en.triggered.connect(lambda: self._switch_language("en"))  # noqa
        self.menu_lang.addAction(self.action_lang_zh)
        self.menu_lang.addAction(self.action_lang_en)

        # 帮助菜单
        self.menu_help = menubar.addMenu("")
        self.action_about = QAction("", self)
        self.action_about.setMenuRole(QAction.MenuRole.NoRole)  # 禁用默认行为，避免在macOS中出现不符合代码本身的不可控行为
        self.action_about.triggered.connect(self._show_about)  # noqa
        self.menu_help.addAction(self.action_about)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        vertical_splitter = ResetSplitter(Qt.Vertical, weights=[1, 2])  # 垂直分割器（设为 1:2 权重）
        input_splitter = ResetSplitter(Qt.Horizontal, weights=[1, 1])  # 上方输入区域（设为 1:1 权重）
        self.text_left_input = LineNumberPlainTextEdit(self)
        self.text_right_input = LineNumberPlainTextEdit(self)
        input_splitter.addWidget(self.text_left_input)
        input_splitter.addWidget(self.text_right_input)
        result_splitter = ResetSplitter(Qt.Horizontal, weights=[1, 1])  # 下方结果区域（设为 1:1 权重，水平分割、只读）
        self.text_left_result = LineNumberPlainTextEdit(self)
        self.text_right_result = LineNumberPlainTextEdit(self)
        for editor in (self.text_left_result, self.text_right_result):
            editor.setReadOnly(True)
        result_splitter.addWidget(self.text_left_result)
        result_splitter.addWidget(self.text_right_result)

        vertical_splitter.addWidget(input_splitter)
        vertical_splitter.addWidget(result_splitter)
        # 注意：使用 ResetSplitter 后，不再需要单独调用 setStretchFactor，
        # 因为我们的 reset_layout 会接管比例逻辑。
        # 但为了初始化显示正确，可以先手动调用一次重置。
        vertical_splitter.setStretchFactor(0, 1)  # 上下高度所占比例为1：2
        vertical_splitter.setStretchFactor(1, 2)
        main_layout.addWidget(vertical_splitter)

        self._connect_focus_signals()  # 焦点信号连接，用于确认查找替换对象
        self._sync_scrollbars()  # 下方结果区域滚动条同步
        self._retranslate_ui()  # 初次加载翻译

    def _switch_language(self, lang_code: str):
        """切换语言

        :param lang_code: zh表示中文；en表示英文"""
        self.current_lang = lang_code
        self._retranslate_ui()
        self.find_dialog.retranslate_ui()

    def _retranslate_ui(self):
        """翻译所有UI组件"""
        tr = TRANSLATIONS[self.current_lang]
        self.setWindowTitle(tr["win_title"])
        self.menu_file.setTitle(tr["menu_file"])
        self.action_open_left.setText(tr["action_open_left"])
        self.action_open_right.setText(tr["action_open_right"])
        self.action_exit.setText(tr["action_exit"])

        self.menu_edit.setTitle(tr["menu_edit"])
        self.action_find.setText(tr["action_find"])
        self.action_find_next.setText(tr["action_find_next"])
        self.action_find_prev.setText(tr["action_find_prev"])
        self.action_replace.setText(tr["action_replace"])

        self.menu_compare.setTitle(tr["menu_compare"])
        self.action_compare.setText(tr["action_compare"])

        self.menu_view.setTitle(tr["menu_view"])
        self.action_zoom_in.setText(tr["action_zoom_in"])
        self.action_zoom_out.setText(tr["action_zoom_out"])
        self.action_zoom_reset.setText(tr["action_zoom_reset"])

        self.menu_lang.setTitle(tr["menu_lang"])

        self.menu_help.setTitle(tr["menu_help"])
        self.action_about.setText(tr["action_about"])

        self.text_left_input.setPlaceholderText(tr["placeholder_orig"])
        self.text_right_input.setPlaceholderText(tr["placeholder_mod"])
        self.text_left_result.setPlaceholderText(tr["placeholder_result_of_orig"])
        self.text_right_result.setPlaceholderText(tr["placeholder_result_of_mod"])
        self.text_left_input.setToolTip(tr["placeholder_orig"])
        self.text_right_input.setToolTip(tr["placeholder_mod"])
        self.text_left_result.setToolTip(tr["placeholder_result_of_orig"])
        self.text_right_result.setToolTip(tr["placeholder_result_of_mod"])
        for text_input in [self.text_left_input, self.text_right_input, self.text_left_result, self.text_right_result]:
            text_input.viewport().update()  # 解决切换中英文时，文本输入框的placeholder的值无法正常显示，需要主界面失去焦点时才能刷新的问题

        self.status_bar.showMessage(tr["status_ready"])

    def _center(self):
        """使主界面在屏幕居中"""
        screen = QGuiApplication.primaryScreen().availableGeometry()
        size = self.geometry()
        self.move(int((screen.width() - size.width()) / 2), int((screen.height() - size.height()) / 2))

    def _setup_context_menus(self):
        """添加文本框的右键菜单"""
        editors = [
            self.text_left_input, self.text_right_input,
            self.text_left_result, self.text_right_result
        ]
        for editor in editors:
            editor.setContextMenuPolicy(Qt.CustomContextMenu)
            # 当用户通过右键点击（或键盘快捷键）请求弹出上下文菜单时，信号customContextMenuRequested被发射
            # 定义了一个匿名函数，它接受两个参数：pos（由信号传入，右键点击时鼠标在控件内的相对坐标（相对于控件左上角））和 e（带有默认值 editor）。
            # 当信号触发时，它会调用 self._show_editor_context_menu(e, pos)
            editor.customContextMenuRequested.connect(
                lambda pos, e=editor: self._show_editor_context_menu(e, pos))

    def _show_editor_context_menu(self, editor: QPlainTextEdit, pos):
        """右键菜单具体实现

        :param editor: 触发信号的编辑器
        :param pos: 鼠标相对控件的坐标"""
        tr = TRANSLATIONS[self.current_lang]
        menu = editor.createStandardContextMenu()
        menu.addSeparator()
        find_action = menu.addAction(tr["action_find"])
        find_action.triggered.connect(lambda: self._show_find_dialog(editor))  # Noqa
        if not editor.isReadOnly():
            replace_action = menu.addAction(tr["action_replace"])
            replace_action.triggered.connect(lambda: self._show_replace_dialog(editor))  # Noqa
        menu.exec(editor.mapToGlobal(pos))  # 将相对坐标转换为全局屏幕坐标，以便在正确位置显示菜单

    def _connect_focus_signals(self):
        """为上下左右四个文本框绑定焦点事件，用于确认查找替换对象"""
        editors = [
            self.text_left_input, self.text_right_input,
            self.text_left_result, self.text_right_result
        ]
        for editor in editors:
            editor.focusReceived.connect(self._on_editor_focused)

    def _on_editor_focused(self, editor: QPlainTextEdit):
        """安全更新当前焦点编辑器：只接受 QPlainTextEdit 实例

        :param editor: 触发信号的编辑器"""
        if isinstance(editor, QPlainTextEdit):
            self.current_editor = editor
            if self.find_dialog.isVisible():
                self.find_dialog.set_editor(editor)

    def _sync_scrollbars(self):
        """同步下方结果区域的滚动（同步滚动水平和垂直滚动条）"""
        left_ver_scroll = self.text_left_result.verticalScrollBar()  # 获取左边垂直滚动条
        left_hor_scroll = self.text_left_result.horizontalScrollBar()
        right_ver_scroll = self.text_right_result.verticalScrollBar()
        right_hor_scroll = self.text_right_result.horizontalScrollBar()

        def sync_ver_left(value):  # 右边垂直滚动条不等于左边，则设置右边的等于左边
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

        left_ver_scroll.valueChanged.connect(sync_ver_left)  # 左边垂直滚动条绑定滚动事件处理函数
        left_hor_scroll.valueChanged.connect(sync_hor_left)
        right_ver_scroll.valueChanged.connect(sync_ver_right)
        right_hor_scroll.valueChanged.connect(sync_hor_right)

    def zoom_in(self):
        """放大字体"""
        new_size = min(MAX_FONT_SIZE, self.current_font_size + 1)
        self._apply_font_size_to_all_editors(new_size)

    def zoom_out(self):
        """缩小字体"""
        new_size = max(MIN_FONT_SIZE, self.current_font_size - 1)
        self._apply_font_size_to_all_editors(new_size)

    def _zoom_reset(self):
        """恢复初始字体大小"""
        self._apply_font_size_to_all_editors(DEFAULT_FONT_SIZE)

    def _apply_font_size_to_all_editors(self, size: int):
        """字体缩放核心方法，统一设置所有编辑器字体大小，并更新行号边距

        :param size: 字体大小"""
        editors = [
            self.text_left_input, self.text_right_input,
            self.text_left_result, self.text_right_result
        ]
        for editor in editors:  # 逐个设置上下左右四个编辑器字体的大小
            font = editor.font()
            font.setPointSize(size)
            editor.setFont(font)
            editor.update_line_number_width()
        self.current_font_size = size

    def _show_about(self):
        """工具使用说明对话框界面"""
        tr = TRANSLATIONS[self.current_lang]
        if platform == "darwin":  # macOS
            shortcut = "Ctrl/Cmd"
        else:
            shortcut = "Ctrl"
        QMessageBox.about(self, tr["action_about"], tr["about_msg"].format(shortcut=shortcut))

    def _open_file(self, text_edit: QPlainTextEdit):
        """打开文件对话框，并将选择的文本文件内容读取到文本框

        :param text_edit: 上边的左/右编辑器对象"""
        tr = TRANSLATIONS[self.current_lang]
        file_path, _ = QFileDialog.getOpenFileName(self, tr["open_text_file"], "", tr["open_text_file_mode"])
        if not file_path:
            return

        try:
            with open(file_path, 'rb') as f:  # 以二进制模式读取原始字节流数据
                raw_data = f.read()
            results = from_bytes(raw_data)  # 自动检测编码
            best_match = results.best()

            if best_match:  # 使用识别出的最佳编码进行解码
                content = str(best_match)
                text_edit.setPlainText(content)
                msg = tr["status_loading"].format(enc=best_match.encoding.upper(), path=file_path)
                self.status_bar.showMessage(msg)
        except Exception as e:
            QMessageBox.critical(self, tr["error"], tr["status_open_file"].format(e=e))

    def _show_find_dialog(self, editor=None):
        """打开查找替换窗口-查找

        :param editor: 触发信号的编辑器对象"""
        self._show_find_replace_dialog(editor)
        self.find_dialog.find_edit.setFocus()  # 将焦点设置到查找输入框

    def _show_replace_dialog(self, editor=None):
        """打开查找替换窗口-替换

        :param editor: 触发信号的编辑器对象"""
        self._show_find_replace_dialog(editor)
        self.find_dialog.replace_edit.setFocus()  # 将焦点设置到替换输入框

    def _show_find_replace_dialog(self, editor: QPlainTextEdit):
        """打开查找替换窗口

        :param editor: 触发信号的编辑器对象"""
        target = self._ensure_valid_editor(editor)  # 返回要查找替换的文本框对象
        self.find_dialog.set_editor(target)  # 设置要查找替换的文本框对象
        cursor = target.textCursor()  # 获取有效目标编辑器，设置对话框关联编辑器
        if cursor.hasSelection():  # 若当前编辑器有选中文本，自动填充到查找框
            self.find_dialog.find_edit.setText(cursor.selectedText())
        self.find_dialog.show()  # 确保对话框显示、置顶并激活
        self.find_dialog.raise_()
        self.find_dialog.activateWindow()

    def _find_next(self):
        """查找下一项"""
        if self.find_dialog.isVisible():  # 搜索替换对话框已打开则查找
            self.find_dialog.find_next()
        else:  # 若不可见但已有查找内容，则设置编辑器并执行查找
            if self.find_dialog.find_edit.text():
                target = self._ensure_valid_editor(self.current_editor)
                self.find_dialog.set_editor(target)
                self.find_dialog.find_next()
            else:
                self._show_find_dialog()

    def _find_prev(self):
        """查找上一项"""
        if self.find_dialog.isVisible():  # 搜索替换对话框已打开则查找
            self.find_dialog.find_prev()
        else:
            if self.find_dialog.find_edit.text():
                target = self._ensure_valid_editor(self.current_editor)
                self.find_dialog.set_editor(target)
                self.find_dialog.find_prev()
            else:
                self._show_find_dialog()

    def _ensure_valid_editor(self, editor: QPlainTextEdit):
        """查找替换接口（双重类型防护），优先返回传入的编辑器（若有效），否则返回当前焦点编辑器，若焦点编辑器无效则返回左侧输入框（永远有效）。杜绝因焦点信号误传布尔值等导致的崩溃。

        :param editor: 编辑器对象"""
        if isinstance(editor, QPlainTextEdit):
            return editor
        if isinstance(self.current_editor, QPlainTextEdit):
            return self.current_editor
        return self.text_left_input  # 最终保底

    def _compare_texts(self):
        """核心文本比较逻辑"""
        left_text = self.text_left_input.toPlainText()  # 获取左右输入编辑器的纯文本内容
        right_text = self.text_right_input.toPlainText()
        left_lines = left_text.splitlines()  # 按行分割，splitlines() 会保留空行
        right_lines = right_text.splitlines()
        matcher = SequenceMatcher(None, left_lines, right_lines)
        # 返回操作码列表，每个操作码为(tag, i1, i2, j1, j2)：
        # tag: 'equal', 'replace', 'delete', 'insert'
        # i1, i2: 左侧切片范围
        # j1, j2: 右侧切片范围
        opcodes = matcher.get_opcodes()
        left_aligned = []  # 左边原始文本比较结果文本内容
        right_aligned = []  # 右边修改后的文本比较结果文本内容

        for tag, i1, i2, j1, j2 in opcodes:  # 利用操作码列表使左右两边对比的文本行数一致，方便后面逐行对比
            if tag == 'equal':  # 相等：直接将左右行一一对应加入
                for k in range(i2 - i1):
                    left_aligned.append(left_lines[i1 + k])
                    right_aligned.append(right_lines[j1 + k])
            elif tag == 'replace':  # 替换：左右块行数可能不同，通过空行补全使行数相等，再逐行加入
                left_block = left_lines[i1:i2]
                right_block = right_lines[j1:j2]
                max_len = max(len(left_block), len(right_block))
                for k in range(max_len):
                    left_aligned.append(left_block[k] if k < len(left_block) else "")
                    right_aligned.append(right_block[k] if k < len(right_block) else "")
            elif tag == 'delete':  # 删除：左侧有内容，右侧补空行
                for k in range(i1, i2):
                    left_aligned.append(left_lines[k])
                    right_aligned.append("")
            elif tag == 'insert':  # 插入：左侧补空行，右侧有内容
                for k in range(j1, j2):
                    left_aligned.append("")
                    right_aligned.append(right_lines[k])

        # 将对齐后的行列表合并为字符串，分别设置到左右结果编辑器
        left_result_text = "\n".join(left_aligned)
        right_result_text = "\n".join(right_aligned)
        self.text_left_result.setPlainText(left_result_text)
        self.text_right_result.setPlainText(right_result_text)

        # 清除之前的高亮
        self.text_left_result.set_diff_selections([])
        self.text_right_result.set_diff_selections([])
        # 定义三种差异格式：删除：红底白字；新增：绿底黑字；修改：黄底黑字
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

        # zip将这两个列表“配对”，生成一个迭代器，每次迭代产生一个元组(left_aligned[i], right_aligned[i])。
        # 例如：left_aligned = ["a", "b", ""], right_aligned = ["a", "", "c"]，则zip会依次产生("a", "a"), ("b", ""), ("", "c")。
        # enumerate 为 zip 生成的每个元素添加一个索引（从 0 开始），返回一个包含 (索引, 元素) 的迭代器。
        # 对于上面的例子，enumerate 会产生：(0, ("a", "a")), (1, ("b", "")), (2, ("", "c"))。
        for line_idx, (l_line, r_line) in enumerate(zip(left_aligned, right_aligned)):  # 逐行处理
            if not l_line and not r_line:  # 若两侧均为空行，跳过
                continue
            if l_line and not r_line:  # 左侧有内容、右侧为空 → 左侧整行标记为删除
                self._add_line_selection(True, line_idx, l_line, delete_format, left_selections)
                continue
            if not l_line and r_line:  # 右侧有内容、左侧为空 → 右侧整行标记为新增
                self._add_line_selection(False, line_idx, r_line, insert_format, right_selections)
                continue

            # 两侧均非空：进行字符级差异比较
            line_matcher = SequenceMatcher(None, l_line, r_line)
            for op, a_start, a_end, b_start, b_end in line_matcher.get_opcodes():
                if op == 'equal':
                    continue
                if op in ('delete', 'replace'):  # 操作码若为delete或replace：在左侧编辑器对应位置添加高亮（删除用红色，替换用黄色）
                    self._add_char_selection(
                        True, line_idx, a_start, a_end - a_start,
                        delete_format if op == 'delete' else replace_format, left_selections)
                if op in ('insert', 'replace'):  # 操作码若为insert或replace：在右侧编辑器对应位置添加高亮（新增用绿色，替换用黄色）
                    self._add_char_selection(
                        False, line_idx, b_start, b_end - b_start,
                        insert_format if op == 'insert' else replace_format, right_selections)

        self.text_left_result.set_diff_selections(left_selections)  # 将收集好的高亮选区应用到编辑器
        self.text_right_result.set_diff_selections(right_selections)
        self.status_bar.showMessage(TRANSLATIONS[self.current_lang]["status_comp_done"], 3000)  # 状态栏显示“比较完成”持续 3 秒

    def _add_line_selection(self, flag: bool, line_idx: int, line_text: str, format1: QTextCharFormat,
                            selections_list: List[QTextEdit.ExtraSelection]):
        """为编辑器中的整行添加高亮格式

        :param flag: True表示下边左侧结果；False表示下边右侧结果
        :param line_idx: 行号
        :param line_text: 该行的文本内容
        :param format1: 文本格式-删除/新增/更新
        :param selections_list: 编辑器文本格式"""
        editor = self.text_left_result if flag else self.text_right_result
        doc = editor.document()
        block = doc.findBlockByNumber(line_idx)  # findBlockByNumber(line_idx)：根据行号（0-indexed）获取文档块（块理解成行）
        if not block.isValid():
            return
        cursor = QTextCursor(block)  # 创建光标并选中整行文本（从块首向右移动 len(line_text) 个字符）
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(line_text))
        selection = QTextEdit.ExtraSelection()  # 构造 ExtraSelection，设置光标和格式，添加到列表中（QTextEdit.ExtraSelection 同样适用于 QPlainTextEdit，此处直接使用）
        selection.cursor = cursor
        selection.format = format1
        selections_list.append(selection)

    def _add_char_selection(self, flag: bool, line_idx: int, col_start: int, length: int, format1: QTextCharFormat,
                            selections_list: List[QTextEdit.ExtraSelection]):
        """为编辑器中的部分字符添加高亮格式

        :param flag: True表示下边左侧结果；False表示下边右侧结果
        :param line_idx: 行号
        :param col_start: 该行的起始位置
        :param length: 要添加格式的文本长度
        :param format1: 文本格式-删除/新增/更新
        :param selections_list: 编辑器文本格式"""
        if length <= 0:
            return
        editor = self.text_left_result if flag else self.text_right_result
        doc = editor.document()
        block = doc.findBlockByNumber(line_idx)
        if not block.isValid():
            return
        start_pos = block.position() + col_start  # block.position()：块在整个文档中的起始位置（全局索引），start_pos = 块起始 + 列偏移
        cursor = QTextCursor(doc)
        cursor.setPosition(start_pos)  # 从 start_pos 开始向右选取 length 个字符形成选区
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format = format1
        selections_list.append(selection)


class LineNumberPlainTextEdit(QPlainTextEdit):
    """左侧带有行号的QPlainTextEdit，禁用自动换行，并可被主窗口追踪焦点"""
    focusReceived = Signal(object)  # 发射自身实例

    def __init__(self, main_window: TextCompareTool):
        super().__init__()
        self.main_window = main_window
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)  # 禁用自动换行，超出宽度的文本显示滚动条
        font_style = QFont()  # 文本界面字体样式
        font_style.setPointSize(DEFAULT_FONT_SIZE)
        self.setFont(font_style)
        self.diff_selections = []  # 区分差异高亮和全局搜索高亮，差异高亮
        self.search_selections = []  # 搜索高亮

        # 解决失去焦点时选中文本变灰看不清的问题
        # 每个组件的颜色组（即调色板，是 Qt 中控制控件颜色的核心对象，
        # 它定义了控件在不同状态下（如 “激活”、“失活”、“禁用”）各个部分（如背景、文字、选中高亮）的颜色）
        p = self.palette()
        # 将 “非激活状态（Inactive）” 下的 “选中背景色（Highlight）”，设置为和 “激活状态（Active）” 下的 “选中背景色”完全相同
        p.setColor(p.ColorGroup.Inactive, p.ColorRole.Highlight,
                   p.color(p.ColorGroup.Active, p.ColorRole.Highlight))
        # 将 “非激活状态（Inactive）” 下的 “选中文字颜色（HighlightedText）”，设置为和 “激活状态（Active）” 下的 “选中文字颜色”完全相同
        p.setColor(p.ColorGroup.Inactive, p.ColorRole.HighlightedText,
                   p.color(p.ColorGroup.Active, p.ColorRole.HighlightedText))
        self.setPalette(p)  # 设置当前组件调色板

        self.line_number_area = LineNumberArea(self)  # 创建行号区域实例，并将自身（self）传递给 LineNumberArea，以便其访问编辑器对象
        self.document().blockCountChanged.connect(self.update_line_number_width)  # 文档块数量（行数）变化时，重新计算行号宽度
        self.verticalScrollBar().valueChanged.connect(
            lambda v: self.line_number_area.update())  # 垂直滚动条位置变化时，刷新行号区域
        self.textChanged.connect(self.update_line_number_width)  # 文本内容变化时，可能引起行数变化，同样更新行号宽度
        self.update_line_number_width()  # 初始化时立即调用一次设置初始边距

    def set_diff_selections(self, selections: List[QTextEdit.ExtraSelection]):
        """单独设置差异高亮

        :param selections: 对比差异的文本样式"""
        self.diff_selections = selections
        self.setExtraSelections(self.diff_selections + self.search_selections)

    def highlight_search_text(self, text: str, case_sensitive: bool, whole_word: bool, use_regex: bool) -> List[QTextCursor]:
        """全局高亮所有搜索结果，返回匹配总数

        :param text: 要搜索的文本
        :param case_sensitive: 是否区分大小写
        :param whole_word: 是否全字匹配
        :param use_regex: 是否使用正则表达式
        :return: 所有的匹配光标"""
        self.search_selections.clear()
        match_cursors = []  # 用于存储所有的匹配光标，方便定位
        if text:
            doc = self.document()
            cursor = QTextCursor(doc)
            fmt = QTextCharFormat()
            if platform != "darwin":  # macOS中使用天蓝色会和选中颜色冲突看不清
                fmt.setBackground(QColor(135, 206, 235))  # 天蓝色作为全局搜索高亮，避开红绿黄
            else:
                fmt.setBackground(QColor(255, 153, 0))  # 暖橙色
            fmt.setForeground(Qt.black)

            # 核心：构建搜索匹配逻辑
            if use_regex:
                options = QRegularExpression.PatternOption.NoPatternOption
                if not case_sensitive:
                    options |= QRegularExpression.PatternOption.CaseInsensitiveOption
                pattern = text
                if whole_word:  # 如果勾选了全词匹配，给正则加上边界符 \b
                    pattern = f"\\b{text}\\b"
                regex = QRegularExpression(pattern, options)

                current_pos = 0
                while True:  # 开始在文档中循环查找正则匹配
                    match = regex.match(doc.toPlainText(), current_pos)
                    if not match.hasMatch():
                        break

                    match_cursor = QTextCursor(doc)  # 创建对应范围的光标
                    match_cursor.setPosition(match.capturedStart())
                    match_cursor.setPosition(match.capturedEnd(), QTextCursor.MoveMode.KeepAnchor)

                    selection = QTextEdit.ExtraSelection()
                    selection.cursor = match_cursor
                    selection.format = fmt
                    self.search_selections.append(selection)
                    match_cursors.append(match_cursor)

                    current_pos = match.capturedEnd()
                    if match.capturedLength() == 0:  # 防止死循环（比如正则匹配空字符）
                        current_pos += 1
            else:  # 不使用正则表达式
                flags = QTextDocument.FindFlag(0)
                if case_sensitive:  # 根据复选框增加大小写敏感、全词匹配标志
                    flags |= QTextDocument.FindFlag.FindCaseSensitively
                if whole_word:
                    flags |= QTextDocument.FindFlag.FindWholeWords

                while True:  # 循环查找匹配项
                    cursor = doc.find(text, cursor, flags)
                    if cursor.isNull():
                        break
                    selection = QTextEdit.ExtraSelection()
                    selection.cursor = cursor
                    selection.format = fmt
                    self.search_selections.append(selection)
                    match_cursors.append(QTextCursor(cursor))  # 复制一份光标
        self.setExtraSelections(self.diff_selections + self.search_selections)  # 合并差异高亮与搜索高亮
        return match_cursors

    def _line_number_width(self):
        """行号宽度计算"""
        digits = len(str(self.document().blockCount()))  # 获取文档总块数（即行数），计算最大行号的数字位数
        return 10 + self.fontMetrics().horizontalAdvance(
            '9') * digits  # 获取当前字体下字符 '9' 的像素宽度（等宽字体下所有数字等宽），左侧留白宽度 = 10（固定内边距） + 数字宽度 × 位数

    def update_line_number_width(self):
        """更新行号边距与重绘"""
        self.setViewportMargins(self._line_number_width(), 0, 0, 0)  # 设置编辑区域视口边距，左侧预留出行号绘制空间
        self.line_number_area.update()  # 同时刷新行号区域（强制重绘）

    def resizeEvent(self, event):
        """尺寸调整事件：重写 resizeEvent，在编辑器大小变化时同步调整行号区域的位置与尺寸

        :param event: 触发对象"""
        super().resizeEvent(event)
        cr = self.contentsRect()  # 获取内容矩形（不包括任何边距）
        self.line_number_area.setGeometry(
            cr.left(), cr.top(), self._line_number_width(),
            cr.height())  # 行号区域定位于内容矩形左侧，宽度为 line_number_width()，高度为内容高度

    def scrollContentsBy(self, dx, dy):
        """重写 scrollContentsBy，当编辑器内容滚动时，让行号区域也垂直滚动相同偏移量，保持行号与文本同步

        :param dx: 水平滚动大小
        :param dy: 垂直滚动大小"""
        super().scrollContentsBy(dx, dy)
        self.line_number_area.scroll(0, dy)

    def focusInEvent(self, event):
        """当编辑器获得焦点时，发射自定义信号 focusReceived，并传入自身实例，主窗口通过连接此信号追踪当前活动编辑器，用于查找替换默认目标

        :param event: 触发对象"""
        super().focusInEvent(event)
        self.focusReceived.emit(self)

    def wheelEvent(self, event):
        """重写监听滚轮事件，按下Ctrl/Cmd键+滚轮时字体放大缩小

        :param event: 触发对象"""
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):  # 修饰键检测Ctrl/Cmd
            delta = event.angleDelta().y()  # 返回垂直滚动角度，正值向上，负值向下
            if delta > 0:
                self.main_window.zoom_in()
            else:
                self.main_window.zoom_out()
        else:
            super().wheelEvent(event)


class LineNumberArea(QWidget):
    """行号绘制区域类"""

    def __init__(self, editor: LineNumberPlainTextEdit):
        """初始化函数

        :param editor: 调用者，即LineNumberPlainTextEdit类"""
        super().__init__(editor)  # 将 editor 作为父对象，确保行号区域悬浮于编辑器上方
        self.editor = editor

    def paintEvent(self, event):
        """只要行号区域的状态（位置、内容、可见性）发生变化，或者有外部请求，系统就会及时调用它来重新绘制行号

        :param event: 触发对象"""
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(240, 240, 240))  # 创建 QPainter，使用浅灰色（RGB 240,240,240）填充整个区域背景

        block = self.editor.firstVisibleBlock()  # 获取编辑器中第一个可见文本块（行）
        block_number = block.blockNumber()  # 当前块（行）的序号（从 0 开始）

        # 通过以下top和bottom两个值，通过这两个值，可以判断当前块是否位于需要绘制的区域内（event.rect()），
        # 从而决定是否绘制其行号。循环遍历从第一个可见块开始的后续块，利用这两个坐标逐块绘制行号，实现行号与文本的精确对齐。

        # 计算块在视口中的全局位置（考虑滚动偏移）
        # blockBoundingGeometry获取指定文本块block在整个文档坐标系中的边界矩形（包含位置和尺寸）。文档坐标系以文档左上角为原点
        # contentOffset()获取编辑器视口左上角相对于文档原点的偏移量（即滚动条滚动的距离）
        # translated将块的边界矩形平移减去该偏移量，从而将其转换到视口坐标系中（以视口左上角为原点）。平移后的矩形表示该块在视口中的可见位置（可能为负，表示块在视口上方）
        # top()取平移后矩形的顶部 y 坐标（相对于视口左上角）。这就是该块在视口中的起始垂直位置
        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
        # 直接获取该文本块的高度（不依赖坐标偏移）。将顶部坐标加上块高度，得到该块在视口中的底部垂直位置（相对于视口左上角）
        bottom = top + self.editor.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():  # 循环遍历从当前块开始的后续块，直到超出可视区域底部
            if block.isVisible() and bottom >= event.rect().top():  # 仅绘制可见且部分或全部位于重绘区域内的块的行号
                number = str(block_number + 1)  # 行号文本 = block_number + 1
                painter.setPen(Qt.darkGray)  # 画笔颜色 darkGray
                painter.drawText(
                    0, int(top), self.width() - 2,
                    self.editor.fontMetrics().height(),
                    Qt.AlignRight, number)  # 在矩形内右对齐绘制行号，参数分别是水平位置x、垂直位置y、宽度、高度（编辑器的字体高度）、对齐方向、绘制内容（行号）
            block = block.next()  # 获取下一个块
            top = bottom
            bottom = top + self.editor.blockBoundingRect(block).height()
            block_number += 1
        painter.end()


class FindReplaceDialog(QDialog):
    """查找/替换对话框（增加双重类型防护）"""

    def __init__(self, text_compare_tool: TextCompareTool):
        super().__init__(text_compare_tool)
        self.text_compare_tool = text_compare_tool
        self.setWindowTitle("查找和替换")
        self.setModal(False)  # 非模态，不阻塞主窗口
        self.editor: Optional[LineNumberPlainTextEdit] = None  # 始终为 QPlainTextEdit 实例或 None
        self.current_matches: List[QTextCursor] = []  # 存储当前所有匹配的光标
        self.setWindowFlag(Qt.WindowStaysOnTopHint)  # 保持搜索替换窗口在最顶层
        self.regex_error_flag = False  # 正则表达式是否错误标识

        self.find_label = QLabel("查找(&N):")  # 标签文本中的 (&N) 定义快捷键 Alt+N
        self.find_edit = QLineEdit()
        self.find_label.setBuddy(self.find_edit)  # setBuddy 将标签与输入框关联，按下 Alt+N 焦点跳至输入框

        self.replace_label = QLabel("替换为(&P):")
        self.replace_edit = QLineEdit()
        self.replace_label.setBuddy(self.replace_edit)

        self.case_check = QCheckBox("大小写匹配(&C)")
        self.whole_check = QCheckBox("全词匹配(&W)")
        self.regex_check = QCheckBox("正则表达式(&E)")

        self.replace_all_btn = QPushButton("全部替换(&A)")
        # 默认情况下，第一个被添加进去的按钮会被赋予 autoDefault 属性。这意味着当你按下回车键时，它会触发该按钮，且在视觉上它通常会有个深色边框，
        # 看起来像被“默认选中”了。这里取消全部默认按钮。
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
        # 第一、二行：查找标签 + 输入框（占4列）；替换标签 + 输入框
        grid.addWidget(self.find_label, 0, 0)  # 位置：0行0列
        grid.addWidget(self.find_edit, 0, 1, 1, 3)  # 位置：0行1列，大小：跨越1行3列
        grid.addWidget(self.replace_label, 1, 0)
        grid.addWidget(self.replace_edit, 1, 1, 1, 3)

        # 第三行：三个复选框 + 伸缩空间
        options_layout = QHBoxLayout()
        options_layout.addWidget(self.case_check)
        options_layout.addWidget(self.whole_check)
        options_layout.addWidget(self.regex_check)
        options_layout.addStretch()
        grid.addLayout(options_layout, 2, 0, 1, 4)

        # 第四行：五个按钮水平排列
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.replace_all_btn)
        btn_layout.addWidget(self.replace_btn)
        btn_layout.addWidget(self.find_prev_btn)
        btn_layout.addWidget(self.find_next_btn)
        btn_layout.addWidget(self.close_btn)
        grid.addLayout(btn_layout, 3, 0, 1, 4)
        self.setLayout(grid)

        self.default_palette = self.find_edit.palette()  # 保存搜索框初始调色板用于正则表达式校验通过时恢复默认样式
        self.error_palette = self.find_edit.palette()  # 预设一个红色调色板用于正则错误提示
        self.error_palette.setColor(self.error_palette.ColorRole.Text, QColor(220, 50, 50))

        self.replace_all_btn.clicked.connect(self.replace_all)  # noqa 忽略未发现connect方法告警
        self.replace_btn.clicked.connect(self.replace)  # noqa
        self.find_prev_btn.clicked.connect(self.find_prev)  # noqa
        self.find_next_btn.clicked.connect(self.find_next)  # noqa
        self.close_btn.clicked.connect(self.close)  # noqa
        self.find_edit.returnPressed.connect(self.find_next)  # noqa
        self.replace_edit.returnPressed.connect(self.replace)  # noqa
        self.find_edit.textChanged.connect(self._update_highlights)  # noqa
        self.case_check.stateChanged.connect(self._update_highlights)  # noqa
        self.whole_check.stateChanged.connect(self._update_highlights)  # noqa
        self.regex_check.stateChanged.connect(self._update_highlights)  # noqa

        self._update_button_state()  # 初始化按钮状态（根据当前 self.editor 是否只读和有效、正则表达式是否错误）
        self.retranslate_ui()

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
        """安全设置编辑器：只接受 QPlainTextEdit 实例

        :param editor: 编辑器"""
        if self.editor and self.editor != editor:  # 1. 如果有老编辑器，先清除老编辑器的搜索高亮和文本监听
            if hasattr(self.editor, 'highlight_search_text'):
                self.editor.highlight_search_text("", False, False, False)
            try:
                self.editor.textChanged.disconnect(self._update_highlights)  # noqa
            except Exception:
                pass
        if isinstance(editor, QPlainTextEdit):  # 2. 绑定新编辑器
            self.editor = editor
            self._update_highlights()  # 立即为新焦点编辑器应用高亮
            self.editor.textChanged.connect(self._update_highlights)  # 监听文本编辑，文本变化时实时刷新高亮
        else:
            self.editor = None
        self._update_button_state()  # 随后更新按钮状态

    def _update_highlights(self):
        """更新当前编辑器的搜索高亮、计算匹配总数并校验正则合法性"""
        if (self.editor is None) or (not hasattr(self.editor, 'highlight_search_text')) or (not self.isVisible()):
            self._update_statusbar_according_to_matches(0, 0)
            return

        text = self.find_edit.text()
        use_regex = self.regex_check.isChecked()

        if use_regex and text:
            re_test = QRegularExpression(text)
            if not re_test.isValid():  # 正则表达式合法性校验
                self.regex_error_flag = True
                self.find_edit.setPalette(self.error_palette)  # 语法错误：输入框背景变红，状态栏提示错误
                for btn in [self.replace_all_btn, self.replace_btn, self.find_prev_btn, self.find_next_btn]:
                    btn.setEnabled(False)  # 语法错误：查找替换按钮不可用
                for action in [self.text_compare_tool.action_find_next, self.text_compare_tool.action_find_prev]:
                    action.setEnabled(False)  # 语法错误：查找上一个/下一个菜单子项不可用
                error_msg = re_test.errorString()
                if hasattr(self.text_compare_tool, 'status_bar'):
                    msg = TRANSLATIONS[self.text_compare_tool.current_lang]["regex_error"].format(err=error_msg)
                    self.text_compare_tool.status_bar.showMessage(msg, 5000)
                self.current_matches = []
                self.editor.highlight_search_text("", False, False, False)  # 清除编辑器里的旧高亮
                return
        self.regex_error_flag = False
        self.find_edit.setPalette(self.default_palette)  # 校验通过或非正则模式：恢复默认初始调色板
        for btn in [self.replace_all_btn, self.replace_btn, self.find_prev_btn, self.find_next_btn]:
            btn.setEnabled(True)
        for action in [self.text_compare_tool.action_find_next, self.text_compare_tool.action_find_prev]:
            action.setEnabled(True)

        case_sens = self.case_check.isChecked()
        whole_word = self.whole_check.isChecked()
        self.current_matches = self.editor.highlight_search_text(text, case_sens, whole_word,
                                                                 use_regex)  # 执行高亮并获取所有匹配的光标列表
        self.refresh_status_index()  # 计算当前位置序号

    def refresh_status_index(self):
        """计算当前光标在所有匹配项中的位置"""
        total = len(self.current_matches)
        if total == 0:
            self._update_statusbar_according_to_matches(0, 0)
            return
        current_cursor = self.editor.textCursor()
        curr_pos = current_cursor.selectionStart()  # 获取编辑器当前光标位置

        index = 0
        for i, m_cursor in enumerate(self.current_matches):  # 找到第一个起始位置大于等于当前光标位置的匹配项
            if m_cursor.selectionStart() >= curr_pos:
                index = i + 1
                break
        if index == 0 and total > 0:  # 如果循环结束没找到（光标在最后），默认指向最后一个
            index = total
        self._update_statusbar_according_to_matches(index, total)

    def _update_statusbar_according_to_matches(self, index, total):
        """根据查找匹配项将信息显示到主界面的状态栏

        :param index: 当前查找项
        :param total: 查找匹配到的个数"""
        tr = TRANSLATIONS[self.text_compare_tool.current_lang]
        if self.find_edit.text() != "":
            if total == 0:
                msg = tr["msg_not_found"].format(text=self.find_edit.text())
            else:
                msg = tr["msg_index"].format(idx=index, total=total)
            if hasattr(self.text_compare_tool, 'status_bar'):
                self.text_compare_tool.status_bar.showMessage(msg, 5000)

    def _update_button_state(self):
        """根据编辑器有效性及只读状态、正则表达式是否错误更新替换按钮"""
        if self.editor is not None:  # 若编辑器为只读（结果区）或不存在，则禁用全部替换、替换按钮及替换输入框、标签
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
        """覆盖setVisible是处理macOS窗口显示/隐藏最可靠的方法，无论用户是按 Esc 键、点击关闭按钮、还是你在代码里调用 .hide()，setVisible(False) 都会执行。
        当visible为True时相当于showEvent，为False时相当于closeEvent/hideEvent。若是直接重写closeEvent和showEvent，在macOS中是不生效的，
        因为关闭窗口在macOS中是隐藏的，打开也只是激活显示隐藏窗口,因此并不会触发关闭和打开事件。

        :param visible: 标识窗口是否可见"""
        super().setVisible(visible)
        if visible:  # 窗口显示时：恢复高亮
            self._update_highlights()
        else:  # 窗口隐藏/关闭时：清除高亮、清除选中状态
            if self.editor and hasattr(self.editor, 'highlight_search_text'):
                self.editor.highlight_search_text("", False, False, False)  # 传入空字符串清除所有搜索高亮，保留 Diff 高亮
            if hasattr(self.text_compare_tool, 'status_bar'):  # 清除状态栏信息
                self.text_compare_tool.status_bar.clearMessage()
            cursor = self.editor.textCursor()
            cursor.clearSelection()  # 清除选中状态
            self.editor.setTextCursor(cursor)  # 将修改后的光标重新应用到控件上

    def find_next(self):
        """查找下一项"""
        if self.editor is None:
            return
        text = self.find_edit.text()
        if not text:
            return

        case_sens = self.case_check.isChecked()  # 使用和高亮一致的参数
        whole_word = self.whole_check.isChecked()
        use_regex = self.regex_check.isChecked()
        if use_regex:  # 正则跳转逻辑：在 current_matches 寻找下一个
            curr_pos = self.editor.textCursor().position()  # 获取编辑器当前光标位置
            target_cursor = None
            for m_cursor in self.current_matches:
                if m_cursor.selectionStart() > curr_pos:  # 找到第一个起始位置大于等于当前光标位置的匹配项
                    target_cursor = m_cursor
                    break
            if target_cursor is None and self.current_matches:  # 如果后面没了，回到第一个（循环查找）
                target_cursor = self.current_matches[0]
            if target_cursor:
                self.editor.setTextCursor(target_cursor)
        else:  # 普通跳转逻辑（原本的逻辑）
            flags = QTextDocument.FindFlag(0)  # 查找下一个标志
            if case_sens:  # 根据复选框增加大小写敏感、全词匹配标志
                flags |= QTextDocument.FindFlag.FindCaseSensitively  # 按位或运算：只要对应的二个二进位有一个为1时，结果位就为1
            if whole_word:
                flags |= QTextDocument.FindFlag.FindWholeWords

            # 从当前光标位置开始查找，找到则选中并返回 True并选中找到的内容；未找到则返回文档开头继续查找，还是没找到则更新状态栏未找到
            if not self.editor.find(text, flags):
                cursor = self.editor.textCursor()  # 获取编辑器光标
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                self.editor.setTextCursor(cursor)
                self.editor.find(text, flags)

        self.refresh_status_index()

    def find_prev(self):
        """查找上一项（代码解释参考find_next函数）"""
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
        """替换单项"""
        if self.editor is None or self.editor.isReadOnly():
            return
        find_text = self.find_edit.text()
        if not find_text:
            return

        cursor = self.editor.textCursor()
        if cursor.hasSelection():  # 当前编辑器有选中区域则替换,否则直接执行查找并选中结果
            selected = cursor.selectedText()
            use_regex = self.regex_check.isChecked()

            if use_regex:  # 正则判定：检查选中文本是否完全符合正则
                options = QRegularExpression.PatternOption.NoPatternOption
                if not self.case_check.isChecked():
                    options |= QRegularExpression.PatternOption.CaseInsensitiveOption

                pattern = find_text
                if self.whole_check.isChecked():
                    pattern = f"\\b{find_text}\\b"  # 匹配一个单词边界，也就是指单词和空格间的位置。例如， 'er\b' 可以匹配"never" 中的 'er'，但不能匹配 "verb" 中的 'er'

                regex = QRegularExpression(f"^{pattern}$", options)  # 使用 ^$ 确保全匹配
                match = regex.match(selected).hasMatch()
            else:  # 普通文本判定,当前查找项等于选中结果才会替换
                if self.case_check.isChecked():
                    match = (selected == find_text)
                else:
                    match = (selected.lower() == find_text.lower())

            if match:
                cursor.insertText(self.replace_edit.text())  # 替换选中区域的文本

        self.find_next()
        self._update_highlights()

    def replace_all(self):
        """替换全部（支持正则表达式）"""
        if self.editor is None or self.editor.isReadOnly():
            return
        find_text = self.find_edit.text()
        replace_text = self.replace_edit.text()
        if not find_text:
            return
        self._update_highlights()  # 确保当前匹配列表是最新的
        if not self.current_matches:
            return

        cursor = self.editor.textCursor()
        cursor.beginEditBlock()  # 表示在文档中开始一组编辑操作，从撤销/重做角度来看，这些操作应被视为一个单一的操作
        count = len(self.current_matches)
        # 从后往前替换,为什么要倒序？因为替换 text -> text_long 会改变后面所有字符的 index。
        # 从后往前替换，前面的 index 依然保持准确。
        for m_cursor in reversed(self.current_matches):
            m_cursor.insertText(replace_text)  # 将编辑器光标移动到该匹配项并替换
        cursor.endEditBlock()  # 结束一组编辑操作

        if hasattr(self.text_compare_tool, 'status_bar'):
            msg = TRANSLATIONS[self.text_compare_tool.current_lang]["msg_replace_done"].format(count=count)
            self.text_compare_tool.status_bar.showMessage(msg)

        QTimer.singleShot(3000, self._update_highlights)  # 延时 3000 毫秒（3秒）后执行高亮和状态刷新，避免状态栏更新过快不显示替换完成的信息


if __name__ == "__main__":
    app = QApplication(argv)
    window = TextCompareTool()
    window.show()
    exit(app.exec())
