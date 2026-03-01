"""
PDF processing using Docling for text extraction and structure preservation
"""
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import json
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from core.logger import log


class PDFProcessor:
    """Handles PDF text extraction and structure preservation"""

    def __init__(self):
        """Initialize Docling converter"""
        # Configure pipeline options (docling v2 API)
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True

        # Initialize converter with v2 PdfFormatOption wrapper
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options
                )
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

            # Extract metadata (docling v2: pages is a dict)
            pages = result.document.pages
            num_pages = len(pages)

            # Check for tables and images across all pages
            has_tables = False
            has_images = False
            for page in pages.values():
                if hasattr(page, 'tables') and page.tables:
                    has_tables = True
                if hasattr(page, 'images') and page.images:
                    has_images = True

            metadata = {
                "num_pages": num_pages,
                "has_tables": has_tables,
                "has_images": has_images,
                "layout_preserved": True,
            }

            log.info(f"Extracted {len(text)} characters from {num_pages} pages")

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

            # In docling v2, export full doc and split by page is more reliable
            # We use the full markdown and page count for metadata
            full_text = result.document.export_to_markdown()
            pages = result.document.pages

            # Split text roughly by number of pages as best effort
            # For true page-by-page, docling v2 requires iterating page chunks
            num_pages = len(pages)
            lines = full_text.split('\n')
            lines_per_page = max(1, len(lines) // num_pages) if num_pages else len(lines)

            for page_num, (page_key, page) in enumerate(pages.items(), start=1):
                start_line = (page_num - 1) * lines_per_page
                end_line = start_line + lines_per_page if page_num < num_pages else len(lines)
                page_text = '\n'.join(lines[start_line:end_line])

                page_info = {
                    "page_number": page_num,
                    "text": page_text,
                    "char_count": len(page_text),
                    "has_tables": bool(getattr(page, 'tables', None)),
                    "has_images": bool(getattr(page, 'images', None)),
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
            pages = result.document.pages

            structure = {
                "num_pages": len(pages),
                "pages": [],
            }

            for page_num, (page_key, page) in enumerate(pages.items(), start=1):
                page_structure = {
                    "page_number": page_num,
                    "width": getattr(page, 'width', None),
                    "height": getattr(page, 'height', None),
                    "num_tables": len(page.tables) if hasattr(page, 'tables') and page.tables else 0,
                    "num_images": len(page.images) if hasattr(page, 'images') and page.images else 0,
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

            pdf_name = Path(pdf_path).stem
            output_dir_path = Path(output_dir)
            output_dir_path.mkdir(parents=True, exist_ok=True)

            output_path = output_dir_path / f"{pdf_name}_extracted.md"

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)

            metadata_path = Path(output_dir) / f"{pdf_name}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            log.info(f"Saved extracted content to {output_path}")
            return str(output_path)

        except Exception as e:
            log.error(f"Failed to save extracted content: {str(e)}")
            raise