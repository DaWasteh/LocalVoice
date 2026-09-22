import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from localvoice.widgets import StableComboBox


@pytest.fixture
def combo():
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')  # same style as main.py, not the platform test default
    parent = QWidget()
    layout = QVBoxLayout(parent)
    box = StableComboBox(parent)
    box.addItems(['Am Ende schreiben', 'Vorschau in Abschnitten'])
    layout.addWidget(box)
    parent.resize(340, 90)
    parent.move(100, 100)
    parent.show()
    app.processEvents()
    yield box
    parent.close()
    parent.deleteLater()
    app.processEvents()


def test_popup_position_does_not_follow_selected_row(combo):
    geometries = []
    for initial in (0, 1):
        combo.setCurrentIndex(initial)
        combo.showPopup()
        # Qt briefly suppresses opening-click releases to avoid instant selection.
        QTest.qWait(400)
        view = combo.view()
        assert combo.isVisible() and view.isVisible(), 'Popup was closed by a pending application event'
        geometry = view.window().geometry().getRect()
        geometries.append(geometry)
        assert not view.hasAutoScroll()
        for row in (1, 0, 1, 0):
            rect = view.visualRect(combo.model().index(row, 0))
            assert rect.height() >= 30
            assert view.viewport().rect().contains(rect)
            QTest.mouseMove(view.viewport(), rect.center())
            QApplication.processEvents()
            assert view.indexAt(rect.center()).row() == row
            assert view.window().geometry().getRect() == geometry
        target = 1 - initial
        rect = view.visualRect(combo.model().index(target, 0))
        pressed, clicked = QSignalSpy(view.pressed), QSignalSpy(view.clicked)
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
        assert combo.currentIndex() == target, (view.currentIndex().row(), pressed.count(), clicked.count(), rect.getRect(), view.viewport().rect().getRect())
        combo.hidePopup()
    assert geometries[0] == geometries[1]


def test_closed_combo_ignores_wheel_but_preserves_arrow_keys(combo):
    combo.setCurrentIndex(1)
    for delta in (120, -120):
        event = QWheelEvent(QPointF(20, 20), QPointF(combo.mapToGlobal(QPoint(20, 20))),
            QPoint(), QPoint(0, delta), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(combo, event)
        assert combo.currentIndex() == 1
    QTest.keyClick(combo, Qt.Key.Key_Up)
    assert combo.currentIndex() == 0
    QTest.keyClick(combo, Qt.Key.Key_Down)
    assert combo.currentIndex() == 1
