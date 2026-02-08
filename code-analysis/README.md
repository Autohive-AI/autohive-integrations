# Code Analysis Integration

Python code execution integration for data analysis, file processing, and automation tasks within Autohive workflows.

## Features

- Execute arbitrary Python code in a sandboxed environment
- Process input files (CSV, Excel, JSON, images, PDFs, etc.)
- Automatically detect and return generated output files
- Access to popular data science and document processing libraries
- Base64-encoded file transfer for binary data

## Authentication

No authentication required. This integration runs Python code locally.

## Actions

### execute_python_code

Execute Python code with optional input files and automatic output file collection.

**Inputs:**

- `python_code` (string, required): The Python code to execute
- `files` (array, optional): Input files to make available to the script
  - `name` (string): Filename (e.g., "data.csv")
  - `content` (string): Base64-encoded file content
  - `contentType` (string, optional): MIME type

**Outputs:**

- `result` (string): Standard output from the executed code
- `error` (string, optional): Error message/traceback if execution failed
- `files` (array): Generated output files
  - `name` (string): Output filename
  - `content` (string): Base64-encoded file content
  - `contentType` (string): MIME type

## Available Libraries

The following third-party libraries are pre-installed:

- **numpy** - Numerical computing
- **Pillow** - Image processing
- **PyPDF2** - PDF manipulation
- **python-docx** - Word document creation/editing
- **reportlab** - PDF generation
- **openpyxl** - Excel file reading/writing
- **XlsxWriter** - Excel file creation
- **matplotlib** - Data visualization and plotting
- **python-pptx** - PowerPoint presentation creation

Plus the entire Python standard library.

## Usage Examples

### Basic Calculation

```python
# Input
python_code = """
result = sum([1, 2, 3, 4, 5])
print(f"Sum: {result}")
"""
```

### Process CSV Data

```python
# Input
python_code = """
import csv
import json

with open('data.csv', 'r') as f:
    reader = csv.DictReader(f)
    data = list(reader)

# Calculate totals
total = sum(float(row['amount']) for row in data)
print(json.dumps({'total': total, 'count': len(data)}))
"""

files = [
    {
        "name": "data.csv",
        "content": "<base64-encoded-csv>",
        "contentType": "text/csv"
    }
]
```

### Generate Excel Report

```python
# Input
python_code = """
import openpyxl
from openpyxl.styles import Font, Alignment

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Report"

# Add headers
ws['A1'] = 'Name'
ws['B1'] = 'Value'
ws['A1'].font = Font(bold=True)
ws['B1'].font = Font(bold=True)

# Add data
data = [('Item 1', 100), ('Item 2', 200), ('Item 3', 150)]
for i, (name, value) in enumerate(data, start=2):
    ws[f'A{i}'] = name
    ws[f'B{i}'] = value

wb.save('report.xlsx')
print("Report generated successfully")
"""
```

### Create Chart with Matplotlib

```python
# Input
python_code = """
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(10, 6))
plt.plot(x, y)
plt.title('Sine Wave')
plt.xlabel('X')
plt.ylabel('Y')
plt.grid(True)
plt.savefig('chart.png', dpi=150)
print("Chart saved")
"""
```

### Convert Image Format

```python
# Input
python_code = """
from PIL import Image

# Open input image
img = Image.open('input.png')

# Convert and save as JPEG
img = img.convert('RGB')
img.save('output.jpg', 'JPEG', quality=85)
print(f"Converted image: {img.size}")
"""

files = [
    {
        "name": "input.png",
        "content": "<base64-encoded-png>",
        "contentType": "image/png"
    }
]
```

## Best Practices

1. **Output results via print()** - Any non-file results should be printed to stdout
2. **Save files to current directory** - Output files are auto-detected from the working directory
3. **Use available libraries only** - Don't import packages not in the pre-installed list
4. **Handle errors gracefully** - Use try/except for robust scripts
5. **Close file handles** - Use context managers (`with` statements) for file operations

## Requirements

- `autohive-integrations-sdk~=1.0.2`
- `numpy`
- `Pillow`
- `PyPDF2`
- `python-docx`
- `reportlab`
- `openpyxl`
- `XlsxWriter`
- `matplotlib`
- `python-pptx`

## Testing

To run the tests:

1. Navigate to the integration directory: `cd code-analysis`
2. Install dependencies: `pip install -r requirements.txt -t dependencies`
3. Run the tests: `python tests/test_code_analysis.py`

## Version

1.0.0
