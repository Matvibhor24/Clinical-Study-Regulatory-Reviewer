# Inspect the 207749 CSR tables

`extract_tables.py` is a standalone PyMuPDF experiment. No LLM or PageIndex calls
are needed. It defaults to `data/gsk-207749-clinical-study-report.pdf` and scans
every physical page, including embedded documents and appendices.

## Run

The local `.venv-tables` environment has PyMuPDF installed:

```bash
.venv-tables/bin/python extract_tables.py
```

For a fresh environment:

```bash
python -m venv .venv-tables
.venv-tables/bin/pip install PyMuPDF==1.26.7
.venv-tables/bin/python extract_tables.py
```

For a quick experiment on a page range:

```bash
.venv-tables/bin/python extract_tables.py --start-page 30 --end-page 50 --output table_output/sample
```

## View the results

Open `table_output/report.html` in a browser, then expand a table. The original
PDF crop is on the left and the parsed cells are on the right. This is the most
useful view for checking whether column boundaries and merged cells parsed well.

- `csv/`: one CSV per detected table, readable in Excel. CSV represents null and
  empty cells as blanks.
- `tables.json`: all tables as lists of rows, preserving nulls, empty strings,
  line breaks, inferred header names, document name, physical page and bounding box.
- `summary.json`: table counts, version, settings and measured elapsed seconds.
- `page_timings.csv`: extraction time and table count for every scanned page,
  including pages where no table was found.
- `images/`: source crops used in the report.

The essential parsing code is:

```python
with pymupdf.open(pdf_path) as document:
    for page in document:
        for table in page.find_tables().tables:
            rows = table.extract()  # [[cell, cell, ...], [cell, cell, ...]]
            print(page.number + 1, rows)
```

PDFs contain positioned text and drawing instructions. PyMuPDF detects table
boundaries and assigns text to cells; it does not understand the clinical meaning.
The default `lines` strategy uses drawn lines. For tables without borders, compare
the `text` strategy on a small range using a different output directory:

```bash
.venv-tables/bin/python extract_tables.py --start-page 30 --end-page 50 --strategy text --output table_output/text_sample
```

Text detection can also mistake ordinary paragraphs for tables. Neither strategy
guarantees all actual tables are found. Scanned images need a separate OCR workflow;
this script does not run OCR. Multi-page tables are kept as separate fragments.
No missing values, merged headers or captions are guessed or repaired. Header
inference can mistake the first data row for a header, so the report displays
neutral column numbers and retains every extracted row.

Extraction time includes page loading, detection and cell extraction, but excludes
PNG rendering and exports. Total time includes those exports and HTML generation,
up to writing the final summary. Timings vary by machine and strategy.
Use distinct output directories for comparisons; reruns replace current report and
JSON files but do not remove older CSV/image files from previous runs.

These outputs inspect PDF parsing only. They are not validated regulatory evidence;
the existing review pipeline still requires raw PageIndex page evidence.

API reference: https://pymupdf.readthedocs.io/en/latest/page.html#Page.find_tables

## Measured runs on this PDF

Both runs scanned all 1,075 pages with PyMuPDF 1.26.7 in this workspace.

| Strategy | Candidates | Extraction seconds | Total including exports |
| --- | ---: | ---: | ---: |
| lines | 193 | 139.818 | 143.958 |
| text | 1,053 | 334.254 | 373.757 |

Open `table_output/report.html` for lines and `table_output/text/report.html`
for text. These are candidate counts, not verified counts of real tables.
The runs overlapped for part of their execution; these are observed timings,
not controlled performance benchmarks.

Physical page 250 is a useful failure example: lines found nothing, while text
found a grid but split headings and included surrounding text. Its small standalone
report is `table_output/text_sample/report.html`. Physical page 91 in the lines
report illustrates multi-level headers with null cells. Do not assume all actual
tables or all columns have been recovered correctly by either strategy.

To repeat the full text run:

```bash
.venv-tables/bin/python extract_tables.py --strategy text --output table_output/text
```
