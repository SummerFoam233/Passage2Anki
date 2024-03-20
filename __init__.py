from aqt import mw
from aqt.utils import showInfo
from aqt.qt import QAction
from .gui import open_main_dialog

def add_menu_item():
    action = QAction("Passage2Card", mw)
    action.triggered.connect(open_main_dialog)
    mw.form.menuTools.addAction(action)

add_menu_item()