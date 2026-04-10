"""
Google Fonts downloader for auto-fetching font files.
Kept separate from main slide_maker.py to avoid bloating the integration file.
"""

import os
import urllib.request
import re


def download_google_font(font_family, variant='regular'):
    """
    Download a font from Google Fonts and save to fonts directory.

    Args:
        font_family (str): Google Font family name (e.g., 'Poppins')
        variant (str): Font variant ('regular', 'bold', 'light', etc.)

    Returns:
        str: Path to downloaded font file, or None if download failed
    """
    try:
        # Construct Google Fonts CSS URL
        # Format: https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;700
        weight_map = {
            'thin': '100',
            'extralight': '200',
            'light': '300',
            'regular': '400',
            'medium': '500',
            'semibold': '600',
            'bold': '700',
            'extrabold': '800',
            'black': '900'
        }

        weight = weight_map.get(variant.lower(), '400')
        family_param = font_family.replace(' ', '+')
        api_url = f"https://fonts.googleapis.com/css2?family={family_param}:wght@{weight}"

        # Download CSS file to get TTF URL
        req = urllib.request.Request(
            api_url,
            headers={'User-Agent': 'Mozilla/5.0'}  # Required to get TTF URLs
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            css_content = response.read().decode('utf-8')

        # Extract TTF URL from CSS
        # Look for: src: url(https://fonts.gstatic.com/.../*.ttf) format('truetype')
        url_match = re.search(r'url\((https://[^)]+\.ttf)\)', css_content)

        if not url_match:
            # Try alternate pattern
            url_match = re.search(r'src:\s*url\(([^)]+\.ttf)\)', css_content)

        if not url_match:
            return None

        font_url = url_match.group(1)

        # Get fonts directory path
        fonts_dir = os.path.dirname(os.path.abspath(__file__))
        os.makedirs(fonts_dir, exist_ok=True)

        # Generate safe filename
        safe_name = font_family.replace(' ', '') + '-' + variant.capitalize() + '.ttf'
        font_path = os.path.join(fonts_dir, safe_name)

        # Download font file if not already cached
        if not os.path.exists(font_path):
            with urllib.request.urlopen(font_url, timeout=30) as response:
                font_data = response.read()

            with open(font_path, 'wb') as f:
                f.write(font_data)

        return font_path

    except Exception as e:
        # Download failed - return None to trigger fallback
        # Common failures: network error, font not found, API limit
        return None


def load_font_alternatives():
    """
    Load commercial font → Google Fonts mapping from JSON file.

    Returns:
        dict: Mapping of commercial fonts to Google Fonts alternatives
    """
    try:
        import json
        alternatives_path = os.path.join(
            os.path.dirname(__file__),
            'font_alternatives.json'
        )

        if os.path.exists(alternatives_path):
            with open(alternatives_path, 'r') as f:
                data = json.load(f)
                return data.get('mappings', {})

    except Exception as e:
        pass

    return {}
