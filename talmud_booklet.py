import requests
from playwright.sync_api import sync_playwright
from pathlib import Path
import sys
import os
import json
import logging
import time

# --- CONFIGURABLE ---
DEFAULT_FONT = "NotoSansHebrew-Regular.ttf"  # You must have a Hebrew TTF font file in the same directory
DEFAULT_FONT_SIZE = 10  # Smaller for A6
DEFAULT_OUTPUT = "output.pdf"
DEFAULT_COMMENTARIES = ["Rashi_on_Berakhot:8:#0000FF", "Tosafot_on_Berakhot:8:#008000"]
CACHE_DIR = "data"
DEFAULT_PAGE_FORMAT = "A6"  # A6 is half the size of A5, which is half of A4
# ---------------------

def parse_commentary_spec(spec):
    """
    Parse commentary specification in format: name[:font_size[:color]]
    Examples:
        "Rashi_on_Berakhot" -> ("Rashi_on_Berakhot", None, None)
        "Rashi_on_Berakhot:10" -> ("Rashi_on_Berakhot", 10, None)
        "Rashi_on_Berakhot:10:#0000FF" -> ("Rashi_on_Berakhot", 10, "#0000FF")
        "Rashi_on_Berakhot::#FF0000" -> ("Rashi_on_Berakhot", None, "#FF0000")
    """
    parts = spec.split(':')
    name = parts[0]
    font_size = None
    color = None
    
    if len(parts) > 1 and parts[1]:
        try:
            font_size = int(parts[1])
        except ValueError:
            logging.warning(f"Invalid font size in '{spec}', using default")
    
    if len(parts) > 2 and parts[2]:
        color = parts[2]
        if not color.startswith('#'):
            color = '#' + color
    
    return name, font_size, color

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
    url = f"https://www.sefaria.org/api/v3/texts/{ref}?return_format=text_only"
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
    # No need for RTL processing with HTML/CSS - the browser handles it
    return text

def generate_html(pages, title, font_path, font_size, commentary_styles):
    """Generate HTML for the entire document."""
    font_path_resolved = Path(font_path).resolve()
    
    # Build CSS for commentary styles
    commentary_css = ""
    for name, style_info in commentary_styles.items():
        safe_name = name.replace("_", "-")
        commentary_css += f"""
  .commentary-{safe_name} {{
    font-size: {style_info['font_size']}pt;
    color: {style_info['color']};
    margin-right: 10px;
    margin-top: 2px;
    margin-bottom: 2px;
  }}
"""
    
    html = f"""
<!doctype html>
<meta charset="utf-8">
<style>
  @font-face {{
    font-family: 'HebrewFont';
    src: url('file://{font_path_resolved}');
  }}
  
  body {{
    font-family: 'HebrewFont', 'Noto Sans Hebrew', sans-serif;
    direction: rtl;
    unicode-bidi: plaintext;
    font-size: {font_size}pt;
    line-height: 1.4;
    margin: 0;
    padding: 0;
  }}
  
  .page {{
    page-break-after: always;
    padding: 8mm 6mm;
  }}
  
  .cover {{
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: {font_size + 4}pt;
    min-height: 100vh;
  }}
  
  .header {{
    direction: ltr;
    text-align: left;
    margin-bottom: 6px;
    font-size: {font_size - 1}pt;
    font-weight: bold;
  }}
  
  .segment {{
    margin-bottom: 4px;
    text-align: right;
  }}
  
  .commentary {{
    text-align: right;
  }}
  
{commentary_css}
</style>
"""
    
    for page in pages:
        if page['type'] == 'cover':
            html += f"""
<div class="page cover">
  <h1 dir="rtl">{page['title']}</h1>
</div>
"""
        elif page['type'] == 'content':
            html += '<div class="page">\n'
            html += f'  <div class="header">{page["header"]}</div>\n'
            for seg_data in page['segments']:
                html += f'  <div class="segment">{seg_data["text"]}</div>\n'
                for comm in seg_data['commentaries']:
                    safe_name = comm['name'].replace("_", "-")
                    html += f'  <div class="commentary commentary-{safe_name}">{comm["text"]}</div>\n'
            html += '</div>\n'
    
    html += "</body>\n</html>"
    return html

def add_cover_page(pages, title):
    pages.append({'type': 'cover', 'title': title})

def estimate_segment_height(segment, commentaries, font_size, chars_per_line=60, lines_per_page=40):
    # Rough estimate: 1 line per 60 chars, plus 1 line per commentary per 60 chars
    seg_lines = max(1, len(segment) // chars_per_line + 1)
    # commentaries is now a list of tuples (text, name)
    comm_lines = sum(max(1, len(comm[0] if isinstance(comm, tuple) else comm) // chars_per_line + 1) for comm in commentaries)
    return seg_lines + comm_lines

def add_talmud_page(pages, header, segments, commentaries, commentary_styles, font_size):
    """Add a talmud page with segments and commentaries."""
    segment_data = []
    for seg, comms in zip(segments, commentaries):
        comm_list = []
        for comm_text, comm_name in comms:
            comm_list.append({'text': comm_text, 'name': comm_name})
        segment_data.append({'text': seg, 'commentaries': comm_list})
    
    pages.append({
        'type': 'content',
        'header': header,
        'segments': segment_data
    })

def main(
    ref_range,
    commentary_specs=DEFAULT_COMMENTARIES,
    font_size=DEFAULT_FONT_SIZE,
    add_cover=False,
    output_format="pdf",
    output_file=DEFAULT_OUTPUT,
    font_path=DEFAULT_FONT,
    page_format=DEFAULT_PAGE_FORMAT
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
    
    pages = []

    # Parse commentary specifications
    commentary_styles = {}
    commentary_prefixes = []
    for spec in commentary_specs:
        name, comm_font_size, color = parse_commentary_spec(spec)
        commentary_prefixes.append(name)
        commentary_styles[name] = {
            'font_size': comm_font_size if comm_font_size else font_size - 2,
            'color': color if color else '#000000'
        }
    
    logger.info(f"Commentaries: {', '.join(commentary_prefixes)}")

    # Parse range
    start_ref, end_ref = parse_range(ref_range)
    # Generate all refs in range
    refs = generate_talmud_refs(start_ref, end_ref)
    logger.info(f"Processing {len(refs)} Talmud pages from {start_ref} to {end_ref}")

    if add_cover:
        add_cover_page(pages, f"מסכת {start_ref}")

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
                        # Store as tuples: (text, commentary_name)
                        for text in comm_texts:
                            comms.append((text, prefix))
                    elif comm_err:
                        logger.debug(f"Missing commentary {prefix} on {ref}.{i}: {comm_err}")
                        # Don't add placeholder - just skip missing commentaries
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
            add_talmud_page(pages, header, page_segments, page_commentaries, commentary_styles, font_size)

    # Generate HTML
    logger.info("Generating HTML")
    html_content = generate_html(pages, start_ref, font_path, font_size, commentary_styles)
    
    # Write HTML to temporary file
    html_file = Path("temp_talmud.html")
    html_file.write_text(html_content, encoding="utf-8")
    logger.info(f"HTML written to {html_file}")

    # Generate PDF using Playwright
    logger.info(f"Generating PDF with Playwright: {output_file}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_file.resolve().as_uri())
        page.pdf(
            path=output_file,
            format=page_format,
            print_background=True,
            margin={"top": "5mm", "bottom": "5mm", "left": "5mm", "right": "5mm"}
        )
        browser.close()
    
    # Clean up temporary HTML file
    html_file.unlink()
    
    logger.info(f"PDF generated successfully: {output_file}")
    elapsed_time = time.time() - start_time
    logger.info(f"Total execution time: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    # Example usage: 
    # python talmud_booklet.py Berakhot_3b --font_size 18 --cover
    # python talmud_booklet.py Berakhot_3a --commentaries Rashi_on_Berakhot:10:#0000FF Tosafot_on_Berakhot:12:#008000
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate Talmud booklet PDFs with optional commentaries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commentary Format:
  Commentaries can be specified with optional font size and color:
    name[:font_size[:color]]
  
  Examples:
    Rashi_on_Berakhot                    # Default size and black color
    Rashi_on_Berakhot:10                 # Font size 10, black color
    Rashi_on_Berakhot:10:#0000FF         # Font size 10, blue color
    Rashi_on_Berakhot::#FF0000           # Default size, red color
    
  Multiple commentaries:
    --commentaries Rashi_on_Berakhot:10:#0000FF Tosafot_on_Berakhot:12:#008000
        """
    )
    parser.add_argument("ref_range", help="Reference or range, e.g. Berakhot_3a-Berakhot_5b")
    parser.add_argument("--commentaries", nargs="+", default=DEFAULT_COMMENTARIES,
                        help="Commentary specifications (see format below)")
    parser.add_argument("--font_size", type=int, default=DEFAULT_FONT_SIZE,
                        help="Base font size for main text")
    parser.add_argument("--page_format", default=DEFAULT_PAGE_FORMAT, 
                        help="Page format (A4, A5, A6, Letter, etc.)")
    parser.add_argument("--cover", action="store_true", help="Add cover page")
    parser.add_argument("--format", default="pdf", help="Output format (pdf only)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output file path")
    parser.add_argument("--font", default=DEFAULT_FONT, help="Path to Hebrew TTF font file")
    args = parser.parse_args()
    main(
        args.ref_range,
        commentary_specs=args.commentaries,
        font_size=args.font_size,
        add_cover=args.cover,
        output_format=args.format,
        output_file=args.output,
        font_path=args.font,
        page_format=args.page_format
    )