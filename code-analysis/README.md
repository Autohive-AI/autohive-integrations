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
- **pypdf** - PDF manipulation
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

files = [{"name": "data.csv", "content": "<base64-encoded-csv>", "contentType": "text/csv"}]
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

files = [{"name": "input.png", "content": "<base64-encoded-png>", "contentType": "image/png"}]
```

## Best Practices

1. **Output results via print()** - Any non-file results should be printed to stdout
2. **Save files to current directory** - Output files are auto-detected from the working directory
3. **Use available libraries only** - Don't import packages not in the pre-installed list
4. **Handle errors gracefully** - Use try/except for robust scripts
5. **Close file handles** - Use context managers (`with` statements) for file operations

## Requirements

Python 3.13+ is required by the SDK. Direct dependencies were checked against PyPI on 2026-10-28:

- `autohive-integrations-sdk~=2.0.1`
- `numpy==2.5.4`
- `Pillow==13.0.0`
- `pypdf==6.21.3`
- `python-docx==1.2.0`
- `reportlab==5.1.0`
- `openpyxl==3.1.5`
- `XlsxWriter==3.3.0`
- `matplotlib==3.11.2`
- `python-pptx==1.0.2`
- `python-dateutil==2.9.0.post0` - Latest compatible 2.x release; Lambda's bundled botocore requires `<3`.

The SDK follows the repository's compatible patch release convention; other direct dependencies are pinned to the reviewed releases. Transitive dependencies are resolved at install time, so repeat the vulnerability audit before deployment.

### Packaging for upload

The deployment target is AWS Lambda Python 3.13 on Amazon Linux 2023 (x86_64). NumPy 2.5.4 and Pillow 13.0.0 require newer Linux wheels than HiveUp's hardcoded `manylinux2014_x86_64` target permits. Stage dependencies inside `public.ecr.aws/lambda/python:3.13` and assemble the archive with HiveUp's `write_package_zip` packaging function. Keep the secure Pillow release: downgrading to the last `manylinux2014` wheel reintroduces known vulnerabilities.

Run dependency checks and the file-processing smoke tests against the staged bundle in that Lambda image before upload.

### Migrating to version 3

PyPDF2 has been replaced by its maintained successor, pypdf. PyPDF2's final release (3.0.1) has no fix for [CVE-2023-36464](https://github.com/py-pdf/pypdf/security/advisories/GHSA-4vvm-4w3v-6mr8), which allows a crafted PDF to cause an infinite loop during text extraction.

Update existing scripts to import from `pypdf`, for example `from pypdf import PdfReader, PdfWriter` instead of `from PyPDF2 import PdfReader, PdfWriter`. For merging, use `PdfWriter.append()`; the old `PdfMerger` API has been removed. Check the [pypdf migration guide](https://pypdf.readthedocs.io/en/stable/user/migration-1-to-2.html) for other legacy APIs used by your scripts.

## Testing

From the repository root, install dependencies and run the unit tests:

```bash
python -m pip install -r code-analysis/requirements.txt -r requirements-test.txt
python -m pytest code-analysis/
```

Audit the resolved dependencies, including transitive packages:

```bash
python -m pip install pip-audit
python -m pip_audit -r code-analysis/requirements.txt
```

## Version

3.0.0
