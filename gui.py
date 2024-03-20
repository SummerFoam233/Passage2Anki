from aqt import mw
from aqt.qt import *
from .vocab_processor import main_process, TranslationError, test_process
from .anki_integration import add_cards_to_deck
import json
import os
import logging
from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSlot, Qt, QMetaObject, Q_ARG
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QProgressDialog

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "Passage2Card.config")

from PyQt6.QtCore import QMimeData

class PlainTextPasteEdit(QTextEdit):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
    
    def insertFromMimeData(self, source: QMimeData):
        if source.hasText():
            self.insertPlainText(source.text())  # 只插入纯文本
        else:
            super().insertFromMimeData(source)  # 其他类型的数据保持默认处理方式

class WorkerSignals(QObject):
    updateProgress = pyqtSignal(int)
    updateUI = pyqtSignal(dict)
    error = pyqtSignal(str)

class Worker(QRunnable):
    def __init__(self, text, vocab_file_path):
        super(Worker, self).__init__()
        self.text = text
        self.vocab_file_path = vocab_file_path
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        def progress_callback(progress):
            self.signals.updateProgress.emit(progress)

        try:
            vocab_list = main_process(self.text, self.vocab_file_path, progress_callback)
            self.signals.updateUI.emit(vocab_list)
        except TranslationError as e:
            self.signals.error.emit(e)

class MainDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loadConfig()
        self.setupUi()

    def setupUi(self):
        self.setWindowTitle("Passage2Card - Main Dialog")
        layout = QVBoxLayout()

        # Input fields for Youdao API credentials and article text
        self.app_id_input = QLineEdit(self.config.get("app_id", ""))
        self.app_key_input = QLineEdit(self.config.get("app_key", ""))
        self.article_text_input = PlainTextPasteEdit(self.config.get("article_text", ""))
        self.file_path_input = QLineEdit(self.config.get("file_path", ""))  # Path for an additional file

        # Button to browse for a text file
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browseFile)

        # Button to process the text
        self.process_btn = QPushButton("Process Text")
        self.process_btn.clicked.connect(self.processText)

        # Button to save config
        save_config_btn = QPushButton("Save Config")
        save_config_btn.clicked.connect(self.saveConfig)

        # Layout setup
        layout.addWidget(QLabel("App ID:"))
        layout.addWidget(self.app_id_input)
        layout.addWidget(QLabel("App Key:"))
        layout.addWidget(self.app_key_input)
        layout.addWidget(QLabel("Article Text:"))
        layout.addWidget(self.article_text_input)
        layout.addWidget(QLabel("File Path:"))
        layout.addWidget(self.file_path_input)
        layout.addWidget(browse_btn)
        layout.addWidget(self.process_btn)
        layout.addWidget(save_config_btn)

        self.setLayout(layout)

    def browseFile(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Text File", "", "Text Files (*.txt)")
        if file_path:
            self.file_path_input.setText(file_path)

    def processText(self):
        self.process_btn.setEnabled(False)
        article_text = self.article_text_input.toPlainText()
        vocab_file_path = self.file_path_input.text()

        self.progressDialog = QProgressDialog("Processing...", "Cancel", 0, 100, self)
        self.progressDialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progressDialog.setAutoClose(True)
        self.progressDialog.setAutoReset(True)
        self.progressDialog.setValue(0)

        worker = Worker(article_text, vocab_file_path)
        worker.signals.updateProgress.connect(self.updateProgress)
        worker.signals.updateUI.connect(self.updateUI)
        worker.signals.error.connect(self.showError)
        QThreadPool.globalInstance().start(worker)

    def processText_2(self):
        article_text = self.article_text_input.toPlainText()
        vocab_file_path = self.file_path_input.text()
        output = test_process(article_text, vocab_file_path)
        # 记录日志
        logging.basicConfig(filename='/Users/summerfoam233/Desktop/备份/output.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

        logging.debug(f"Article Text: {article_text}")
        logging.debug(f"Vocab File Path: {vocab_file_path}")
        logging.debug(f"Output: {output}")

    def updateProgress(self, progress):
        self.progressDialog.setValue(progress)

    def updateUI(self, vocab_list):
        self.progressDialog.setValue(100)
        self.resultsDialog = ResultsDialog(vocab_list, self)
        self.resultsDialog.setFocus()  # 设置焦点到 resultsDialog
        self.resultsDialog.exec() 
        self.process_btn.setEnabled(True)

    def showError(self, error_message):
        QMessageBox.critical(self, "Translation Error", error_message)
        self.process_btn.setEnabled(True)
        self.progressDialog.cancel()

    def saveConfig(self):
        self.config["app_id"] = self.app_id_input.text()
        self.config["app_key"] = self.app_key_input.text()
        self.config["file_path"] = self.file_path_input.text()
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as config_file:
            json.dump(self.config, config_file, ensure_ascii=False, indent=4)
        QMessageBox.information(self, "Info", "Configuration saved successfully.")

    def loadConfig(self):
        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as config_file:
                self.config = json.load(config_file)
        except FileNotFoundError:
            self.config = {}

from PyQt6.QtWidgets import QCheckBox, QTableWidgetItem, QAbstractItemView, QComboBox

class ResultsDialog(QDialog):
    def __init__(self, vocab_list, parent=None):
        super().__init__(parent)
        self.vocab_list = vocab_list  # Expecting a dict
        self.checkedItems = []  # Keep track of checked items
        self.loadConfig()
        self.setupUi()

    def loadConfig(self):
        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as config_file:
                self.config = json.load(config_file)
        except FileNotFoundError:
            self.config = {}

    def save_config(self,config):
        config_path = os.path.join(os.path.dirname(__file__), "Passage2Card.config")
        with open(config_path, 'w', encoding='utf-8') as config_file:
            json.dump(config, config_file, ensure_ascii=False, indent=4)

    def get_anki_decks(self):
        return mw.col.decks.all_names()
    
    def setupUi(self):
        self.setWindowTitle("Translation Results")
        layout = QVBoxLayout()
        deckLabel = QLabel("导入牌组：")
        layout.addWidget(deckLabel)

        deckNames = self.get_anki_decks()
        # 创建并填充牌组选择的下拉菜单
        self.deckComboBox = QComboBox()
        self.deckComboBox.addItems(deckNames)  # 填充牌组名称

        # 选择上次使用的牌组，如果没有或牌组不存在则选择第一个
        lastUsedDeck = self.config.get("lastUsedDeck", deckNames[0] if deckNames else "")
        if lastUsedDeck in deckNames:
            self.deckComboBox.setCurrentText(lastUsedDeck)
        else:
            self.config["lastUsedDeck"] = deckNames[0] if deckNames else ""  # 更新配置以反映当前选择
            self.save_config(self.config)

        self.deckComboBox.currentIndexChanged.connect(self.onDeckSelected)

        layout.addWidget(self.deckComboBox)  # 将下拉菜单添加到布局中

        self.table = QTableWidget(len(self.vocab_list), 4)  # Added an extra column for checkboxes
        self.table.setHorizontalHeaderLabels(["Select", "Word", "Original", "Translation"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        for i, word in enumerate(self.vocab_list):
            # Add a checkbox to each row
            checkBox = QCheckBox()
            checkBox.setChecked(False)  # Default to checked
            checkBox.stateChanged.connect(self.onCheckboxStateChanged)
            self.table.setCellWidget(i, 0, checkBox)

            # Fill the rest of the row with data
            self.table.setItem(i, 1, QTableWidgetItem(word))
            self.table.setItem(i, 2, QTableWidgetItem(self.vocab_list[word]["original"]))
            self.table.setItem(i, 3, QTableWidgetItem(self.vocab_list[word]["chinese_translate"]))
            self.checkedItems.append(i)  # Initially all items are checked

        add_btn = QPushButton("Add to Anki")
        add_btn.clicked.connect(self.addToAnki)

        layout.addWidget(self.table)
        layout.addWidget(add_btn)

        self.setLayout(layout)
        self.resize(600, 400)

    def onDeckSelected(self, index):
        selectedDeck = self.deckComboBox.currentText()
        self.config["lastUsedDeck"] = selectedDeck  # 更新配置以记住选择
        self.save_config(self.config)

    def onCheckboxStateChanged(self, state):
        for i in range(self.table.rowCount()):
            checkBox = self.table.cellWidget(i, 0)
            if checkBox.isChecked() and i not in self.checkedItems:
                self.checkedItems.append(i)
            elif not checkBox.isChecked() and i in self.checkedItems:
                self.checkedItems.remove(i)

    def addToAnki(self):
        selectedDeck = self.deckComboBox.currentText()  # 获取选中的牌组名称
        self.config["lastUsedDeck"] = selectedDeck  # 更新配置以记住选择
        self.save_config(self.config)
        # 使用selectedDeck作为牌组名称进行卡片添加的逻辑...
        data_list = [(self.table.item(i, 2).text(), self.table.item(i, 3).text()) for i in range(self.table.rowCount()) if self.table.cellWidget(i, 0).isChecked()]
        add_cards_to_deck(selectedDeck, data_list)  # 假设这个函数负责添加卡片到指定的Anki牌组
        QMessageBox.information(self, "Success", "Selected translations have been added to Anki deck: " + selectedDeck)
        self.accept()

def open_main_dialog():
    dialog = MainDialog(mw)
    dialog.exec()
