"""
PDF reconstruction with masked content
"""
from typing import List
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter
from models.schemas import Detection
from core.logger import log


class PDFReconstructor:
    """Reconstructs PDF with masked PII"""

    def __init__(self):
        log.info("PDFReconstructor initialized")

    def create_simple_masked_pdf(
        self,
        text_content: str,
        detections: List[Detection],
        output_path: str,
        pagesize=letter
    ) -> str:
        """
        Create a PDF from masked text with proper page overflow and word-wrap.

        Args:
            text_content: Original text content
            detections: List of PII detections
            output_path: Output file path
            pagesize: Page size tuple (default: letter)

        Returns:
            Path to created PDF
        """
        try:
            log.info("Creating simple masked PDF from text")

            masked_text = self._mask_text(text_content, detections)

            can = canvas.Canvas(output_path, pagesize=pagesize)
            width, height = pagesize

            margin_x = 50
            margin_top = 50
            margin_bottom = 50
            font_name = "Helvetica"
            font_size = 10
            line_height = font_size * 1.5
            max_width = width - 2 * margin_x

            can.setFont(font_name, font_size)
            y = height - margin_top

            for raw_line in masked_text.split('\n'):
                # Word-wrap each line
                wrapped_lines = self._wrap_line(raw_line, max_width, can, font_name, font_size)

                for line in wrapped_lines:
                    if y < margin_bottom + line_height:
                        can.showPage()
                        can.setFont(font_name, font_size)
                        y = height - margin_top

                    can.drawString(margin_x, y, line)
                    y -= line_height

            can.save()

            log.info(f"Simple masked PDF created at {output_path}")
            return output_path

        except Exception as e:
            log.error(f"Simple PDF creation failed: {str(e)}")
            raise

    def _wrap_line(
        self,
        line: str,
        max_width: float,
        can: canvas.Canvas,
        font_name: str,
        font_size: int
    ) -> List[str]:
        """Word-wrap a line to fit within max_width points."""
        if not line.strip():
            return ['']

        words = line.split(' ')
        result = []
        current = ''

        for word in words:
            candidate = f"{current} {word}".strip() if current else word
            if can.stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
            else:
                if current:
                    result.append(current)
                # If single word is too long, force it onto its own line
                current = word

        if current:
            result.append(current)

        return result if result else ['']

    def _mask_text(self, text: str, detections: List[Detection]) -> str:
        """Apply block masking to text at detected positions."""
        valid_detections = [
            d for d in detections
            if d.start_pos is not None
            and d.end_pos is not None
            and d.start_pos >= 0
            and d.end_pos > d.start_pos
            and d.start_pos < len(text)
        ]

        sorted_detections = sorted(valid_detections, key=lambda d: d.start_pos, reverse=True)
        text_chars = list(text)

        for detection in sorted_detections:
            start = detection.start_pos
            end = min(detection.end_pos, len(text))
            text_chars[start:end] = list("█" * (end - start))

        return ''.join(text_chars)