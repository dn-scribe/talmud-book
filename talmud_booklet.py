import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Frame, SimpleDocTemplate, Spacer, PageBreak
from reportlab.lib.enums import TA_RIGHT
import sys
import os
import json
import logging
import time

# --- CONFIGURABLE ---
DEFAULT_FONT = "NotoSansHebrew-Regular.ttf"  # You must have a Hebrew TTF font file in the same directory
DEFAULT_FONT_SIZE = 16
DEFAULT_PAGE_SIZE = A4
DEFAULT_OUTPUT = "output.pdf"
DEFAULT_COMMENTARIES = ["Rashi_on_Berakhot"]
CACHE_DIR = "data"
# ---------------------

def fetch_sefaria_text(ref):
    # Create cache directory if it doesn't exist
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    # Create a safe filename from the ref (replace / and . with _)
    safe_filename = ref.replace("/", "_").replace(".", "_") + ".json"
    cache_path = os.path.join(CACHE_DIR, safe_filename)
    
    # Check if cached file exists
    if os.path.exists(cache_path):
        logging.info(f"Loading {ref} from cache")
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data, None
        except Exception as e:
            logging.warning(f"Error reading cache for {ref}: {e}, fetching from API")
    
    # Fetch from API
    url = f"https://www.sefaria.org/api/v3/texts/{ref}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"
    data = resp.json()
    if "error" in data:
        return None, data["error"]
    
    # Save to cache
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"Cached {ref} to {cache_path}")
    except Exception as e:
        logging.warning(f"Error caching {ref}: {e}")
    
    return data, None

def parse_range(ref_range):
    # e.g. Berakhot_3a-Berakhot_5b
    if "-" in ref_range:
        start, end = ref_range.split("-")
        return start, end
    return ref_range, ref_range

def parse_talmud_page(ref):
    # e.g. Berakhot_3a -> ("Berakhot", 3, "a")
    if "_" in ref:
        tractate, page_side = ref.split("_")
    else:
        tractate, page_side = ref.split(".")
    if page_side[-1] in ("a", "b"):
        page = int(page_side[:-1])
        side = page_side[-1]
    else:
        raise ValueError(f"Invalid Talmud page: {ref}")
    return tractate, page, side

def generate_talmud_refs(start_ref, end_ref):
    # Returns list of refs from start_ref to end_ref inclusive
    tractate1, page1, side1 = parse_talmud_page(start_ref)
    tractate2, page2, side2 = parse_talmud_page(end_ref)
    if tractate1 != tractate2:
        raise ValueError("Range must be within a single tractate")
    refs = []
    page = page1
    side = side1
    while True:
        refs.append(f"{tractate1}_{page}{side}")
        if page == page2 and side == side2:
            break
        if side == "a":
            side = "b"
        else:
            side = "a"
            page += 1
    return refs

def hebrew_rtl(text):
    # Improved RTL: try to use python-bidi if available, else fallback to reverse
    try:
        from bidi.algorithm import get_display
        return get_display(text)
    except ImportError:
        return text[::-1]

def register_hebrew_font(font_path):
    pdfmetrics.registerFont(TTFont("Hebrew", font_path))

def add_cover_page(story, title, font_size):
    style = ParagraphStyle(
        name='Cover',
        fontName='Hebrew',
        fontSize=font_size + 10,
        alignment=TA_RIGHT,
        rightIndent=0,
        leftIndent=0,
        spaceAfter=20,
    )
    story.append(Spacer(1, 100))
    story.append(Paragraph(hebrew_rtl(title), style))
    story.append(PageBreak())

def add_blank_page(story):
    story.append(PageBreak())

def estimate_segment_height(segment, commentaries, font_size, chars_per_line=60, lines_per_page=40):
    # Rough estimate: 1 line per 60 chars, plus 1 line per commentary per 60 chars
    seg_lines = max(1, len(segment) // chars_per_line + 1)
    comm_lines = sum(max(1, len(comm) // chars_per_line + 1) for comm in commentaries)
    return seg_lines + comm_lines

def add_talmud_page(story, header, segments, commentaries, font_size):
    # Header
    header_style = ParagraphStyle(
        name='Header',
        fontName='Hebrew',
        fontSize=font_size,
        alignment=TA_RIGHT,
        spaceAfter=10,
    )
    text_style = ParagraphStyle(
        name='Text',
        fontName='Hebrew',
        fontSize=font_size,
        alignment=TA_RIGHT,
        spaceAfter=6,
    )
    comm_style = ParagraphStyle(
        name='Commentary',
        fontName='Hebrew',
        fontSize=font_size - 2,
        alignment=TA_RIGHT,
        leftIndent=20,
        rightIndent=0,
        spaceAfter=4,
    )
    story.append(Paragraph(hebrew_rtl(header), header_style))
    for seg, comms in zip(segments, commentaries):
        story.append(Paragraph(hebrew_rtl(seg), text_style))
        for comm in comms:
            story.append(Paragraph(hebrew_rtl(comm), comm_style))
    story.append(PageBreak())

def main(
    ref_range,
    commentary_prefixes=DEFAULT_COMMENTARIES,
    font_size=DEFAULT_FONT_SIZE,
    page_size=DEFAULT_PAGE_SIZE,
    add_cover=False,
    output_format="pdf",
    output_file=DEFAULT_OUTPUT,
    font_path=DEFAULT_FONT
):
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger(__name__)
    
    start_time = time.time()
    logger.info("Starting Talmud booklet generation")
    
    register_hebrew_font(font_path)
    story = []

    # Parse range
    start_ref, end_ref = parse_range(ref_range)
    # Generate all refs in range
    refs = generate_talmud_refs(start_ref, end_ref)
    logger.info(f"Processing {len(refs)} Talmud pages from {start_ref} to {end_ref}")

    if add_cover:
        add_cover_page(story, f"מסכת {start_ref}", font_size)

    for ref in refs:
        logger.info(f"Fetching {ref}")
        data, err = fetch_sefaria_text(ref)
        if err:
            logger.warning(f"Error fetching {ref}: {err}")
            # Insert placeholder for missing page
            segments = [f"[Missing text for {ref}]"]
            all_commentaries = [[]]
        else:
            segments = data["versions"][0]["text"]
            if isinstance(segments, str):
                segments = [segments]
            # Fetch commentaries for each segment
            all_commentaries = []
            for i, seg in enumerate(segments, 1):
                comms = []
                for prefix in commentary_prefixes:
                    comm_ref = f"{prefix}.{ref.split('_')[1]}.{i}"
                    comm_data, comm_err = fetch_sefaria_text(comm_ref)
                    if comm_data and "versions" in comm_data:
                        comm_texts = comm_data["versions"][0]["text"]
                        if isinstance(comm_texts, str):
                            comm_texts = [comm_texts]
                        comms.extend(comm_texts)
                    elif comm_err:
                        logger.debug(f"Missing commentary {prefix} on {ref}.{i}: {comm_err}")
                        comms.append(f"[Missing commentary: {prefix} on {ref}.{i}]")
                all_commentaries.append(comms)
        # Pagination: group segments so all commentaries fit, or overflow to next page
        max_lines_per_page = 40  # rough estimate, can be parameterized
        idx = 0
        while idx < len(segments):
            page_segments = []
            page_commentaries = []
            used_lines = 3  # header
            start_idx = idx
            while idx < len(segments):
                seg = segments[idx]
                comms = all_commentaries[idx]
                seg_height = estimate_segment_height(seg, comms, font_size)
                if used_lines + seg_height > max_lines_per_page:
                    if not page_segments:
                        # Single segment too big, force it to overflow
                        page_segments.append(seg)
                        page_commentaries.append(comms)
                        idx += 1
                    break
                page_segments.append(seg)
                page_commentaries.append(comms)
                used_lines += seg_height
                idx += 1
            # Header: text name, page, segment range
            seg_range = f"{start_idx+1}-{start_idx+len(page_segments)}" if len(page_segments) > 1 else f"{start_idx+1}"
            header = f"{data['title']} {ref.split('_')[1]} (Segments {seg_range})"
            add_talmud_page(story, header, page_segments, page_commentaries, font_size)
            # Ensure new Talmud text starts on even page
            if idx < len(segments) and len(story) % 2 != 0:
                add_blank_page(story)

    # Ensure text starts on even page
    if len(story) % 2 != 0:
        add_blank_page(story)

    # Output
    logger.info(f"Writing output to {output_file}")
    if output_format == "pdf":
        doc = SimpleDocTemplate(output_file, pagesize=page_size, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        doc.build(story)
        logger.info(f"PDF generated successfully: {output_file}")
    else:
        logger.error("RTF output not implemented.")
    
    elapsed_time = time.time() - start_time
    logger.info(f"Total execution time: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    # Example usage: python talmud_booklet.py Berakhot_3b --font_size 18 --cover
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("ref_range", help="Reference or range, e.g. Berakhot_3a-Berakhot_5b")
    parser.add_argument("--commentaries", nargs="+", default=DEFAULT_COMMENTARIES)
    parser.add_argument("--font_size", type=int, default=DEFAULT_FONT_SIZE)
    parser.add_argument("--page_size", default="A4")
    parser.add_argument("--cover", action="store_true")
    parser.add_argument("--format", default="pdf")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--font", default=DEFAULT_FONT)
    args = parser.parse_args()
    main(
        args.ref_range,
        commentary_prefixes=args.commentaries,
        font_size=args.font_size,
        page_size=A4 if args.page_size == "A4" else args.page_size,
        add_cover=args.cover,
        output_format=args.format,
        output_file=args.output,
        font_path=args.font
    )