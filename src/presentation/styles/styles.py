DARK_STYLE = """
QMainWindow, QDialog {
    background-color: #121212;
    color: #ffffff;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
}

QWidget {
    color: #ffffff;
    font-family: 'Segoe UI', system-ui, sans-serif;
}

/* Sidebar */
QFrame#SidebarFrame {
    background-color: #000000;
    border-right: 1px solid #1f1f1f;
}

QPushButton#NavButton {
    background-color: transparent;
    color: #b3b3b3;
    border: none;
    border-radius: 6px;
    padding: 12px 16px;
    font-size: 14px;
    font-weight: 600;
    text-align: left;
}

QPushButton#NavButton:hover {
    background-color: #1a1a1a;
    color: #ffffff;
}

QPushButton#NavButton:checked {
    background-color: #282828;
    color: #1db954;
    font-weight: 700;
}

/* Inputs & Combo Boxes */
QLineEdit {
    background-color: #1f1f1f;
    border: 1px solid #2e2e2e;
    border-radius: 8px;
    padding: 12px 16px;
    color: #ffffff;
    font-size: 14px;
    selection-background-color: #1db954;
}

QLineEdit:focus {
    border: 1px solid #1db954;
}

QComboBox {
    background-color: #1f1f1f;
    border: 1px solid #2e2e2e;
    border-radius: 8px;
    padding: 10px 14px;
    color: #ffffff;
    font-size: 14px;
}

QComboBox:hover {
    border-color: #1db954;
}

QComboBox QAbstractItemView {
    background-color: #1f1f1f;
    selection-background-color: #1db954;
    color: #ffffff;
    border: 1px solid #2e2e2e;
    padding: 4px;
}

/* Selector de Calidad de Video Vertical */
QListWidget#VideoQualityList {
    background-color: #181818;
    border: 1px solid #282828;
    border-radius: 8px;
    outline: none;
    padding: 4px;
}

QListWidget#VideoQualityList::item {
    background-color: transparent;
    border-radius: 6px;
    margin: 2px 4px;
    padding: 4px;
}

QListWidget#VideoQualityList::item:hover {
    background-color: #282828;
}

QListWidget#VideoQualityList::item:selected {
    background-color: #282828;
    border-left: 3px solid #1db954;
}

/* Primary Action Buttons */
QPushButton#PrimaryButton {
    background-color: #1db954;
    color: #000000;
    border: none;
    border-radius: 20px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: 700;
}

QPushButton#PrimaryButton:hover {
    background-color: #1ed760;
}

QPushButton#PrimaryButton:pressed {
    background-color: #169c46;
}

QPushButton#PrimaryButton:disabled {
    background-color: #282828;
    color: #727272;
}

/* Secondary Buttons */
QPushButton#SecondaryButton {
    background-color: #282828;
    color: #ffffff;
    border: 1px solid #333333;
    border-radius: 18px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#SecondaryButton:hover {
    background-color: #3e3e3e;
    border-color: #ffffff;
}

/* Toggle Buttons */
QPushButton#ModeButton {
    background-color: #1f1f1f;
    color: #b3b3b3;
    border: 1px solid #2e2e2e;
    border-radius: 16px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#ModeButton:hover {
    color: #ffffff;
    border-color: #1db954;
}

QPushButton#ModeButton:checked {
    background-color: #1db954;
    color: #000000;
    font-weight: 700;
    border-color: #1db954;
}

/* Progress Bar */
QProgressBar {
    border: none;
    background-color: #282828;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
    font-size: 12px;
    font-weight: 600;
}

QProgressBar::chunk {
    background-color: #1db954;
    border-radius: 4px;
}

/* Tables & Lists */
QTableWidget {
    background-color: #181818;
    border: 1px solid #282828;
    gridline-color: #282828;
    border-radius: 8px;
}

QHeaderView::section {
    background-color: #282828;
    color: #b3b3b3;
    padding: 10px;
    border: none;
    font-weight: 700;
}

/* Cards & Elevated Containers */
QFrame#Card {
    background-color: #181818;
    border: 1px solid #282828;
    border-radius: 12px;
    padding: 20px;
}

QFrame#DownloadCard {
    background-color: #181818;
    border: 1px solid #282828;
    border-radius: 10px;
    padding: 16px;
}

QFrame#DownloadCard:hover {
    border-color: #3e3e3e;
    background-color: #202020;
}
"""
