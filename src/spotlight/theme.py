"""Professional local visual system for the BEEP desktop application."""

from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QSizePolicy, QWidget

# Color tokens
BACKGROUND = "#07080C"
SURFACE_LOW = "#0C0E14"
SURFACE = "#11141D"
SURFACE_HIGH = "#171B26"
BORDER = "#292F3D"
TEXT_PRIMARY = "#F0F3FA"
TEXT_MUTED = "#A7AFC1"
BLUE_ACCENT = "#25C2FF"
BLUE_HOVER = "#6BD5FF"
PINK_ACCENT = "#FF4FB4"
PINK_HOVER = "#FF82CB"
SUCCESS = "#51D99A"
WARNING = "#FFB454"
ERROR = "#FF719E"

# One 8-point spacing system. SPACE_HALF is restricted to optical adjustments.
SPACE_HALF = 4
SPACE_1 = 8
SPACE_2 = 16
SPACE_3 = 24
SPACE_4 = 32
SPACE_5 = 40
SPACING_SCALE = (SPACE_1, SPACE_2, SPACE_3, SPACE_4, SPACE_5)

# Exactly three semantic typography levels.
TYPOGRAPHY_DISPLAY = "display"
TYPOGRAPHY_SECTION = "section"
TYPOGRAPHY_BODY = "body"
TYPOGRAPHY_LEVELS = (
    TYPOGRAPHY_DISPLAY,
    TYPOGRAPHY_SECTION,
    TYPOGRAPHY_BODY,
)
DISPLAY_POINT_SIZE = 24
SECTION_POINT_SIZE = 13
BODY_POINT_SIZE = 10

# Responsive presentation constants, expressed in Qt logical pixels.
EXPANDED_BREAKPOINT = 2200
# Below the expanded 1440p workspace, stack candidate content so summaries retain
# a comfortable reading measure instead of competing for a narrow side-by-side pane.
NARROW_REVIEW_BREAKPOINT = 2200
SIDEBAR_COMPACT_WIDTH = 224
SIDEBAR_EXPANDED_MIN = 240
SIDEBAR_EXPANDED_MAX = 288
HEADER_COMPACT_HEIGHT = 80
HEADER_EXPANDED_HEIGHT = 88
PLAYER_PANE_PERCENT = 64

# Bounded presentation motion.
MOTION_MIN_MS = 150
MOTION_DEFAULT_MS = 180
MOTION_MAX_MS = 250
REDUCED_MOTION_ENVIRONMENT_VARIABLE = "BEEP_REDUCED_MOTION"


def clamp_motion_duration(duration_ms: int) -> int:
    """Keep decorative motion inside the approved duration range."""
    return max(MOTION_MIN_MS, min(duration_ms, MOTION_MAX_MS))


def reduced_motion_requested() -> bool:
    """Honor an explicit override and the Windows client-animation preference."""
    override = os.environ.get(REDUCED_MOTION_ENVIRONMENT_VARIABLE, "").casefold()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    if sys.platform != "win32":
        return False

    try:
        win_dll = getattr(ctypes, "WinDLL")
        user32 = win_dll("user32", use_last_error=True)
        animations_enabled = ctypes.c_int()
        # SPI_GETCLIENTAREAANIMATION
        succeeded = user32.SystemParametersInfoW(
            0x1042,
            0,
            ctypes.byref(animations_enabled),
            0,
        )
    except (AttributeError, OSError):
        return False
    return bool(succeeded) and not bool(animations_enabled.value)


def _linear_channel(channel: int) -> float:
    normalized = channel / 255
    return (
        normalized / 12.92
        if normalized <= 0.04045
        else ((normalized + 0.055) / 1.055) ** 2.4
    )


def contrast_ratio(foreground: str, background: str) -> float:
    """Calculate the WCAG contrast ratio for two opaque hexadecimal colors."""
    colors = (QColor(foreground), QColor(background))
    luminances: list[float] = []
    for color in colors:
        luminances.append(
            0.2126 * _linear_channel(color.red())
            + 0.7152 * _linear_channel(color.green())
            + 0.0722 * _linear_channel(color.blue())
        )
    lighter, darker = sorted(luminances, reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def classify_status(message: str) -> str:
    """Classify existing status copy without changing its diagnostic content."""
    normalized = message.casefold()
    if any(
        token in normalized
        for token in ("error", "failed", "failure", "unavailable", "timed out")
    ):
        return "error"
    if any(
        token in normalized
        for token in (
            "preparing",
            "reading",
            "extracting",
            "transcribing",
            "analyzing",
            "loading",
            "seeking",
        )
    ):
        return "active"
    if any(
        token in normalized
        for token in ("complete", "saved", "created", "opened", "ready")
    ):
        return "success"
    return "neutral"


class StatusLabel(QLabel):
    """A status label that exposes existing text changes to presentation code."""

    status_changed = Signal(str)

    def __init__(self, text: str = "") -> None:
        super().__init__()
        self.setText(text)

    def setText(self, text: str) -> None:
        changed = text != self.text()
        super().setText(text)
        self.setAccessibleDescription(text)
        if changed:
            self.status_changed.emit(text)


class GradientWordmark(QLabel):
    """A crisp, local blue-to-pink BEEP wordmark with a text fallback."""

    gradient_colors = (BLUE_ACCENT, PINK_ACCENT)

    def __init__(self) -> None:
        super().__init__("BEEP")
        self.setObjectName("GradientWordmark")
        self.setAccessibleName("BEEP")
        self.setAccessibleDescription("BEEP application wordmark")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        font = QFont("Segoe UI Variable Display")
        if not font.exactMatch():
            font = QFont("Segoe UI")
        font.setPointSize(DISPLAY_POINT_SIZE)
        font.setWeight(QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        self.setFont(font)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self.font())
        return QSize(
            metrics.horizontalAdvance(self.text()) + SPACE_1, metrics.height() + 8
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.width() <= 0 or self.height() <= 0:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        if not painter.isActive():
            super().paintEvent(event)
            return
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, QColor(BLUE_ACCENT))
        gradient.setColorAt(1.0, QColor(PINK_ACCENT))
        painter.setPen(QPen(QBrush(gradient), 0))
        painter.setFont(self.font())
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.text(),
        )


class MotionController(QObject):
    """Own short, coalesced opacity transitions and release them on completion."""

    def __init__(self, reduced_motion: bool | None = None) -> None:
        super().__init__()
        self.reduced_motion = (
            reduced_motion_requested() if reduced_motion is None else reduced_motion
        )
        self._animations: dict[QWidget, QPropertyAnimation] = {}

    @property
    def active_animation_count(self) -> int:
        return len(self._animations)

    def fade_in(self, widget: QWidget, duration_ms: int = MOTION_DEFAULT_MS) -> bool:
        """Fade a presentation widget without delaying its state change."""
        self._stop(widget)
        if self.reduced_motion or not widget.isVisible():
            # PySide accepts nullptr here, but its generated type stub omits it.
            widget.setGraphicsEffect(None)  # pyright: ignore[reportArgumentType]
            return False

        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.72)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(clamp_motion_duration(duration_ms))
        animation.setStartValue(0.72)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(
            lambda target=widget, current=animation: self._finish(target, current)
        )
        self._animations[widget] = animation
        animation.start()
        return True

    def _stop(self, widget: QWidget) -> None:
        animation = self._animations.pop(widget, None)
        if animation is not None:
            animation.stop()
            animation.deleteLater()
        # PySide accepts nullptr here, but its generated type stub omits it.
        widget.setGraphicsEffect(None)  # pyright: ignore[reportArgumentType]

    def _finish(self, widget: QWidget, animation: QPropertyAnimation) -> None:
        if self._animations.get(widget) is not animation:
            return
        self._animations.pop(widget, None)
        # PySide accepts nullptr here, but its generated type stub omits it.
        widget.setGraphicsEffect(None)  # pyright: ignore[reportArgumentType]
        animation.deleteLater()


DARK_STYLESHEET = f"""
QWidget {{
    background-color: {BACKGROUND};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI";
    font-size: {BODY_POINT_SIZE}pt;
}}

QWidget[typographyLevel="display"] {{
    font-size: {DISPLAY_POINT_SIZE}pt;
    font-weight: 700;
}}

QWidget[typographyLevel="section"],
QLabel#SectionTitle,
QLabel#SidebarTitle {{
    font-size: {SECTION_POINT_SIZE}pt;
    font-weight: 650;
}}

QFrame#Header {{
    background-color: {SURFACE_LOW};
    border-bottom: 1px solid {BORDER};
}}

QFrame#HeaderDivider {{
    background-color: {BORDER};
    min-width: 1px;
    max-width: 1px;
}}

QLabel#HeaderCaption,
QLabel#StatusCaption,
QLabel#SidebarEyebrow {{
    background: transparent;
    color: {TEXT_MUTED};
    font-weight: 700;
}}

QLabel#HeaderProject {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-size: {SECTION_POINT_SIZE}pt;
    font-weight: 650;
}}

QFrame#FutureHeaderRegion,
QFrame#FutureSidebarRegion {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QLabel#FutureLabel {{
    background: transparent;
    color: #7F8799;
    font-weight: 600;
}}

QFrame#Sidebar {{
    background-color: {SURFACE_LOW};
    border-right: 1px solid {BORDER};
}}

QLabel#SidebarTitle {{
    background: transparent;
    color: {TEXT_PRIMARY};
}}

QLabel#ActiveProject {{
    background-color: {SURFACE_HIGH};
    color: {PINK_ACCENT};
    border: 1px solid #343A4B;
    border-radius: 8px;
    padding: 12px;
    font-weight: 650;
}}

QFrame#ActiveNavigation {{
    background-color: #142333;
    border-left: 4px solid {BLUE_ACCENT};
    border-radius: 8px;
}}

QLabel#ActiveNavigationText {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-weight: 650;
}}

QFrame#Card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QFrame#PlayerCard {{
    background-color: {SURFACE};
    border: 1px solid #313746;
    border-radius: 12px;
}}

QVideoWidget#VideoOutput {{
    background-color: #000000;
    border: 1px solid #323848;
    border-radius: 8px;
}}

QLabel#PlaybackMessage {{
    background-color: {SURFACE_HIGH};
    color: {TEXT_MUTED};
    border-left: 4px solid {BLUE_ACCENT};
    border-radius: 4px;
    padding: 8px 12px;
}}

QLabel#PlaybackTime {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-family: "Cascadia Mono", "Consolas";
    font-weight: 600;
}}

QLabel#SeekingStatus {{
    background: transparent;
    color: {PINK_ACCENT};
    font-weight: 700;
}}

QLabel#SectionTitle {{
    background: transparent;
    color: {TEXT_PRIMARY};
}}

QLabel#MutedText {{
    background: transparent;
    color: {TEXT_MUTED};
}}

QPushButton {{
    min-height: 40px;
    padding: 0 16px;
    background-color: {BLUE_ACCENT};
    color: #031018;
    border: 1px solid {BLUE_ACCENT};
    border-radius: 8px;
    font-weight: 700;
}}

QPushButton:hover {{
    background-color: {BLUE_HOVER};
    border-color: {BLUE_HOVER};
}}

QPushButton:pressed {{
    background-color: #0BA6E3;
}}

QPushButton:focus {{
    border: 2px solid {TEXT_PRIMARY};
}}

QPushButton:disabled {{
    background-color: #202532;
    border-color: #2B3140;
    color: #747D91;
}}

QPushButton#TranscribeButton {{
    background-color: {PINK_ACCENT};
    border-color: {PINK_ACCENT};
    color: #170710;
}}

QPushButton#TranscribeButton:hover {{
    background-color: {PINK_HOVER};
    border-color: {PINK_HOVER};
}}

QPushButton#AnalyzeButton,
QPushButton#CpuButton,
QPushButton#SearchNavigationButton,
QPushButton#SidebarAction {{
    background-color: transparent;
    border-color: #444C61;
    color: {TEXT_PRIMARY};
}}

QPushButton#AnalyzeButton:hover,
QPushButton#SearchNavigationButton:hover,
QPushButton#SidebarAction:hover {{
    background-color: #132A38;
    border-color: {BLUE_ACCENT};
    color: {BLUE_ACCENT};
}}

QPushButton#CpuButton {{
    border-color: {PINK_ACCENT};
    color: {PINK_ACCENT};
}}

QPushButton#ProcessingAction {{
    text-align: left;
    padding-left: 16px;
}}

QPushButton#PlaybackButton {{
    min-width: 80px;
}}

QPlainTextEdit,
QTextEdit {{
    background-color: #0A0C12;
    color: #E1E6F0;
    border: 1px solid #303646;
    border-radius: 8px;
    padding: 16px;
    selection-background-color: #195576;
}}

QPlainTextEdit:focus,
QTextEdit:focus,
QLineEdit:focus,
QListWidget:focus {{
    border: 2px solid {BLUE_ACCENT};
}}

QPlainTextEdit#TranscriptView {{
    font-family: "Segoe UI";
}}

QTextEdit#CandidateDetails {{
    background-color: {SURFACE_HIGH};
}}

QListWidget {{
    background-color: #0A0C12;
    color: #E1E6F0;
    border: 1px solid #303646;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}

QListWidget::item {{
    min-height: 56px;
    padding: 8px 12px;
    margin: 4px;
    border-radius: 8px;
}}

QListWidget::item:hover {{
    background-color: {SURFACE_HIGH};
}}

QListWidget::item:selected {{
    background-color: #184D68;
    color: {TEXT_PRIMARY};
    border-left: 4px solid {PINK_ACCENT};
}}

QListWidget#CandidateList::item {{
    min-height: 72px;
}}

QLineEdit {{
    min-height: 40px;
    padding: 0 12px;
    background-color: #0A0C12;
    color: #E1E6F0;
    border: 1px solid #303646;
    border-radius: 8px;
    selection-background-color: #195576;
}}

QListWidget#RecentProjects {{
    background-color: transparent;
    border: none;
    padding: 0;
}}

QListWidget#RecentProjects::item {{
    min-height: 48px;
    padding: 8px;
    margin: 0 0 4px 0;
    border-radius: 8px;
}}

QLabel#ErrorText {{
    color: {ERROR};
    font-weight: 650;
}}

QSlider#PlaybackTimeline::groove:horizontal {{
    height: 8px;
    background-color: #2B3241;
    border-radius: 4px;
}}

QSlider#PlaybackTimeline::sub-page:horizontal {{
    background-color: {BLUE_ACCENT};
    border-radius: 4px;
}}

QSlider#PlaybackTimeline::handle:horizontal {{
    width: 16px;
    margin: -4px 0;
    background-color: {PINK_ACCENT};
    border: 2px solid {SURFACE_LOW};
    border-radius: 8px;
}}

QSlider#PlaybackTimeline:focus {{
    border: 2px solid {TEXT_PRIMARY};
}}

QSplitter::handle {{
    background-color: {BACKGROUND};
    width: 4px;
    height: 4px;
}}

QSplitter::handle:hover {{
    background-color: {BLUE_ACCENT};
}}

QProgressBar {{
    min-height: 8px;
    max-height: 8px;
    background-color: #262D3B;
    border: none;
    border-radius: 4px;
    color: transparent;
}}

QProgressBar::chunk {{
    border-radius: 4px;
    background-color: {PINK_ACCENT};
}}

QFrame#StatusBar {{
    background-color: {SURFACE_LOW};
    border-top: 1px solid {BORDER};
}}

QFrame#StatusActivity {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-left: 4px solid #778096;
    border-radius: 8px;
}}

QFrame#StatusActivity[statusKind="active"] {{
    border-left-color: {BLUE_ACCENT};
}}

QFrame#StatusActivity[statusKind="success"] {{
    border-left-color: {SUCCESS};
}}

QFrame#StatusActivity[statusKind="error"] {{
    border-left-color: {ERROR};
}}

QLabel#StatusGlyph {{
    background: transparent;
    color: #778096;
    font-weight: 700;
}}

QLabel#StatusGlyph[statusKind="active"] {{ color: {BLUE_ACCENT}; }}
QLabel#StatusGlyph[statusKind="success"] {{ color: {SUCCESS}; }}
QLabel#StatusGlyph[statusKind="error"] {{ color: {ERROR}; }}

QLabel#StatusValue {{
    background: transparent;
    color: #E6EAF3;
    font-weight: 600;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 4px 2px;
}}

QScrollBar::handle:vertical {{
    background: #40485C;
    min-height: 32px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {BLUE_ACCENT};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""
