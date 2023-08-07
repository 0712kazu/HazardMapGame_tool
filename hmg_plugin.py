import os

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from qgis.core import *
from qgis.gui import *

from preprocessor import Preprocessor
from hmg_data_generator import HGMDataGenerator

PLUGIN_NAME = "sample"


class Sample:
    def __init__(self, iface):
        self.iface = iface
        self.win = self.iface.mainWindow()
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = PLUGIN_NAME
        self.toolbar = self.iface.addToolBar(PLUGIN_NAME)
        self.toolbar.setObjectName(PLUGIN_NAME)

        # ツールバーのUIを生成
        self.toolbar = self.iface.addToolBar("HGM DATA")
        self.toolButton = QToolButton()
        self.toolButton.setMenu(QMenu())
        self.toolButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.toolButton.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "imgs/icon.png")))
        self.toolbar.addWidget(self.toolButton)

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None,
            as_default=False):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.toolButton.menu().addAction(action)
        if as_default:
            self.toolButton.setDefaultAction(action)
        if add_to_menu:
            self.iface.addPluginToWebMenu(
                PLUGIN_NAME,
                action)
        self.actions.append(action)
        return action

    def initGui(self):
        self.win = self.iface.mainWindow()
        self.add_action(
            icon_path="",
            text="シームレスデータ整備",
            callback=self.show_menu_01,
            parent=self.win)
        self.add_action(
            icon_path="",
            text="HMGデータ作成",
            callback=self.show_menu_02,
            parent=self.win)


        # メニュー設定
        # self.add_action(
        #     icon_path=None, text="シームレスデータ整備", callback=self.show_menu_01, parent=self.win
        # )
        # self.add_action(
        #     icon_path=None, text="HMGデータ作成", callback=self.show_menu_02, parent=self.win
        # )

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(PLUGIN_NAME, action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def show_menu_01(self):
        self.sample_menu_01 = Preprocessor()
        self.sample_menu_01.show()

    def show_menu_02(self):
        self.sample_menu_02 = HGMDataGenerator()
        self.sample_menu_02.show()
