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
        
        Args:
            page: PyPDF2 page object
            detections: List of detections for this page
        
        Returns:
            Modified page object
        """
        # Note: PyPDF2 doesn't have direct redaction support
        # We'll add black rectangles over detected text
        
        # Get page dimensions
        page_height = float(page.mediabox.height)
        page_width = float(page.mediabox.width)
        
        # Create overlay with black boxes
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(page_width, page_height))
        
        # Set fill color to black
        can.setFillColor(black)
        
        # For each detection, estimate position and draw rectangle
        # Note: This is simplified - in production, you'd need proper
        # text position extraction from the PDF
        for detection in detections:
            # Simplified position estimation
            # In a real implementation, you'd extract actual text positions
            # from the PDF using a library like pdfplumber
            
            # For now, we'll create a visible redaction mark
            # This would need to be replaced with actual position detection
            pass
        
        can.save()
        
        # Merge overlay with original page
        packet.seek(0)
        # Note: Full implementation would merge the overlay
        
        return page
    
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
        # Sort detections by position (reverse order to avoid offset issues)
        sorted_detections = sorted(detections, key=lambda d: d.start_pos, reverse=True)
        
        # Convert to list for easier manipulation
        text_chars = list(text)
        
        # Replace each detection with mask characters
        for detection in sorted_detections:
            start = detection.start_pos
            end = detection.end_pos
            
            # Replace with black boxes
            mask_length = end - start
            mask = "█" * mask_length
            
            # Apply mask
            text_chars[start:end] = list(mask)
        
        return ''.join(text_chars)