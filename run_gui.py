import sys
from PySide6.QtWidgets import QApplication
from gui.app import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(900, 540)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
