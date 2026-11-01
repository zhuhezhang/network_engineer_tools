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
Windows nuitka打包：python -m nuitka --standalone --onefile --remove-output --enable-plugin=pyside6 --windows-console-mode=disable --nofollow-import-to=tkinter --product-name=网络工程师工具 --product-version=1.2 main.py
Linux nuitka打包：python -m nuitka --standalone --onefile --remove-output --enable-plugin=pyside6 --nofollow-import-to=tkinter --product-name=网络工程师工具 --product-version=1.2 main.py

Windows/Linux pyinstaller打包：pyinstaller -F -w main.py
"""
from sys import exit, argv, platform
from PySide6.QtCore import Qt
from PySide6.QtGui import  QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, 
    QMainWindow, 
    QWidget, 
    QVBoxLayout, 
    QSplitter, 
    QStatusBar, 
    QPushButton, 
    QSplitterHandle, 
    QStackedWidget, 
    QSizePolicy
)
from text_compare_page import TextComparePage
from ip_calculator_page import IpCalculatorPage
from batch_ping_page import BatchPingPage
from network_ip_setup_page import NetworkIpSetupPage

# --- 语言配置字典 ---
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
        "nav_text_compare": "文本对比",
        "nav_ip_calculator": "IP地址计算",
        "nav_batch_ping": "批量ping",
        "nav_network_ip_set": "网卡IP地址设置",
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
        "nav_text_compare": "Text Compare",
        "nav_ip_calculator": "IP Calculator",
        "nav_batch_ping": "Batch Ping",
        "nav_network_ip_set": "NIC IP Settings",
    },
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
    """应用主窗口框架"""

    def __init__(self):
        super().__init__()
        self.current_lang = "zh"
        self.resize(1300, 800)
        self._init_ui()
        self._center()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 先创建页面，再绑定菜单事件，避免在初始化阶段访问尚未创建的 compare_page
        self.compare_page = TextComparePage(self)
        self.ip_page = IpCalculatorPage(self)
        self.ping_page = BatchPingPage(self)
        self.network_page = NetworkIpSetupPage(self)

        menubar = self.menuBar()

        self.menu_file = menubar.addMenu("")
        self.action_open_left = QAction("", self)
        self.action_open_left.triggered.connect(lambda: self.compare_page._open_file(self.compare_page.text_left_input))
        self.action_open_right = QAction("", self)
        self.action_open_right.triggered.connect(lambda: self.compare_page._open_file(self.compare_page.text_right_input))
        self.action_exit = QAction("", self)
        self.action_exit.setMenuRole(QAction.MenuRole.NoRole)
        self.action_exit.triggered.connect(self.close)
        self.menu_file.addAction(self.action_open_left)
        self.menu_file.addAction(self.action_open_right)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.action_exit)

        self.menu_edit = menubar.addMenu("")
        self.action_find = QAction("", self)
        self.action_find.triggered.connect(lambda: self.compare_page._show_find_dialog())
        self.action_find.setShortcut(QKeySequence.Find)
        self.action_find_next = QAction("", self)
        self.action_find_next.triggered.connect(lambda: self.compare_page._find_next())
        self.action_find_next.setShortcut(QKeySequence.FindNext)
        self.action_find_prev = QAction("", self)
        self.action_find_prev.triggered.connect(lambda: self.compare_page._find_prev())
        self.action_find_prev.setShortcut(QKeySequence.FindPrevious)
        self.action_replace = QAction("", self)
        self.action_replace.triggered.connect(lambda: self.compare_page._show_replace_dialog())
        if platform == "darwin":
            self.action_replace.setShortcut("Ctrl+T")
        else:
            self.action_replace.setShortcut(QKeySequence.Replace)
        self.menu_edit.addAction(self.action_find)
        self.menu_edit.addAction(self.action_find_next)
        self.menu_edit.addAction(self.action_find_prev)
        self.menu_edit.addSeparator()
        self.menu_edit.addAction(self.action_replace)

        self.menu_compare = menubar.addMenu("")
        self.action_compare = QAction("", self)
        self.action_compare.triggered.connect(lambda: self.compare_page._compare_texts())
        self.action_compare.setShortcut("Ctrl+R")
        self.menu_compare.addAction(self.action_compare)

        self.menu_view = menubar.addMenu("")
        self.action_zoom_in = QAction("", self)
        self.action_zoom_in.triggered.connect(lambda: self.compare_page.zoom_in())
        self.action_zoom_in.setShortcut("Ctrl+=")
        self.action_zoom_out = QAction("", self)
        self.action_zoom_out.triggered.connect(lambda: self.compare_page.zoom_out())
        self.action_zoom_out.setShortcut(QKeySequence.ZoomOut)
        self.action_zoom_reset = QAction("", self)
        self.action_zoom_reset.triggered.connect(lambda: self.compare_page._zoom_reset())
        self.action_zoom_reset.setShortcut("Ctrl+0")
        self.menu_view.addAction(self.action_zoom_in)
        self.menu_view.addAction(self.action_zoom_out)
        self.menu_view.addAction(self.action_zoom_reset)

        self.menu_lang = menubar.addMenu("")
        self.action_lang_zh = QAction("简体中文", self)
        self.action_lang_en = QAction("English", self)
        self.action_lang_zh.triggered.connect(lambda: self._switch_language("zh"))
        self.action_lang_en.triggered.connect(lambda: self._switch_language("en"))
        self.menu_lang.addAction(self.action_lang_zh)
        self.menu_lang.addAction(self.action_lang_en)

        self.menu_help = menubar.addMenu("")
        self.action_about = QAction("", self)
        self.action_about.triggered.connect(self._show_about)
        self.menu_help.addAction(self.action_about)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.nav_widget = QWidget()
        self.nav_widget.setMinimumWidth(180)
        self.nav_widget.setMaximumWidth(350)
        self.nav_layout = QVBoxLayout(self.nav_widget)
        self.nav_layout.setContentsMargins(10, 10, 5, 10)
        self.nav_layout.setSpacing(8)
        self.nav_layout.setAlignment(Qt.AlignTop)

        self.nav_buttons = {}
        self.nav_button_order = [
            "nav_text_compare",
            "nav_ip_calculator",
            "nav_batch_ping",
            "nav_network_ip_set",
        ]
        for item in self.nav_button_order:
            btn = QPushButton("")
            btn.setCheckable(True)
            btn.setAutoDefault(False)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked=False, key=item: self._on_nav_button_clicked(key))
            self.nav_layout.addWidget(btn)
            self.nav_buttons[item] = btn

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_widget = QStackedWidget()
        self.content_layout.addWidget(self.stacked_widget)

        self.stacked_widget.addWidget(self.compare_page)
        self.stacked_widget.addWidget(self.ip_page)
        self.stacked_widget.addWidget(self.ping_page)
        self.stacked_widget.addWidget(self.network_page)

        self.nav_splitter = QSplitter(Qt.Horizontal)
        self.nav_splitter.setChildrenCollapsible(False)
        self.nav_splitter.setHandleWidth(6)
        self.nav_splitter.addWidget(self.nav_widget)
        self.nav_splitter.addWidget(self.content_widget)
        self.nav_splitter.setSizes([210, 1090])

        main_layout.addWidget(self.nav_splitter)
        self.nav_buttons["nav_text_compare"].setChecked(True)
        self.stacked_widget.setCurrentIndex(0)
        self._update_nav_menus()
        self._retranslate_ui()

    def _on_nav_button_clicked(self, nav_key: str):
        index_map = {
            "nav_text_compare": 0,
            "nav_ip_calculator": 1,
            "nav_batch_ping": 2,
            "nav_network_ip_set": 3,
        }
        self.stacked_widget.setCurrentIndex(index_map.get(nav_key, 0))
        self._update_nav_menus()
        for key, btn in self.nav_buttons.items():
            btn.setChecked(key == nav_key)

    def _update_nav_menus(self):
        is_compare_page = self.stacked_widget.currentIndex() == 0
        for menu in (self.menu_file, self.menu_edit, self.menu_compare):
            menu.menuAction().setVisible(is_compare_page)
            menu.setEnabled(is_compare_page)

    def _switch_language(self, lang_code: str):
        self.current_lang = lang_code
        self._retranslate_ui()
        if hasattr(self.compare_page, "find_dialog"):
            self.compare_page.find_dialog.retranslate_ui()

    def _retranslate_ui(self):
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

        for item, btn in self.nav_buttons.items():
            btn.setText(tr[item])

        if hasattr(self.compare_page, "retranslate_ui"):
            self.compare_page.retranslate_ui()

    def _center(self):
        screen = self.screen().availableGeometry()
        size = self.geometry()
        self.move(int((screen.width() - size.width()) / 2), int((screen.height() - size.height()) / 2))

    def _show_about(self):
        self.status_bar.showMessage("Network Engineer Tools")

    def zoom_in(self):
        if hasattr(self, "compare_page"):
            self.compare_page.zoom_in()

    def zoom_out(self):
        if hasattr(self, "compare_page"):
            self.compare_page.zoom_out()

    def _zoom_reset(self):
        if hasattr(self, "compare_page"):
            self.compare_page._zoom_reset()


if __name__ == "__main__":
    app = QApplication(argv)
    window = TextCompareTool()
    window.show()
    exit(app.exec())
