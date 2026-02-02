# Font Files for Auto-Fitting

This directory contains font files used by Pillow-based auto-fitting in the slide maker integration.

## Bundled Fonts

- **Calibri.ttf** (1.7 MB) - PowerPoint default font
- **Arial.ttf** (1.0 MB) - Common sans-serif font
- **Times.ttf** (1.2 MB) - Classic serif font
- **Courier.ttf** (810 KB) - Monospace font

## How It Works

The slide maker uses these font files to:
1. Load the actual font geometry with Pillow's `ImageFont.truetype()`
2. Measure exact text dimensions with `font.getbbox()`
3. Calculate optimal font size based on real pixel measurements
4. Achieve ~99% accuracy vs ~80% with heuristic approach

## Where to Get Fonts

- **Windows:** `C:\Windows\Fonts\`
- **macOS:** `/System/Library/Fonts/` or `/Library/Fonts/`
- **Linux:** Install `msttcorefonts` or use Liberation fonts

## Adding More Fonts

To add support for additional fonts:

1. Copy TTF file to this directory
2. Update the `font_files` mapping in `slide_maker.py` `get_font_path()` function:
   ```python
   font_files = {
       'calibri': 'Calibri.ttf',
       'arial': 'Arial.ttf',
       'your-font-name': 'YourFont.ttf',  # Add here
       ...
   }
   ```
3. Use in presentations by passing `font_face` parameter

## Licensing Notes

⚠️ **Important:** Font files may be subject to licensing restrictions:

- **Development/Testing:** Generally OK under OS license
- **Production Deployment:** Verify license compliance before deploying
- **Alternative:** Use Liberation fonts (open-source, metric-compatible with Microsoft fonts)

Liberation font alternatives:
- Liberation Sans → Arial replacement
- Liberation Serif → Times replacement
- Liberation Mono → Courier replacement

## Technical Details

- **DPI:** 72 DPI standard for screen/presentation rendering
- **Format:** TrueType Font (.ttf) files only
- **Size:** Total ~4.6 MB for all 4 bundled fonts
- **Lambda:** Well under AWS Lambda's 250 MB deployment limit
- **Cache:** Fonts loaded on-demand per request (Lambda stateless)

## Fallback Behavior

If a font file is not found:
- The system automatically falls back to the heuristic-based calculation
- No errors are raised
- Accuracy reverts to ~80% for that specific text box
- Other text boxes with available fonts still use Pillow measurement

## Troubleshooting

**Font not found error:**
- Check that the `.ttf` file exists in this directory
- Verify file name matches exactly (case-sensitive on Linux)
- Ensure font name mapping is correct in `get_font_path()`

**Inaccurate sizing:**
- Verify correct font file is being used
- Check if fallback to heuristic is occurring
- Ensure font has proper metrics (some decorative fonts may have issues)
