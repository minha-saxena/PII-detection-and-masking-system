"""
PDF reconstruction with masked content
"""
from typing import List
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.colors import black
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import RectangleObject
import io
from models.schemas import Detection
from core.logger import log


class PDFReconstructor:
    """Reconstructs PDF with masked PII"""
    
    def __init__(self):
        log.info("PDFReconstructor initialized")
    
    def create_masked_pdf(
        self,
        original_pdf_path: str,
        detections: List[Detection],
        output_path: str,
        mask_char: str = "█"
    ) -> str:
        """
        Create a new PDF with PII masked using black boxes
        
        Args:
            original_pdf_path: Path to original PDF
            detections: List of PII detections
            output_path: Path to save masked PDF
            mask_char: Character to use for masking (default: black box)
        
        Returns:
            Path to masked PDF
        """
        try:
            log.info(f"Creating masked PDF with {len(detections)} detections")
            
            # Read original PDF
            reader = PdfReader(original_pdf_path)
            writer = PdfWriter()
            
            # Group detections by page
            detections_by_page = self._group_detections_by_page(detections)
            
            # Process each page
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                
                # Get detections for this page
                page_detections = detections_by_page.get(page_num + 1, [])
                
                if page_detections:
                    # Apply redactions to this page
                    page = self._apply_redactions(page, page_detections)
                
                writer.add_page(page)
            
            # Write output
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
            
            log.info(f"Masked PDF saved to {output_path}")
            return output_path
        
        except Exception as e:
            log.error(f"PDF reconstruction failed: {str(e)}")
            raise
    
    def _group_detections_by_page(
        self, 
        detections: List[Detection]
    ) -> dict:
        """
        Group detections by page number
        
        Args:
            detections: List of detections
        
        Returns:
            Dictionary mapping page_number -> list of detections
        """
        by_page = {}
        
        for detection in detections:
            page_num = detection.page_number or 1
            if page_num not in by_page:
                by_page[page_num] = []
            by_page[page_num].append(detection)
        
        return by_page
    
    def _apply_redactions(self, page, detections: List[Detection]):
        """
        Apply black box redactions to a page

        Note: This method is currently not implemented and returns the
        original page unchanged. Use create_simple_masked_pdf for text-based
        masking as an alternative.

        Args:
            page: PyPDF2 page object
            detections: List of detections for this page

        Returns:
            Modified page object
        """
        log.warning(
            "PDF redaction not implemented - returning original page. "
            "Use create_simple_masked_pdf for text-based masking."
        )
        # TODO: Implement actual PDF redaction using pdfplumber for text
        # position extraction and PyPDF2 page merging
        raise NotImplementedError(
            "PDF redaction is not yet implemented. "
            "Use create_simple_masked_pdf as an alternative."
        )    
    def create_simple_masked_pdf(
        self,
        text_content: str,
        detections: List[Detection],
        output_path: str,
        pagesize=letter
    ) -> str:
        """
        Create a simple PDF from masked text (alternative approach)
        
        Args:
            text_content: Original text content
            detections: List of detections
            output_path: Output path
            pagesize: Page size (default: letter)
        
        Returns:
            Path to created PDF
        """
        try:
            log.info("Creating simple masked PDF from text")
            
            # Apply masking to text
            masked_text = self._mask_text(text_content, detections)
            
            # Create PDF
            can = canvas.Canvas(output_path, pagesize=pagesize)
            width, height = pagesize
            
            # Set up text object
            text_object = can.beginText(50, height - 50)
            text_object.setFont("Helvetica", 10)
            
            # Split text into lines
            lines = masked_text.split('\n')
            
            for line in lines:
                # Handle page breaks
                if text_object.getY() < 50:
                    can.drawText(text_object)
                    can.showPage()
                    text_object = can.beginText(50, height - 50)
                    text_object.setFont("Helvetica", 10)
                
                text_object.textLine(line)
            
            can.drawText(text_object)
            can.save()
            
            log.info(f"Simple masked PDF created at {output_path}")
            return output_path
        
        except Exception as e:
            log.error(f"Simple PDF creation failed: {str(e)}")
            raise
    
    def _mask_text(self, text: str, detections: List[Detection]) -> str:
        """
        Apply masking to text content
        
        Args:
            text: Original text
            detections: List of detections
        
        Returns:
            Masked text
        """
        # Filter detections with valid positions
        valid_detections = [
            d for d in detections
            if d.start_pos is not None 
            and d.end_pos is not None
            and d.start_pos >= 0
            and d.end_pos >= d.start_pos
            and d.start_pos < len(text)
        ]
        
        # Sort detections by position (reverse order to avoid offset issues)
        sorted_detections = sorted(valid_detections, key=lambda d: d.start_pos, reverse=True)
        
        # Convert to list for easier manipulation
        text_chars = list(text)
        
        # Replace each detection with mask characters
        for detection in sorted_detections:
            start = detection.start_pos
            end = min(detection.end_pos, len(text))  # Clamp to text length
            
            # Replace with black boxes
            mask_length = end - start
            mask = "█" * mask_length
            
            # Apply mask
            text_chars[start:end] = list(mask)        
        return ''.join(text_chars)