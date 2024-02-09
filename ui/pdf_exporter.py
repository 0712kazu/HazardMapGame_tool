from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import QVariant
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsPrintLayout,
    QgsReadWriteContext,
    QgsLayoutExporter,
)
from PyQt5.QtXml import QDomDocument


from qgis.utils import iface

import os
import datetime
import constants


class PDFExporter:
    def __init__(self, main: QDialog):
        self.plot_widget = None
        self.main = main
        self.canvas = iface.mapCanvas()

        self.main.pushButton_export_pdf.clicked.connect(self._on_export_pdf_clicked)

    def _on_export_pdf_clicked(self):
        # TODO STEP 1: check fields t_hazard. If not, message it

        for hazard in constants.hazards_ui_names:
            # TODO STEP 2: for each hazards, symbolize
            # TODO STEP 3: export pdf
            self._export_pdf(hazard)
        return

    def _export_pdf(self, hazard_name):
        project = QgsProject.instance()

        if QgsProject.instance().mapLayersByName("waku"):
            waku_lyr = QgsProject.instance().mapLayersByName("waku")[0]
        else:
            error_message = "「waku」レイヤが足りません。"
            QMessageBox.information(None, "エラー", error_message)
            return
        # TODO : determine landscape or portrait from waku
        orientation = "landscape"
        layout_template_path = os.path.join(
            os.path.dirname(__file__),
            constants.data_dir,
            f"tcg_layout_a1_{orientation}.qpt",
        )

        with open(layout_template_path, "r") as f:
            xml_content = f.read()

        # Create a QDomDocument from the XML content
        doc = QDomDocument()
        doc.setContent(xml_content)
        composition = QgsPrintLayout(project)
        composition.loadFromTemplate(doc, QgsReadWriteContext())

        template_name = composition.name()
        manager = project.layoutManager()
        project.layoutManager().addLayout(composition)
        layout = manager.layoutByName(template_name)

        # retrieve map item and set extent to waku
        map_item = layout.itemById("tcg_map")
        map_item.zoomToExtent(waku_lyr.extent())

        # retrieve text object and set text
        txt_title_item = layout.itemById("map_title")
        txt_title_item.setText(self.main.pdf_map_title.text())

        txt_hazard_item = layout.itemById("hazard_name")
        txt_hazard_item.setText(hazard_name)

        txt_year_item = layout.itemById("copyright_year")
        txt_year_item.setText(str(datetime.date.today().year))

        # Export PDF
        exporter = QgsLayoutExporter(layout)
        pdf_path = os.path.join(
            self.main.pdf_folder.filePath(),
            f"{self.main.pdf_map_title.text()}_{hazard_name}.pdf",
        )
        exporter.exportToPdf(pdf_path, QgsLayoutExporter.PdfExportSettings())
