"""Minimal dependency-free PDF writer (make_pdf). Standard library only."""
import textwrap


def make_pdf(title: str, sections: list[tuple[str, str]], metadata: dict = None) -> bytes:
    """Minimal multi-page PDF writer (no dependencies). sections = [(heading, body)]."""
    PAGE_TOP, PAGE_BOTTOM = 750, 60
    pages_lines: list[list[str]] = [[]]
    y = PAGE_TOP

    def _clean(t):
        return (t.replace("—", "--").replace("–", "-")
                 .replace("‘", "'").replace("’", "'")
                 .replace("“", '"').replace("”", '"')
                 .replace("…", "...").replace(" ", " "))

    def add_line(text, font_size=12, bold=False, indent=0):
        nonlocal y
        if y < PAGE_BOTTOM:            # start a new page
            pages_lines.append([])
            y = PAGE_TOP
        font = "/F2" if bold else "/F1"
        text = _clean(text)
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        pages_lines[-1].append(f"BT {font} {font_size} Tf {72 + indent} {y} Td ({escaped}) Tj ET")
        y -= font_size + 4

    add_line(title, font_size=16, bold=True)
    y -= 8
    if metadata:
        for k, v in metadata.items():
            add_line(f"{k}: {v}", font_size=9)
        y -= 4
    add_line("-" * 92, font_size=8)
    y -= 8

    for heading, body in sections:
        add_line(heading, font_size=13, bold=True)
        y -= 2
        for paragraph in body.split("\n"):
            wrapped = textwrap.wrap(paragraph, width=92)
            if not wrapped:
                y -= 10
                continue
            for line in wrapped:
                add_line(line, font_size=10, indent=8)
        y -= 8

    # Assemble PDF objects: catalog, pages, then per-page [page, content] + 2 fonts
    objects = []
    n_pages = len(pages_lines)
    # object numbering: 1 catalog, 2 pages, then pages 3..(3+n-1) are Page objects,
    # content streams follow, fonts last.
    page_obj_ids = [3 + i for i in range(n_pages)]
    content_obj_ids = [3 + n_pages + i for i in range(n_pages)]
    font_f1_id = 3 + 2 * n_pages
    font_f2_id = font_f1_id + 1

    objects.append((1, "<< /Type /Catalog /Pages 2 0 R >>"))
    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects.append((2, f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>"))

    for i in range(n_pages):
        objects.append((page_obj_ids[i],
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_obj_ids[i]} 0 R "
            f"/Resources << /Font << /F1 {font_f1_id} 0 R /F2 {font_f2_id} 0 R >> >> >>"))

    for i in range(n_pages):
        stream_content = "\n".join(pages_lines[i])
        stream_bytes = stream_content.encode("latin-1")
        objects.append((content_obj_ids[i],
            f"<< /Length {len(stream_bytes)} >>\nstream\n{stream_content}\nendstream"))

    objects.append((font_f1_id, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))
    objects.append((font_f2_id, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"))

    objects.sort(key=lambda o: o[0])
    pdf_parts = ["%PDF-1.4\n"]
    offsets = {}
    for obj_id, body in objects:
        offsets[obj_id] = len("".join(pdf_parts).encode("latin-1"))
        pdf_parts.append(f"{obj_id} 0 obj\n{body}\nendobj\n")

    xref_offset = len("".join(pdf_parts).encode("latin-1"))
    max_id = objects[-1][0]
    pdf_parts.append("xref\n")
    pdf_parts.append(f"0 {max_id + 1}\n")
    pdf_parts.append("0000000000 65535 f \n")
    for oid in range(1, max_id + 1):
        pdf_parts.append(f"{offsets.get(oid, 0):010d} 00000 n \n")
    pdf_parts.append("trailer\n")
    pdf_parts.append(f"<< /Size {max_id + 1} /Root 1 0 R >>\n")
    pdf_parts.append("startxref\n")
    pdf_parts.append(f"{xref_offset}\n%%EOF\n")
    return "".join(pdf_parts).encode("latin-1")
