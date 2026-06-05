import sys
import shutil
import logging
from pathlib import Path
from collections import deque

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QStackedWidget,
    QSizePolicy,
)
from PyQt5.QtGui import QPixmap, QKeySequence
from PyQt5.QtCore import Qt

SUPPORTED = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}

# logger
logger = logging.getLogger('image_sorter')
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler('image_sorter.log', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    fh.setFormatter(fmt)
    logger.addHandler(fh)


class SetupPage(QWidget):
    def __init__(self, on_done):
        super().__init__()
        self.on_done = on_done
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.instructions = QLabel('Add Hotkey and Folder name pairs then click Start')
        self.layout.addWidget(self.instructions)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['Hotkey', 'Folder Name'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout.addWidget(self.table)

        controls = QHBoxLayout()
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setPlaceholderText('Press a single key for hotkey (e.g. a)')
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText('Folder name')
        add_btn = QPushButton('Add')
        add_btn.clicked.connect(self.add_pair)

        controls.addWidget(self.hotkey_input)
        controls.addWidget(self.folder_input)
        controls.addWidget(add_btn)
        self.layout.addLayout(controls)

        start_btn = QPushButton('Start Sorting')
        start_btn.clicked.connect(self.start)
        self.layout.addWidget(start_btn)

    def add_pair(self):
        k = self.hotkey_input.text().strip()
        f = self.folder_input.text().strip()
        if not k or not f:
            QMessageBox.warning(self, 'Missing', 'Specify both hotkey and folder name')
            return
        if len(k) != 1:
            QMessageBox.warning(self, 'Hotkey', 'Use a single character as hotkey')
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(k.lower()))
        self.table.setItem(row, 1, QTableWidgetItem(f))
        self.hotkey_input.clear()
        self.folder_input.clear()

    def start(self):
        mapping = {}
        for r in range(self.table.rowCount()):
            key = self.table.item(r, 0).text().strip().lower()
            folder = self.table.item(r, 1).text().strip()
            if key in mapping:
                QMessageBox.warning(self, 'Duplicate', f'Duplicate hotkey: {key}')
                return
            mapping[key] = folder
        if not mapping:
            QMessageBox.warning(self, 'Empty', 'Add at least one mapping')
            return
        logger.debug('Starting sorter with mapping: %s', mapping)
        self.on_done(mapping)


class SortPage(QWidget):
    def __init__(self, mapping, image_folder: Path):
        super().__init__()
        self.mapping = mapping
        self.image_folder = image_folder
        self.sorted_root = image_folder / '==SORTED=='
        self.sorted_root.mkdir(exist_ok=True)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        top = QHBoxLayout()
        self.image_label = QLabel('')
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(600, 400)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        top.addWidget(self.image_label, 1)

        side = QVBoxLayout()
        side.addWidget(QLabel('Folders (click to move)'))
        self.buttons = {}
        for k, folder in mapping.items():
            btn = QPushButton(f'{k} → {folder}')
            btn.clicked.connect(self._make_move_callback(k))
            side.addWidget(btn)
            self.buttons[k] = btn
        top.addLayout(side)
        self.layout.addLayout(top)

        nav = QHBoxLayout()
        undo_btn = QPushButton('Undo (Ctrl+Z)')
        undo_btn.clicked.connect(self.undo)
        skip_btn = QPushButton('Skip (Ctrl+N)')
        skip_btn.clicked.connect(self.skip)
        nav.addWidget(undo_btn)
        nav.addWidget(skip_btn)
        self.layout.addLayout(nav)

        # shortcuts
        from PyQt5.QtWidgets import QShortcut
        for k in mapping.keys():
            QShortcut(QKeySequence(k), self, activated=self._make_move_callback(k))

        QShortcut(QKeySequence('Ctrl+Z'), self, activated=self.undo)
        QShortcut(QKeySequence('Ctrl+N'), self, activated=self.skip)

        self.images = deque(self._collect_images())
        self.current = None
        # action_stack holds tuples: (action_type, dst, original)
        # only 'move' actions are undoable
        self.action_stack = []
        self.load_next()

    def _collect_images(self):
        imgs = []
        for p in sorted(self.image_folder.iterdir()):
            if p.is_file() and p.suffix.lower() in SUPPORTED:
                if p.parent.name == '==SORTED==':
                    continue
                imgs.append(p)
        logger.debug('Collected %d images from %s', len(imgs), str(self.image_folder))
        return imgs

    def _make_move_callback(self, k):
        def cb():
            self.move_current_to(k)

        return cb

    def load_next(self):
        try:
            self.current = self.images.popleft()
        except IndexError:
            self.current = None
        if not self.current:
            self.image_label.setText('No more images')
            logger.debug('No more images to show')
            return
        logger.debug('Loading image: %s', str(self.current))
        pix = QPixmap(str(self.current))
        if pix.isNull():
            self.load_next()
            return
        self.image_label.setPixmap(pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def animate_and_run(self, direction='right', on_finished=None):
        # animations removed — run the callback immediately
        if on_finished:
            on_finished()

    def move_current_to(self, hotkey):
        if not self.current:
            return
        folder = self.mapping[hotkey]
        dest_dir = self.sorted_root / folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        original = self.current

        def do_move():
            dst = dest_dir / original.name
            logger.debug('Moving %s -> %s', str(original), str(dst))
            try:
                shutil.move(str(original), str(dst))
            except Exception as e:
                logger.exception('Move failed')
                QMessageBox.warning(self, 'Move failed', str(e))
                return
            # push undo info (action_type, dst path, original path)
            self.action_stack.append(('move', dst, original))
            logger.debug('Moved and pushed undo: %s -> %s', str(dst), str(original))
            self.load_next()

        self.animate_and_run('right', on_finished=do_move)

    def skip(self):
        # animate left and load next without moving
        if not self.current:
            return

        def after():
            logger.debug('Skipped image: %s', str(self.current))
            self.load_next()

        self.animate_and_run('left', on_finished=after)

    def undo(self):
        if not self.action_stack:
            return
        action = self.action_stack.pop()
        if not action:
            return
        action_type = action[0]
        if action_type != 'move':
            logger.debug('Undo skipped for non-move action: %s', action_type)
            return
        _, dst, original = action
        if not dst.exists():
            logger.debug('Undo target no longer exists: %s', str(dst))
            return
        logger.debug('Undoing move: %s -> %s', str(dst), str(original))
        try:
            shutil.move(str(dst), str(original))
        except Exception as e:
            logger.exception('Undo failed')
            QMessageBox.warning(self, 'Undo failed', str(e))
            return
        # reinsert original at front of queue
        self.images.appendleft(original)
        logger.debug('Undo completed, reinserted %s', str(original))
        self.load_next()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Image Tinder Sorter')
        self.resize(1000, 700)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        self.setup = SetupPage(self.on_setup_done)
        self.stack.addWidget(self.setup)

    def on_setup_done(self, mapping):
        image_folder = Path('Image').resolve()
        image_folder.mkdir(parents=True, exist_ok=True)
        logger.debug('Using image folder: %s', str(image_folder))
        self.sort_page = SortPage(mapping, image_folder)
        self.stack.addWidget(self.sort_page)
        self.stack.setCurrentWidget(self.sort_page)


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
