import fitz


def extract_pdf_pages(pdf_path: str) -> list[dict]:

    document = fitz.open(pdf_path)

    pages = []

    try:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text")

            text = text.strip()

            if not text:
                continue

            pages.append({"page": page_number, "text": text})

    finally:
        document.close()

    return pages

    