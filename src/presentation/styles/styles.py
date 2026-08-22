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

QLabel#SidebarTitle {
    font-size: 15px;
    font-weight: 800;
    color: #1db954;
    letter-spacing: 0.5px;
    padding-bottom: 16px;
}

QPushButton#NavButton {
    background-color: transparent;
    color: #b3b3b3;
    border: none;
    border-left: 3px solid transparent;
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
    border-left: 3px solid #1db954;
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

/* Encabezados de vista */
QLabel#ViewTitle {
    font-size: 26px;
    font-weight: 800;
    color: #ffffff;
}

QLabel#ViewSubtitle {
    font-size: 13px;
    color: #b3b3b3;
}

/* Banner de estados de análisis */
QLabel#StatusLabel {
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 600;
    border: 1px solid #282828;
    background-color: #181818;
    color: #b3b3b3;
}

QLabel#StatusLabel[state="analyzing"] {
    border: 1px solid #1db954;
    color: #1db954;
    background-color: rgba(29, 185, 84, 0.08);
}

QLabel#StatusLabel[state="success"] {
    border: 1px solid #1db954;
    color: #1ed760;
    background-color: rgba(29, 185, 84, 0.12);
}

QLabel#StatusLabel[state="error"] {
    border: 1px solid #ff6b6b;
    color: #ff6b6b;
    background-color: rgba(255, 107, 107, 0.08);
}

/* Chips informativos */
QLabel#Chip {
    background-color: #1f1f1f;
    border: 1px solid #2e2e2e;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
    color: #b3b3b3;
}

QLabel#ChipAccent {
    background-color: rgba(29, 185, 84, 0.14);
    border: 1px solid #1db954;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
    color: #1db954;
}

/* Previsualización */
QLabel#PreviewTitle {
    font-size: 19px;
    font-weight: 700;
    color: #ffffff;
}

QLabel#PreviewChannel {
    font-size: 13px;
    color: #b3b3b3;
}

QLabel#SectionHeader {
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1.5px;
    color: #727272;
}

QLabel#SynopsisText {
    font-size: 13px;
    color: #d9d9d9;
}

QLabel#FieldLabel {
    font-size: 13px;
    font-weight: 600;
    color: #ffffff;
}

QLabel#HintLabel {
    font-size: 11px;
    color: #b3b3b3;
}

QLabel#SizeEstimate {
    font-size: 13px;
    font-weight: 700;
    color: #1db954;
}

/* Botones de texto (Ver más / Ver menos) */
QPushButton#LinkButton {
    background-color: transparent;
    border: none;
    color: #1db954;
    font-size: 12px;
    font-weight: 700;
    padding: 2px 0px;
    text-align: left;
}

QPushButton#LinkButton:hover {
    text-decoration: underline;
}

/* Tarjetas seleccionables de calidad */
QFrame#QualityCard {
    background-color: #181818;
    border: 1px solid #282828;
    border-radius: 10px;
}

QFrame#QualityCard:hover {
    border-color: #3e3e3e;
    background-color: #1c1c1c;
}

QFrame#QualityCard[selected="true"] {
    border: 1px solid #1db954;
    background-color: rgba(29, 185, 84, 0.06);
}

QRadioButton#QualityRadio {
    background-color: transparent;
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
    spacing: 10px;
}

QRadioButton#QualityRadio::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid #555555;
    background-color: #1f1f1f;
}

QRadioButton#QualityRadio::indicator:hover {
    border-color: #1db954;
}

QRadioButton#QualityRadio::indicator:checked {
    border: 5px solid #1db954;
    background-color: #ffffff;
}

QLabel#QualityBadge {
    background-color: #1db954;
    color: #000000;
    font-size: 10px;
    font-weight: 800;
    padding: 2px 8px;
    border-radius: 4px;
}

QLabel#QualityTechInfo {
    font-size: 11px;
    color: #727272;
}

/* Chips de formato [MP4] [MP3] */
QPushButton#FormatChip {
    background-color: #1f1f1f;
    color: #b3b3b3;
    border: 1px solid #2e2e2e;
    border-radius: 16px;
    padding: 8px 24px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#FormatChip:hover {
    color: #ffffff;
    border-color: #1db954;
}

QPushButton#FormatChip:checked {
    background-color: #1db954;
    color: #000000;
    border-color: #1db954;
}

/* Estados vacíos */
QFrame#EmptyStateCard {
    background-color: #181818;
    border: 1px dashed #2e2e2e;
    border-radius: 12px;
    padding: 40px;
}

QLabel#EmptyStateTitle {
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
}

QLabel#EmptyStateHint {
    font-size: 13px;
    color: #727272;
}

/* Tarjeta de descarga */
QLabel#DownloadCardTitle {
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
}

QLabel#PlatformBadge {
    font-size: 11px;
    color: #1db954;
    font-weight: 700;
    background-color: #1f1f1f;
    padding: 4px 8px;
    border-radius: 4px;
}

QLabel#TelemetryLabel {
    font-size: 12px;
    color: #b3b3b3;
}

QLabel#CardErrorLabel {
    font-size: 11px;
    color: #ff6b6b;
}
"""
