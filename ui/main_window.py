import os

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QGroupBox, QLabel

from .hmg_data_generator import HMGDataGenerator
from .preprocessor import Preprocessor
from .hmg_data_classifier import HMGDataClassifier
from .pdf_exporter import PDFExporter


class MainWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi(
            os.path.join(os.path.dirname(__file__), "main_window.ui"), self
        )

        self._set_workflow_labels()

        self.preprocessor = Preprocessor(self)
        self.hmg_data_generator = HMGDataGenerator(self)
        self.hmg_data_classifier = HMGDataClassifier(self)
        self.pdf_exporter = PDFExporter(self)

    def _set_workflow_labels(self):
        """処理順とボタンの役割が伝わる名称にそろえる。"""

        self.pushButton_processhmg.setText("リスク値を計算")
        self.pushButton_classify.setText("点数を再計算")
        self.pushButton_total_hazard.setText("現在の点数を確認")

        self.QgsFileWidget_tatumaki.hide()
        self.QgsFileWidget_refuge.hide()
        for label in self.groupBox_6.findChildren(QLabel):
            if label.text() in ("竜巻", "避難施設"):
                label.hide()
        for group in self.findChildren(QGroupBox, "groupBox_custom"):
            group.hide()

        score_tab_index = self.tabWidget.indexOf(self.tab_3_hmg_data_generator)
        self.tabWidget.setTabText(score_tab_index, "リスク計算・点数調整")
        output_tab_index = self.tabWidget.indexOf(self.tab_4_pdf)
        self.tabWidget.setTabText(output_tab_index, "PDF・ゲームデータ出力")
