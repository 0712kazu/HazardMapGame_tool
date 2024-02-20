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

from utils import get_layer_orientation, add_xyz_basemap_layer


class PDFExporter:
    def __init__(self, main: QDialog):
        self.plot_widget = None
        self.main = main
        self.canvas = iface.mapCanvas()

        self.main.pushButton_export_pdf.clicked.connect(self._on_export_pdf_clicked)

    def _on_export_pdf_clicked(self):
        # import basemaps
        # basemap: gsi standard
        gsi_std_lyr = add_xyz_basemap_layer(
            "https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png",
            "basemap_standard",
        )

        # basemap: gsi coloured elevation
        gsi_relief_lyr = add_xyz_basemap_layer(
            "https://cyberjapandata.gsi.go.jp/xyz/relief/{z}/{x}/{y}.png",
            "basemap_relief",
        )

        # basemap: gsi hillshade
        gsi_hillshade_lyr = add_xyz_basemap_layer(
            "https://cyberjapandata.gsi.go.jp/xyz/hillshademap/{z}/{x}/{y}.png",
            "basemap_hillshade",
        )

        # make labels
        # label Mesh ID
        # Label Score
        # Label Hinan #0070ff

        # HMG01_ans : gsi standard only, refuges score and number, total hazard score
        # HNG02_base : gsi standard and hillshade
        # HMG02_base2: gsi standard
        # HMG03_tile: gsi_standard, turn off mesh id label

        # HMG04_use: Landuse symbol gsi_standard 50%, redisplay mesh_id
        # HMG05_elev: elevation, gsi_standard 50%, coloured elevation, hillshade

        # HMG06_g04: slope symbol & score, gsi_standard 50%
        # HMG07_b01: quake symbol & score, gsi_standard 50%

        # HMG08_a30 (DO NOT YET): tornado symbol & score, gsi_standard 50%

        # HMG09_a31 : flood symbol & score, gsi_standard 50%
        # HMG10_a33 : sediment symbol & score, gsi_standard 50%
        # HMG11_a40 : tsunami OR surge symbol & score, gsi_standard 50%

        # HMG12_a46 (DO NOT YET): landslip symbol & score, gsi_standard 50%
        # HMG13_a48 (DO NOT YET): disaster symbol & score, gsi_standard 50%

        self._export_pdf("hmgtest")
        for hazard in constants.hazards_ui_names:
            print(hazard)
            # TODO STEP 1: check fields t_hazard. If not, message it
            # TODO STEP 2: for each hazards, symbolize
            # TODO STEP 3: export pdf WITH FIELD NAME or in Japanese
        return

    def _export_pdf(self, map_title):
        project = QgsProject.instance()

        if QgsProject.instance().mapLayersByName("waku"):
            waku_lyr = QgsProject.instance().mapLayersByName("waku")[0]
        else:
            error_message = "「waku」レイヤが足りません。"
            QMessageBox.information(None, "エラー", error_message)
            return
        # determine landscape or portrait from waku
        orientation = get_layer_orientation(waku_lyr)
        layout_template_path = os.path.join(
            os.path.dirname(__file__),
            constants.data_dir,
            "layouts",
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
        # txt_title_item = layout.itemById("map_title")
        # txt_title_item.setText(self.main.pdf_map_title.text())

        # txt_hazard_item = layout.itemById("map_title")
        # txt_hazard_item.setText(map_title)

        txt_year_item = layout.itemById("copyright")
        copyright_txt = f"ハザードマップゲーム {str(datetime.date.today().year)} 東京カートグラフィック株式会社"
        txt_year_item.setText(copyright_txt)

        # Export PDF
        exporter = QgsLayoutExporter(layout)
        pdf_path = os.path.join(
            self.main.pdf_folder.filePath(),
            f"{self.main.pdf_map_title.text()}_{map_title}.pdf",
        )
        exporter.exportToPdf(pdf_path, QgsLayoutExporter.PdfExportSettings())
