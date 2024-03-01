from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import QVariant
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsPrintLayout,
    QgsReadWriteContext,
    QgsLayoutExporter,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
)
from PyQt5.QtXml import QDomDocument


from qgis.utils import iface

import os
import processing
import datetime
import constants

from converter.hmg2pdf import (
    label_pt_mesh,
    set_hmg01_ans_refuge,
    set_hmg02_base,
    set_hmg02_base_hillshade,
    set_hmg03_tile,
    set_hmg04_landuse,
    set_hmg05_elev,
    set_hmg06_slope,
    set_hmg07_earthquake,
    set_hmg08_tornado,
    set_hmg09_flood,
    set_hmg10_sediments,
    set_hmg11_tsunami,
    set_hmg12_landslip,
    set_hmg13_disaster,
    calculate_hazard_rank,
)
from utils import (
    get_layer_orientation,
    add_xyz_basemap_layer,
    add_to_map,
    remove_layer,
    find,
)


class PDFExporter:
    def __init__(self, main: QDialog):
        self.plot_widget = None
        self.main = main
        self.canvas = iface.mapCanvas()

        self.main.pushButton_export_pdf.clicked.connect(self._on_export_pdf_clicked)
        self.main.pushButton_cancel_pdf.clicked.connect(lambda: self.main.close())

        # set default checkbox
        default_pdf_to_exports = [
            "hmg01",
            "hmg02",
            "hmg02b",
            "hmg03",
            "hmg04",
            "hmg05",
            "hmg06",
            "hmg07",
            "hmg09",
            "hmg10",
            "hmg11",
        ]
        for pdf_to_export in default_pdf_to_exports:
            checkbox = getattr(self.main, f"checkBox_{pdf_to_export}")
            checkbox.setChecked(True)

        # set tsunami radiobutton as default for hmg11
        self.main.radioButton_hmg11_tsunami.setChecked(True)

    def _on_export_pdf_clicked(self):
        # check parameters
        if not self.main.pdf_folder.filePath():
            error_message = "エラーが発生しました。\n\n"
            error_message += "出力PDFフォルダーが設定していません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        # set style to mesh_score and waku
        if QgsProject.instance().mapLayersByName("waku"):
            waku_lyr = QgsProject.instance().mapLayersByName("waku")[0]
        else:
            error_message = "「waku」レイヤが足りません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        if QgsProject.instance().mapLayersByName("mesh_score"):
            mesh_lyr = QgsProject.instance().mapLayersByName("mesh_score")[0]
        else:
            error_message = "「mesh_score」レイヤが足りません。"
            QMessageBox.information(None, "エラー", error_message)
            return

        # List of missing layers to message at the end of process
        missing_layers = []

        # style mesh_score and waku layers
        qml_file = os.path.join(
            os.path.dirname(__file__),
            constants.data_dir,
            "styles",
            "mesh_pdf_style.qml",
        )
        mesh_lyr.loadNamedStyle(qml_file)
        waku_lyr.loadNamedStyle(qml_file)

        # calculate total hazard score
        scored_hazard = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": mesh_lyr,
                "FIELD_NAME": constants.field_hazard_score,
                "FIELD_TYPE": 1,
                "FIELD_LENGTH": 0,
                "FIELD_PRECISION": 0,
                "FORMULA": self._make_hazard_scores_formula(),
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )["OUTPUT"]

        # calculate rank formula
        ranked_hazard = calculate_hazard_rank(scored_hazard)

        # export mesh as shapefile
        shp_file_name = f"{self.main.pdf_map_title.text()}_HMG_hazard_score.shp"
        if self.main.pdf_map_title.text() == "":
            # remove first "_" if title is empty
            shp_file_name = shp_file_name[1:]

        shp_path = os.path.join(
            self.main.pdf_folder.filePath(),
            shp_file_name,
        )
        QgsVectorFileWriter.writeAsVectorFormat(
            ranked_hazard,
            shp_path,
            "UTF-8",
            QgsCoordinateReferenceSystem("epsg:3857"),
            "ESRI Shapefile",
        )

        # create hazard score point layer from mesh centroid
        hazard_lyr = processing.run(
            "native:pointonsurface",
            {
                "INPUT": ranked_hazard,
                "ALL_PARTS": False,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )["OUTPUT"]

        # remove layer if already exists
        remove_layer("hazard_score")
        add_to_map(hazard_lyr, "hazard_score")

        # make labels
        # label Mesh ID
        label_mesh_id = processing.run(
            "native:pointonsurface",
            {
                "INPUT": ranked_hazard,
                "ALL_PARTS": False,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )["OUTPUT"]
        # remove layer if already exists
        remove_layer("label_id")
        add_to_map(label_mesh_id, "label_id")
        label_pt_mesh(label_mesh_id, '"id"', "#686868")
        label_mesh_id.setOpacity(0)

        # Label Score
        # get the distance to translate label from mesh center (1/5 mesh distance)
        mesh_feature = next(mesh_lyr.getFeatures())
        mesh_edge_size = mesh_feature.geometry().length() / 4
        dy = mesh_edge_size / 5
        label_mesh_score = processing.run(
            "native:translategeometry",
            {
                "INPUT": label_mesh_id,
                "DELTA_X": 0,
                "DELTA_Y": -dy,
                "DELTA_Z": 0,
                "DELTA_M": 0,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )["OUTPUT"]
        # remove layer if already exists
        remove_layer("label_score")
        add_to_map(label_mesh_score, "label_score")

        label_pt_mesh(label_mesh_score, '"t_refuge"', "red")
        label_mesh_score.setOpacity(0)

        # Label Hinan #0070ff
        label_hinan_count = processing.run(
            "native:translategeometry",
            {
                "INPUT": label_mesh_id,
                "DELTA_X": 0,
                "DELTA_Y": dy,
                "DELTA_Z": 0,
                "DELTA_M": 0,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )["OUTPUT"]
        # remove layer if already exists
        remove_layer(f"label_{constants.field_refuge}")
        add_to_map(label_hinan_count, f"label_{constants.field_refuge}")

        label_pt_mesh(label_hinan_count, f'"{constants.field_refuge}"', "#0070ff")
        label_hinan_count.setOpacity(0)

        # import basemaps

        # basemap: gsi standard
        # remove layer if already exists
        remove_layer("basemap_standard")
        gsi_std_lyr = add_xyz_basemap_layer(
            "https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png",
            "basemap_standard",
        )

        # basemap: gsi coloured elevation
        remove_layer("basemap_relief")
        gsi_relief_lyr = add_xyz_basemap_layer(
            "https://cyberjapandata.gsi.go.jp/xyz/relief/{z}/{x}/{y}.png",
            "basemap_relief",
        )

        # basemap: gsi hillshade
        remove_layer("basemap_hillshade")
        gsi_hillshade_lyr = add_xyz_basemap_layer(
            "https://cyberjapandata.gsi.go.jp/xyz/hillshademap/{z}/{x}/{y}.png",
            "basemap_hillshade",
        )

        # 変更前のレイヤー順序を取得
        root = iface.layerTreeCanvasBridge().rootGroup()
        root.setCustomLayerOrder(root.layerOrder())
        root.setHasCustomLayerOrder(True)
        order = list(
            map(
                lambda list: list.layer(),
                QgsProject.instance().layerTreeRoot().findLayers(),
            )
        )

        # 地理院標準レイヤーを最後面に
        std_idx = find(order, gsi_std_lyr)
        if std_idx > -1:
            order.insert(-1, order.pop(std_idx))

        # 地理院色別標高レイヤーを最後面に
        rlf_idx = find(order, gsi_relief_lyr)
        if std_idx > -1:
            order.insert(-1, order.pop(rlf_idx))

        # 地理院陰影レイヤーを最後面に
        hls_idx = find(order, gsi_hillshade_lyr)
        if hls_idx > -1:
            order.insert(-1, order.pop(hls_idx))

        # 避難施設所レイヤーを最前面に
        if QgsProject.instance().mapLayersByName(f"seamless_{constants.field_refuge}"):
            hinan_lyr = QgsProject.instance().mapLayersByName(
                f"seamless_{constants.field_refuge}"
            )[0]
            hinan_idx = find(order, hinan_lyr)
            if hinan_idx > -1:
                order.insert(0, order.pop(hinan_idx))
        else:
            missing_layers.append(f"seamless_{constants.field_refuge}")

        # 変更されたレイヤー順序を適用
        root.setCustomLayerOrder(order)

        # HMG01_ans : gsi standard only, refuges score and number, total hazard score, colors
        if self.main.checkBox_hmg01.isChecked():
            miss_lyrs = set_hmg01_ans_refuge(gsi_std_lyr, label_mesh_score)
            missing_layers.extend(miss_lyrs)
            self._export_pdf("HMG01_ans")

        # HMG02_base : gsi standard
        if self.main.checkBox_hmg02.isChecked():
            set_hmg02_base(gsi_std_lyr)
            self._export_pdf("HMG02_base")

        # HMG02_base2: gsi standard and hillshade
        if self.main.checkBox_hmg02b.isChecked():
            set_hmg02_base_hillshade(gsi_std_lyr, gsi_hillshade_lyr)
            self._export_pdf("HMG02_base2")

        # HMG03_tile: gsi_standard, turn off mesh id label
        if self.main.checkBox_hmg03.isChecked():
            set_hmg03_tile(gsi_std_lyr)
            self._export_pdf("HMG03_tile")

        # HMG04_use: Landuse symbol gsi_standard 50%, redisplay mesh_id
        if self.main.checkBox_hmg04.isChecked():
            miss_lyrs = set_hmg04_landuse(gsi_std_lyr)
            missing_layers.extend(miss_lyrs)
            self._export_pdf("HMG04_use")

        # HMG05_elev: elevation, gsi_standard 50%, coloured elevation, hillshade
        if self.main.checkBox_hmg05.isChecked():
            set_hmg05_elev(gsi_std_lyr)
            self._export_pdf("HMG05_elev")

        # HMG06_g04: slope symbol & score, gsi_standard 50%
        if self.main.checkBox_hmg06.isChecked():
            miss_lyrs = set_hmg06_slope(gsi_std_lyr, label_mesh_score)
            missing_layers.extend(miss_lyrs)
            self._export_pdf("HMG06_g04")

        # HMG07_b01: quake symbol & score, gsi_standard 50%
        if self.main.checkBox_hmg07.isChecked():
            miss_lyrs = set_hmg07_earthquake(gsi_std_lyr, label_mesh_score)
            missing_layers.extend(miss_lyrs)
            self._export_pdf("HMG07_b01")

        # HMG08_a30 (OPTION): tornado symbol & score, gsi_standard 50%
        if self.main.checkBox_hmg08.isChecked():
            miss_lyrs = set_hmg08_tornado(gsi_std_lyr, label_mesh_score)
            missing_layers.extend(miss_lyrs)
            self._export_pdf("HMG08_a30")

        # HMG09_a31 : flood symbol & score, gsi_standard 50%
        if self.main.checkBox_hmg09.isChecked():
            miss_lyrs = set_hmg09_flood(gsi_std_lyr, label_mesh_score)
            missing_layers.extend(miss_lyrs)
            self._export_pdf("HMG09_a31")

        # HMG10_a33 : sediment symbol & score, gsi_standard 50%
        if self.main.checkBox_hmg10.isChecked():
            miss_lyrs = set_hmg10_sediments(gsi_std_lyr, label_mesh_score)
            missing_layers.extend(miss_lyrs)
            self._export_pdf("HMG10_a33")

        # HMG11_a40 : tsunami OR surge symbol & score, gsi_standard 50%
        if self.main.checkBox_hmg11.isChecked():
            if self.main.radioButton_hmg11_tsunami.isChecked():
                hmg11_field = constants.field_tsunami
            elif self.main.radioButton_hmg11_surge.isChecked():
                hmg11_field = constants.field_surge
            else:
                error_message = "HMG11_a31の対象カラムが指定していません。\n"
                error_message += "津波に指定します。"
                QMessageBox.information(None, "エラー", error_message)

            miss_lyrs = set_hmg11_tsunami(gsi_std_lyr, label_mesh_score, hmg11_field)
            missing_layers.extend(miss_lyrs)
            self._export_pdf("HMG11_a40")

        # HMG12_a46 (OPTION): landslip symbol & score, gsi_standard 50%
        if self.main.checkBox_hmg12.isChecked():
            miss_lyrs = set_hmg12_landslip(gsi_std_lyr, label_mesh_score)
            missing_layers.extend(miss_lyrs)
            self._export_pdf("HMG12_a46")

        # HMG13_a48 (OPTION): disaster symbol & score, gsi_standard 50%
        if self.main.checkBox_hmg13.isChecked():
            miss_lyrs = set_hmg13_disaster(gsi_std_lyr, label_mesh_score)
            missing_layers.extend(miss_lyrs)
            self._export_pdf("HMG13_a48")

        # End process message
        message = "PDFの出力が完了しました。\n"
        if len(missing_layers) > 0:
            message += "\n以下のレイヤが足りないため、PDFに表示しません。\n"
            for missing_layer in missing_layers:
                message += f"{missing_layer}\n"
        QMessageBox.information(None, "エラー", message)

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
        txt_title_item = layout.itemById("map_title")
        txt_title_item.setText(self.main.pdf_map_title.text())

        txt_year_item = layout.itemById("copyright")
        copyright_txt = f"ハザードマップゲーム {str(datetime.date.today().year)} 東京カートグラフィック株式会社"
        txt_year_item.setText(copyright_txt)

        # Export PDF
        exporter = QgsLayoutExporter(layout)

        pdf_file_name = f"{self.main.pdf_map_title.text()}_{map_title}.pdf"
        if self.main.pdf_map_title.text() == "":
            # remove first "_" if title is empty
            pdf_file_name = pdf_file_name[1:]

        pdf_path = os.path.join(
            self.main.pdf_folder.filePath(),
            pdf_file_name,
        )
        exporter.exportToPdf(pdf_path, QgsLayoutExporter.PdfExportSettings())

    def _make_hazard_scores_formula(self):
        target_fields = []
        if self.main.checkBox_hmg06.isChecked():
            target_fields.append(f"t_{constants.field_slope}")
        if self.main.checkBox_hmg07.isChecked():
            target_fields.append(f"t_{constants.field_earthquake}")
        if self.main.checkBox_hmg08.isChecked():
            target_fields.append(f"t_{constants.field_tornado}")
        if self.main.checkBox_hmg09.isChecked():
            target_fields.append(f"t_{constants.field_kozui}")
        if self.main.checkBox_hmg10.isChecked():
            target_fields.append(f"t_{constants.field_sediments}")
        if (
            self.main.checkBox_hmg11.isChecked()
            and self.main.radioButton_hmg11_tsunami.isChecked()
        ):
            target_fields.append(f"t_{constants.field_tsunami}")
        if (
            self.main.checkBox_hmg11.isChecked()
            and self.main.radioButton_hmg11_surge.isChecked()
        ):
            target_fields.append(f"t_{constants.field_surge}")
        if self.main.checkBox_hmg12.isChecked():
            target_fields.append(f"t_{constants.field_jisuberi}")
        if self.main.checkBox_hmg13.isChecked():
            target_fields.append(f"t_{constants.field_saigai}")

        # handle if no hazard
        if len(target_fields) == 0:
            error_message = (
                "選択した出力項目に災害地図が無いため、合計点数が0になります。"
            )
            QMessageBox.information(None, "お知らせ", error_message)
            return "0"
        score_formula = '" + "'.join(target_fields)

        return ' "' + score_formula + '" '
