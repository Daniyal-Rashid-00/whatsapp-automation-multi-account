from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush

class ToggleSwitch(QWidget):
    """Custom-painted toggle switch widget with smooth knob aesthetic."""
    stateChanged = pyqtSignal(bool)

    def __init__(self, checked: bool = True, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(40, 20)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self.stateChanged.emit(self._checked)
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.stateChanged.emit(self._checked)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw track background
        track_color = QColor("#10B981") if self._checked else QColor("#484F58")
        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 40, 20, 10, 10)

        # Draw circular white thumb knob
        thumb_x = 22 if self._checked else 2
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawEllipse(thumb_x, 2, 16, 16)
