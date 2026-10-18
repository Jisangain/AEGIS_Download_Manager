import os
import sys
import traceback

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    from ui import MainWindow
    w = MainWindow()
    print("SUCCESS: Window initialized")
    print("Rows:", w.table.rowCount())
    for r in range(w.table.rowCount()):
        st = w.table.item(r, 6).text() if w.table.item(r, 6) else ""
        has_widget = w.table.cellWidget(r, 3) is not None
        item_txt = w.table.item(r, 3).text() if w.table.item(r, 3) else ""
        print(f"Row {r}: Status={st} | HasWidget={has_widget} | Text='{item_txt}'")
    w.close()
    print("ALL TESTS PASSED")
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
