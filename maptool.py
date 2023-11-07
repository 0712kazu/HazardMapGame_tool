from PyQt5.QtCore import Qt, pyqtSignal
from qgis.core import QgsPointXY, QgsRectangle
from qgis.gui import QgsMapTool, QgsRubberBand, QgsVertexMarker
from qgis.utils import iface


class POIMapTool(QgsMapTool):
    """
    Canvasをクッリクし、ポイントジオメトリを取得するマップツール
    """

    clicked = pyqtSignal(object)

    def __init__(self):
        QgsMapTool.__init__(self, iface.mapCanvas())
        self.vmarker = QgsVertexMarker(iface.mapCanvas())
        self.vmarker.setIconType(QgsVertexMarker.ICON_CROSS)
        self.vmarker.setIconSize(30)
        self.vmarker.setPenWidth(3)

    # クリック時の動作
    def canvasPressEvent(self, e):
        self.point = self.toMapCoordinates(e.pos())
        self.showRect(self.point)
        self.clicked.emit(self.point)

    def showRect(self, point):
        self.vmarker.setCenter(point)
        self.vmarker.show()

    def deactivate(self):
        iface.mapCanvas().scene().removeItem(self.vmarker)


class RectangleMapTool(QgsMapTool):
    rect_created = pyqtSignal(QgsRectangle)

    def __init__(self):
        QgsMapTool.__init__(self, iface.mapCanvas())
        self.rubberBand = QgsRubberBand(iface.mapCanvas(), True)
        self.rubberBand.setColor(Qt.red)
        self.rubberBand.setWidth(1)
        self.reset()

    def reset(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBand.reset(True)

    def canvasPressEvent(self, e):
        self.startPoint = self.toMapCoordinates(e.pos())
        self.endPoint = self.startPoint
        self.isEmittingPoint = True
        self.showRect(self.startPoint, self.endPoint)

    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False
        r = self.rectangle()
        if r is not None:
            self.rect_created.emit(r)

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return

        self.endPoint = self.toMapCoordinates(e.pos())
        self.showRect(self.startPoint, self.endPoint)

    def showRect(self, startPoint, endPoint):
        self.rubberBand.reset()
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return

        point1 = QgsPointXY(startPoint.x(), startPoint.y())
        point2 = QgsPointXY(startPoint.x(), endPoint.y())
        point3 = QgsPointXY(endPoint.x(), endPoint.y())
        point4 = QgsPointXY(endPoint.x(), startPoint.y())
        point5 = point1

        self.rubberBand.addPoint(point1, False)
        self.rubberBand.addPoint(point2, False)
        self.rubberBand.addPoint(point3, False)
        self.rubberBand.addPoint(point4, False)
        self.rubberBand.addPoint(point5, True)
        # true to update canvas
        self.rubberBand.show()

    def rectangle(self):
        if self.startPoint is None or self.endPoint is None:
            return None
        elif (
            self.startPoint.x() == self.endPoint.x()
            or self.startPoint.y() == self.endPoint.y()
        ):
            return None
        return QgsRectangle(self.startPoint, self.endPoint)

    def deactivate(self):
        self.rubberBand.reset()
        QgsMapTool.deactivate(self)
        self.deactivated.emit()
