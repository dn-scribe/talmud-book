# Talmud Booklet Generator

Generate beautiful PDF booklets of Talmud text with commentaries (Rashi, Tosafot, etc.) using Playwright for high-quality Hebrew text rendering.

## Usage

### Basic Usage

Generate a single page:
```bash
python talmud_booklet.py Berakhot_2a
```

Generate a range of pages:
```bash
python talmud_booklet.py Berakhot_2a-Berakhot_5b
```

### With Commentaries

Add Rashi and Tosafot with custom colors:
```bash
python talmud_booklet.py Berakhot_2a \
  --commentaries Rashi_on_Berakhot:8:#0000FF Tosafot_on_Berakhot:8:#008000
```

Commentary format: `name[:font_size[:color]]`

Examples:
- `Rashi_on_Berakhot` - Default size (8pt) and black color
- `Rashi_on_Berakhot:10` - Font size 10, black color
- `Rashi_on_Berakhot:10:#0000FF` - Font size 10, blue color
- `Rashi_on_Berakhot::#FF0000` - Default size, red color

### Additional Options

```bash
python talmud_booklet.py Berakhot_2a \
  --font_size 12 \
  --page_format A5 \
  --cover \
  --output my_booklet.pdf \
  --font path/to/HebrewFont.ttf
```

**Options:**
- `--commentaries` - List of commentaries with optional size and color
- `--font_size` - Base font size for main text (default: 10pt)
- `--page_format` - Page format: A6, A5, A4, Letter (default: A6)
- `--cover` - Add a cover page
- `--output` - Output PDF filename (default: output.pdf)
- `--font` - Path to Hebrew TTF font file (default: NotoSansHebrew-Regular.ttf)

### Examples

Compact A6 booklet for printing:
```bash
python talmud_booklet.py Berakhot_2a-Berakhot_10b \
  --commentaries Rashi_on_Berakhot:7:#000080 Tosafot_on_Berakhot:7:#006400 \
  --font_size 9 \
  --cover
```

Larger A4 format with bigger text:
```bash
python talmud_booklet.py Berakhot_2a \
  --page_format A4 \
  --font_size 14 \
  --commentaries Rashi_on_Berakhot:12:#0000FF
```

## Installation

### 1. Install Python Dependencies

```bash
pip install playwright requests
```

### 2. Install Playwright Browsers

After installing the Playwright package, you need to install the browser binaries:

```bash
playwright install chromium
```

Or install all browsers:
```bash
playwright install
```

### 3. Install Hebrew Font

Download a Hebrew font file (TTF format) and place it in the project directory. Recommended fonts:

- **Noto Sans Hebrew**: Download from [Google Fonts](https://fonts.google.com/noto/specimen/Noto+Sans+Hebrew)
- **Frank Ruehl CLM**: Traditional Hebrew typeface
- **David CLM**: Classic Hebrew font

Save the font file as `NotoSansHebrew-Regular.ttf` in the project directory, or use `--font` to specify a different path.

### 4. Verify Installation

Test the setup:
```bash
python talmud_booklet.py Berakhot_2a
```

This should generate `output.pdf` with the first page of Tractate Berakhot.

## Technical Details

### Rendering Process

1. **Data Fetching**: Text is fetched from the Sefaria API (`https://www.sefaria.org/api/v3/texts/`)
   - Main Talmud text
   - Commentaries (Rashi, Tosafot, etc.)
   - Results are cached in the `data/` directory to avoid repeated API calls

2. **HTML Generation**: 
   - Creates an HTML document with embedded CSS
   - Uses `@font-face` to load the Hebrew TTF font
   - Applies RTL (right-to-left) text direction via CSS
   - Generates separate CSS classes for each commentary with custom styling
   - Each page is a `<div class="page">` with automatic page breaks

3. **PDF Rendering with Playwright**:
   - Writes HTML to temporary file (`temp_talmud.html`)
   - Launches headless Chromium browser
   - Loads the HTML file with proper font rendering
   - Generates PDF with specified page format and margins
   - Cleans up temporary HTML file

4. **Layout**:
   - **A6 format** (105mm × 148mm) - Compact booklet size
   - **5mm margins** - Tight spacing for more content
   - **8mm × 6mm padding** - Internal page padding
   - **RTL text flow** - Proper Hebrew text direction
   - **Automatic pagination** - Content flows naturally across pages

### Why Playwright?

Playwright provides superior Hebrew text rendering compared to ReportLab:

- **Native browser rendering**: Uses Chromium's advanced text layout engine
- **Proper RTL support**: CSS handles right-to-left text direction automatically
- **Better font rendering**: High-quality anti-aliasing and glyph positioning
- **Unicode support**: Full support for Hebrew vowels (nikkud) and cantillation marks
- **HTML/CSS flexibility**: Easy to customize layout and styling

### Caching

Text is automatically cached in the `data/` directory:
- Reduces API calls to Sefaria
- Speeds up regeneration of PDFs
- Files named by reference (e.g., `Berakhot_2a.json`)

To clear cache and fetch fresh data:
```bash
rm -rf data/
```

### Page Format Sizes

| Format | Dimensions (mm) | Use Case |
|--------|----------------|----------|
| A6 | 105 × 148 | Compact pocket booklet |
| A5 | 148 × 210 | Small book format |
| A4 | 210 × 297 | Standard document size |
| Letter | 215.9 × 279.4 | US letter size |

### Customization

Edit `talmud_booklet.py` to customize:
- `DEFAULT_FONT_SIZE` - Base font size (default: 10pt)
- `DEFAULT_PAGE_FORMAT` - Page format (default: A6)
- `DEFAULT_COMMENTARIES` - Default commentaries to include
- CSS in `generate_html()` - Styling, spacing, colors

### Troubleshooting

**Font not found**: Make sure the TTF font file exists in the specified path

**Playwright browser not installed**: Run `playwright install chromium`

**API errors**: Check internet connection; Sefaria API may be temporarily unavailable

**Empty pages**: Ensure you removed blank page logic; check that text data is being fetched correctly

**Rendering issues**: Try different font files; some fonts render Hebrew vowels better than others
