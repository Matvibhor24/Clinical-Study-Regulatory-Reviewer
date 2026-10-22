"""Extract PDF table candidates and compare their cells with the original image.

Run: python extract_tables.py
Only dependency: pip install PyMuPDF==1.26.7
"""

import argparse
import csv
import json
from html import escape
from pathlib import Path
from time import perf_counter

import pymupdf


def write_report(output, tables, summary):
    """A local HTML file: original table crop on the left, parsed cells on the right."""
    parts = ["""<!doctype html><meta charset="utf-8"><title>PDF table parsing</title>
<style>
body{font:15px system-ui;margin:24px;color:#172536}summary{cursor:pointer;padding:12px}
.compare{display:grid;grid-template-columns:1fr 1fr;gap:20px} .pane{overflow:auto}
img{max-width:100%}table{border-collapse:collapse;font-size:12px}
td,th{border:1px solid #bbc6d1;padding:6px;white-space:pre-wrap;min-width:60px}
th{background:#edf2f7}details{border:1px solid #bbc6d1;margin:12px 0}
pre{white-space:pre-wrap}.missing{background:#fff0cb}
@media(max-width:800px){.compare{grid-template-columns:1fr}}
</style><h1>PDF table parsing</h1>
<p>Detected candidates, not verified complete tables. Page numbers are physical PDF pages.
Blank cells remain blank; yellow cells represent null (often merged cells).
Multi-page tables remain separate. Images show the detected region, which may omit captions or notes.</p>"""]
    parts.append(f"<pre>{escape(json.dumps(summary, indent=2))}</pre>")
    for t in tables:
        parts.append(f'<details><summary>{t["id"]} — physical page {t["physical_page"]} '
                     f'— {t["row_count"]} rows × {t["column_count"]} columns</summary>')
        parts.append(f'<p><a href="csv/{t["id"]}.csv">Download CSV</a></p>'
                     f'<div class="compare"><div class="pane"><h3>Original PDF region</h3>'
                     f'<img loading="lazy" src="images/{t["id"]}.png" alt="Original table"></div>'
                     '<div class="pane"><h3>Parsed rows and cells</h3><table>')
        parts.append('<tr><th>Row</th>' + ''.join(
            f'<th>Column {i + 1}</th>' for i in range(t['column_count'])) + '</tr>')
        for number, row in enumerate(t['rows'], 1):
            parts.append(f'<tr><th>{number}</th>' + ''.join(
                '<td class="missing">null</td>' if cell is None
                else f'<td>{escape(cell)}</td>' for cell in row) + '</tr>')
        parts.append('</table></div></div>')
        raw_json = json.dumps(t['rows'], indent=2, ensure_ascii=False)
        parts.append('<details><summary>Raw JSON from table.extract()</summary>'
                     f'<pre><code>{escape(raw_json)}</code></pre></details></details>')
    (output / 'report.html').write_text('\n'.join(parts), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', nargs='?', type=Path,
                        default=Path(__file__).parent / 'data/gsk-207749-clinical-study-report.pdf')
    parser.add_argument('--start-page', type=int, default=1)
    parser.add_argument('--end-page', type=int)
    parser.add_argument('--strategy', choices=['lines', 'lines_strict', 'text'], default='lines')
    parser.add_argument('--output', type=Path, default=Path('table_output'))
    args = parser.parse_args()
    started = perf_counter()
    tables, timings = [], []
    extraction_seconds = 0.0
    output = args.output
    with pymupdf.open(args.pdf) as document:
        end = args.end_page if args.end_page is not None else len(document)
        if not 1 <= args.start_page <= end <= len(document):
            parser.error(f'Page range must be within 1–{len(document)}.')
        for folder in ['csv', 'images']:
            (output / folder).mkdir(parents=True, exist_ok=True)
        for page_number in range(args.start_page, end + 1):
            tick = perf_counter()
            page = document[page_number - 1]
            # This is the actual parsing: find table regions, then read their cells.
            found = page.find_tables(strategy=args.strategy)
            page_tables = []
            for index, table in enumerate(found.tables, 1):
                page_tables.append({
                    'id': f'page_{page_number:04d}_table_{index:02d}',
                    'document': args.pdf.name,
                    'physical_page': page_number,
                    'bbox': list(table.bbox),
                    'row_count': table.row_count,
                    'column_count': table.col_count,
                    'header_names': list(table.header.names),
                    'header_external': table.header.external,
                    'rows': table.extract(),
                })
            elapsed = perf_counter() - tick
            extraction_seconds += elapsed
            timings.append({'physical_page': page_number, 'tables': len(page_tables),
                            'extraction_seconds': round(elapsed, 6)})
            # Exporting and rendering are deliberately outside the extraction timer.
            for table in page_tables:
                with (output / 'csv' / f'{table["id"]}.csv').open('w', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerows(table['rows'])
                page.get_pixmap(clip=pymupdf.Rect(table['bbox']), matrix=pymupdf.Matrix(1.5, 1.5)).save(
                    output / 'images' / f'{table["id"]}.png')
            tables.extend(page_tables)
            if page_number % 25 == 0 or page_number == end:
                print(f'Page {page_number}/{end}: {len(tables)} table candidates; '
                      f'{extraction_seconds:.2f}s extracting', flush=True)
        summary = {
            'document': args.pdf.name, 'pymupdf_version': pymupdf.__version__,
            'strategy': args.strategy, 'pdf_pages': len(document),
            'start_page': args.start_page, 'end_page': end,
            'pages_scanned': len(timings), 'table_candidates': len(tables),
            'pages_with_tables': sum(t['tables'] > 0 for t in timings),
            'extraction_seconds': round(extraction_seconds, 3),
        }
    (output / 'tables.json').write_text(json.dumps(tables, indent=2, ensure_ascii=False), encoding='utf-8')
    with (output / 'page_timings.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['physical_page', 'tables', 'extraction_seconds'])
        writer.writeheader()
        writer.writerows(timings)
    write_report(output, tables, summary)
    summary['total_seconds_including_exports'] = round(perf_counter() - started, 3)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    print(f'Open {output.resolve() / "report.html"}')


if __name__ == '__main__':
    main()
