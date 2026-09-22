"""Native/offscreen popup geometry and mouse-selection regression check."""
import json
from pathlib import Path
import sys
import tempfile
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from localvoice.ui import Window

app = QApplication([])
app.setStyle('Fusion')
report = []
with tempfile.TemporaryDirectory(prefix='localvoice-dropdown-') as folder:
    window = Window(Path(folder))
    window.show()
    QTest.qWait(100)
    try:
        combo = window.mode
        for initial in (0, 1):
            combo.setCurrentIndex(initial)
            combo.showPopup()
            QTest.qWait(100)
            view = combo.view()
            popup = view.window()
            initial_geometry = popup.geometry().getRect()
            positions = {i: view.visualRect(combo.model().index(i, 0)).center() for i in (0, 1)}
            hovers = []
            for index in (1, 0, 1, 0):
                QTest.mouseMove(view.viewport(), positions[index])
                QTest.qWait(80)
                hovers.append({'intended_row': index, 'current_row': view.currentIndex().row(),
                               'row_at_mouse': view.indexAt(positions[index]).row(),
                               'popup_geometry': popup.geometry().getRect(),
                               'row_rects': [view.visualRect(combo.model().index(i, 0)).getRect() for i in (0, 1)]})
            target = 1 - initial
            QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=positions[target])
            QTest.qWait(50)
            report.append({'initial': initial, 'target': target, 'selected': combo.currentIndex(),
                           'geometry': initial_geometry, 'hovers': hovers})
    finally:
        window.quit()
root = Path(__file__).resolve().parents[1]
(root / 'reports').mkdir(exist_ok=True)
(root / 'reports/dropdown.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
assert report[0]['geometry'] == report[1]['geometry'], 'Popup moved with the selected row'
assert all(r['selected'] == r['target'] for r in report)
assert all(h['row_at_mouse'] == h['intended_row'] and tuple(h['popup_geometry']) == tuple(r['geometry'])
           for r in report for h in r['hovers'])
