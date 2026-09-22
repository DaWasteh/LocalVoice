"""Predictable combo-box popups instead of Qt's selected-row-aligned menu mode."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QComboBox, QListView, QStyledItemDelegate


class PopupItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width() + 16, max(30, size.height() + 8))


class StableComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView(self)
        view.setUniformItemSizes(True)
        view.setMouseTracking(True)
        # The application's control padding must not shrink the popup viewport:
        # otherwise the lower item's hitbox can extend below the visible list.
        view.setStyleSheet('QListView { padding: 0px; margin: 0px; border: 0px; }')
        view.setAutoScroll(False)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setView(view)
        self.setItemDelegate(PopupItemDelegate(view))
        self.setMaxVisibleItems(12)
        # Menu-mode popups align the active row with the closed control and use
        # edge-triggered menu scrolling. A regular list remains spatially stable.
        self.setStyleSheet('QComboBox { combobox-popup: 0; }')

    def showPopup(self):
        view = self.view()
        rows = min(self.count(), self.maxVisibleItems())
        height = rows * max(30, view.sizeHintForRow(0)) + 2 * view.frameWidth()
        # Some Qt styles subtract control padding from the popup's viewport.
        # Give the layout an explicit content minimum so both rows stay hittable.
        view.setMinimumHeight(min(height, max(30, self.screen().availableGeometry().height() - 40)))
        super().showPopup()

    def wheelEvent(self, event):
        # Merely passing/scrolling over a closed selector must not change a model,
        # microphone or dictation mode. The open list still scrolls normally.
        if not self.view().isVisible():
            event.ignore()
            return
        super().wheelEvent(event)
