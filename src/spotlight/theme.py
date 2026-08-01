"""Local visual theme for the BEEP desktop application."""

BACKGROUND = "#07070A"
BLUE_ACCENT = "#25B8FF"
PINK_ACCENT = "#FF3DAE"

DARK_STYLESHEET = f"""
QWidget {{
    background-color: {BACKGROUND};
    color: #F4F6FF;
    font-size: 10pt;
}}

QFrame#Header {{
    background-color: #0B0B11;
    border-bottom: 1px solid #242438;
}}

QLabel#Brand {{
    color: #FFFFFF;
    font-size: 22pt;
    font-weight: 700;
}}

QLabel#BrandAccent {{
    color: {PINK_ACCENT};
    font-size: 22pt;
    font-weight: 700;
}}

QLabel#Eyebrow {{
    color: {BLUE_ACCENT};
    font-size: 8pt;
    font-weight: 700;
}}

QFrame#Sidebar {{
    background-color: #0B0B11;
    border-right: 1px solid #242438;
}}

QLabel#SidebarTitle, QLabel#StatusCaption {{
    color: #777D91;
    font-size: 8pt;
    font-weight: 700;
}}

QLabel#ActiveProject {{
    background-color: #101018;
    color: {PINK_ACCENT};
    border: 1px solid #27273A;
    border-radius: 5px;
    padding: 8px;
    font-weight: 650;
}}

QFrame#ActiveNavigation {{
    background-color: #111827;
    border-left: 3px solid {BLUE_ACCENT};
    border-radius: 4px;
}}

QLabel#ActiveNavigationText {{
    background: transparent;
    color: #FFFFFF;
    font-weight: 600;
}}

QFrame#Card {{
    background-color: #101018;
    border: 1px solid #27273A;
    border-radius: 10px;
}}

QLabel#SectionTitle {{
    background: transparent;
    color: #FFFFFF;
    font-size: 13pt;
    font-weight: 650;
}}

QLabel#MutedText {{
    background: transparent;
    color: #8C92A8;
}}

QPushButton {{
    min-height: 34px;
    padding: 0 18px;
    background-color: {BLUE_ACCENT};
    color: #03060A;
    border: 1px solid {BLUE_ACCENT};
    border-radius: 6px;
    font-weight: 700;
}}

QPushButton:hover {{
    background-color: #62CBFF;
    border-color: #62CBFF;
}}

QPushButton:pressed {{
    background-color: #0099E5;
}}

QPushButton:disabled {{
    background-color: #222432;
    border-color: #303243;
    color: #676C80;
}}

QPushButton#TranscribeButton {{
    background-color: {PINK_ACCENT};
    border-color: {PINK_ACCENT};
    color: #090309;
}}

QPushButton#TranscribeButton:hover {{
    background-color: #FF73C5;
    border-color: #FF73C5;
}}

QPushButton#AnalyzeButton {{
    background-color: transparent;
    border-color: {BLUE_ACCENT};
    color: {BLUE_ACCENT};
}}

QPushButton#AnalyzeButton:hover {{
    background-color: #102A3A;
    color: #FFFFFF;
}}

QPushButton#CpuButton {{
    background-color: transparent;
    border-color: {PINK_ACCENT};
    color: {PINK_ACCENT};
}}

QPlainTextEdit {{
    background-color: #09090E;
    color: #DDE2F2;
    border: 1px solid #2B2D40;
    border-radius: 7px;
    padding: 10px;
    selection-background-color: #174D6B;
}}

QPlainTextEdit:focus {{
    border-color: {BLUE_ACCENT};
}}

QListWidget {{
    background-color: #09090E;
    color: #DDE2F2;
    border: 1px solid #2B2D40;
    border-radius: 7px;
    padding: 6px;
    outline: none;
}}

QListWidget::item {{
    min-height: 48px;
    padding: 8px;
    border-bottom: 1px solid #202230;
}}

QListWidget::item:selected {{
    background-color: #174D6B;
    color: #FFFFFF;
}}

QLineEdit {{
    min-height: 34px;
    padding: 0 10px;
    background-color: #09090E;
    color: #DDE2F2;
    border: 1px solid #2B2D40;
    border-radius: 6px;
    selection-background-color: #174D6B;
}}

QLineEdit:focus {{
    border-color: {BLUE_ACCENT};
}}

QPushButton#SearchNavigationButton {{
    min-height: 32px;
    padding: 0 12px;
    background-color: transparent;
    border-color: #3A3D53;
    color: #DDE2F2;
}}

QPushButton#SidebarAction {{
    min-height: 30px;
    padding: 0 7px;
    background-color: transparent;
    border-color: #3A3D53;
    color: #DDE2F2;
    font-size: 8pt;
}}

QPushButton#SidebarAction:hover {{
    border-color: {BLUE_ACCENT};
    color: {BLUE_ACCENT};
}}

QListWidget#RecentProjects {{
    background-color: transparent;
    border: none;
    padding: 0;
    font-size: 8pt;
}}

QListWidget#RecentProjects::item {{
    min-height: 36px;
    padding: 6px;
    border-bottom: 1px solid #202230;
}}

QLabel#ErrorText {{
    color: {PINK_ACCENT};
}}

QPushButton#SearchNavigationButton:hover {{
    border-color: {BLUE_ACCENT};
    color: {BLUE_ACCENT};
}}

QProgressBar {{
    height: 8px;
    background-color: #202230;
    border: none;
    border-radius: 4px;
    color: transparent;
}}

QProgressBar::chunk {{
    border-radius: 4px;
    background-color: {PINK_ACCENT};
}}

QFrame#StatusBar {{
    background-color: #0B0B11;
    border-top: 1px solid #242438;
}}

QLabel#StatusValue {{
    color: #E6E9F5;
    font-weight: 600;
}}

QScrollBar:vertical {{
    background: #0A0A10;
    width: 10px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: #35384C;
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {BLUE_ACCENT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""
