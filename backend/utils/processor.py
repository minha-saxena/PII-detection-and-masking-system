"""
PDF processing using Docling for text extraction and structure preservation
"""
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import json
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from core.logger import log


class PDFProcessor:
    """Handles PDF text extraction and structure preservation"""
    
    def __init__(self):
        """Initialize Docling converter"""
        # Configure pipeline options
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True  # Enable OCR for scanned PDFs
        pipeline_options.do_table_structure = True  # Preserve table structure
        
        # Initialize converter
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: pipeline_options,
            }
        )
        
        log.info("PDFProcessor initialized with Docling")
    
    def extract_text(self, pdf_path: str) -> Tuple[str, Dict]:
        """
        Extract text and metadata from PDF
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Tuple of (extracted_text, metadata)
        """
        try:
            log.info(f"Processing PDF: {pdf_path}")
            
            # Convert PDF
            result = self.converter.convert(pdf_path)
            
            # Get markdown representation (preserves structure)
            text = result.document.export_to_markdown()
            
            # Extract metadata
            metadata = {
                "num_pages": len(result.document.pages),
                "has_tables": any(page.tables for page in result.document.pages),
                "has_images": any(page.images for page in result.document.pages),
                "layout_preserved": True,
            }
            
            log.info(f"Extracted {len(text)} characters from {metadata['num_pages']} pages")
            
            return text, metadata
        
        except Exception as e:
            log.error(f"PDF extraction failed: {str(e)}")
            raise
    
    def extract_by_page(self, pdf_path: str) -> List[Dict]:
        """
        Extract text page by page
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            List of dictionaries with page text and metadata
        """
        try:
            log.info(f"Processing PDF page by page: {pdf_path}")
            
            result = self.converter.convert(pdf_path)
            pages_data = []
            
            for page_num, page in enumerate(result.document.pages, start=1):
                # Extract text from page
                page_text = page.export_to_markdown()
                
                page_info = {
                    "page_number": page_num,
                    "text": page_text,
                    "char_count": len(page_text),
                    "has_tables": bool(page.tables),
                    "has_images": bool(page.images),
                }
                
                pages_data.append(page_info)
            
            log.info(f"Processed {len(pages_data)} pages")
            return pages_data
        
        except Exception as e:
            log.error(f"Page-by-page extraction failed: {str(e)}")
            raise
    
    def get_document_structure(self, pdf_path: str) -> Dict:
        """
        Get document structure for reconstruction
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Document structure information
        """
        try:
            result = self.converter.convert(pdf_path)
            
            structure = {
                "num_pages": len(result.document.pages),
                "pages": [],
            }
            
            for page_num, page in enumerate(result.document.pages, start=1):
                page_structure = {
                    "page_number": page_num,
                    "width": getattr(page, 'width', None),
                    "height": getattr(page, 'height', None),
                    "num_tables": len(page.tables) if hasattr(page, 'tables') else 0,
                    "num_images": len(page.images) if hasattr(page, 'images') else 0,
                }
                structure["pages"].append(page_structure)
            
            return structure
        
        except Exception as e:
            log.error(f"Failed to get document structure: {str(e)}")
            raise
    
    def save_extracted_content(self, pdf_path: str, output_dir: str) -> str:
        """
        Save extracted content to file
        
        Args:
            pdf_path: Path to PDF file
            output_dir: Directory to save output
        
        Returns:
            Path to saved markdown file
        """
        try:
            text, metadata = self.extract_text(pdf_path)
            
            # Create output filename
            pdf_name = Path(pdf_path).stem
            output_path = Path(output_dir) / f"{pdf_name}_extracted.md"
            
            # Save markdown
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            # Save metadata
            metadata_path = Path(output_dir) / f"{pdf_name}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            log.info(f"Saved extracted content to {output_path}")
            
            return str(output_path)
        
        except Exception as e:
            log.error(f"Failed to save extracted content: {str(e)}")
            raise