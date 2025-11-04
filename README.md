# Report Generator

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Polars](https://img.shields.io/badge/polars-latest-green.svg)](https://pola.rs/)

A flexible Python library for generating beautiful reports from polars dataframes with support for tables, plots, and multiple output formats.

## Features

- 📊 Native support for Polars DataFrames
- 📈 Seamless integration with Matplotlib and Plotly plots
- 📑 GitHub-flavored Markdown output
- 📄 Export to PDF, HTML, and DOCX (via Pandoc)
- 🎨 Customizable styling and layout
- 🔄 Fluent interface for method chaining

## Installation
```bash
pip install -r requirements.txt
```
### Dependencies

- `polars`: Fast DataFrame library
- `matplotlib`: Plotting library
- `plotly`: Interactive plotting library
  - `kaleido`: Required for static plotly exports
- `pandoc`: Required for PDF/DOCX/HTML export (system dependency)

## Quick Start
```python
import polars as pl
from polarstory.report import Report

# Create sample data
df = pl.DataFrame({
    'category': ['A', 'B', 'C'],
    'value': [10, 20, 30]
})

# Generate report
report = Report(title='Sales Report', author='John Doe')
report.add_heading('Monthly Sales Overview')
report.add_table('Sales by Category', df)

# Save as markdown
report.save_markdown()

# Or compile to PDF (requires pandoc)
report.compile(to='pdf')
```
## Advanced Usage

### Adding Plots

Add plots from matplotlib and plotly.

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.bar(df['category'], df['value'])
report.add_plot(fig, caption='Sales Distribution')
```
### Custom Formatting
```python
# Add custom markdown
report.add_markdown('**Bold text** and *italics*')

# Add images
report.add_image('path/to/image.png', width='80%')

# Control heading levels
report.add_heading('Important Section', level=2)
```
## Export Options

The report can be exported in various formats:
```python
# Save as Markdown
report.save_markdown()

# Export to PDF
report.compile(to='pdf')

# Export to HTML
report.compile(to='html')

# Export to DOCX
report.compile(to='docx')
```

## Development

### Running Tests
```bash
pytest tests/
```
### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## System Requirements

- Python 3.12+
- Pandoc (for PDF/DOCX/HTML export)
  - A PDF engines for PDF export:
    - wkhtmltopdf
    - weasyprint
    - xelatex/pdflatex

## License

This project is licensed under the MIT License: https://kpwhri.mit-license.org/.

## Acknowledgments

- Built with [Polars](https://pola.rs/)
- Export functionality powered by [Pandoc](https://pandoc.org/)
