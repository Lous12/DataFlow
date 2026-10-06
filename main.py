import sys

from PySide6.QtWidgets import QApplication

from ui.smart_window import SmartMainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("DataFlow")

    window = SmartMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
