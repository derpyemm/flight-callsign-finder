ERROR_COLOR = "#c62828"
OK_COLOR = "#66bb6a"

STYLESHEET = """
QWidget {
    background: #2b2b2b;
    color: #e8e8e8;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QMainWindow, QFrame {
    background: #2b2b2b;
}

#masthead {
    background: #242424;
    border-bottom: 1px solid #3d3d3d;
}

#brandMark {
    color: #b0b0b0;
    font-size: 11px;
    letter-spacing: 2px;
}

#brandTitle {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 1px;
}

#clockLabel {
    font-size: 18px;
    font-weight: 600;
    color: #e8e8e8;
}

#sectionLabel {
    color: #c8c8c8;
    font-size: 11px;
    letter-spacing: 1px;
    font-weight: 600;
}

#hint, #statusText, #summaryText {
    color: #b0b0b0;
}

#rail, #board, #mapFrame {
    background: #2b2b2b;
}

#pill {
    padding: 3px 8px;
    border: 1px solid #4a4a4a;
    color: #8a8a8a;
}

#pill[state="on"] {
    border-color: #66bb6a;
    color: #66bb6a;
}

#pill[state="off"] {
    border-color: #3d3d3d;
    color: #6a6a6a;
}

QLineEdit, QSpinBox, QTextEdit {
    background: #1f1f1f;
    color: #e8e8e8;
    border: 1px solid #4a4a4a;
    border-radius: 2px;
    padding: 7px 8px;
    selection-background-color: #3d5a80;
}

QLineEdit:focus, QSpinBox:focus {
    border: 1px solid #6a6a6a;
}

QPushButton {
    background: #3d3d3d;
    color: #e8e8e8;
    border: 1px solid #5a5a5a;
    border-radius: 2px;
    padding: 10px 14px;
}

QPushButton:hover {
    background: #4a4a4a;
}

QPushButton:disabled {
    color: #888888;
    background: #333333;
}

QTableWidget QPushButton {
    padding: 2px 8px;
    min-width: 52px;
}

QPushButton#ghost {
    background: transparent;
    padding: 6px 10px;
}

QPushButton#compact {
    padding: 4px 10px;
}

QCheckBox {
    color: #e8e8e8;
    spacing: 8px;
}

QTableWidget {
    background: #1f1f1f;
    alternate-background-color: #252525;
    gridline-color: #3d3d3d;
    border: 1px solid #3d3d3d;
    selection-background-color: #3d5a80;
    selection-color: #ffffff;
}

QHeaderView::section {
    background: #333333;
    color: #d0d0d0;
    border: none;
    border-bottom: 1px solid #3d3d3d;
    border-right: 1px solid #3d3d3d;
    padding: 7px 8px;
}

QSplitter::handle:vertical {
    background: #3d3d3d;
    height: 4px;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background: #2b2b2b;
    border: none;
    width: 10px;
    height: 10px;
}

QScrollBar::handle {
    background: #555555;
    border-radius: 2px;
}

QScrollBar::add-line, QScrollBar::sub-line {
    height: 0;
    width: 0;
}
"""
