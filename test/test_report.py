"""
Tests for the polarstory.report.Report to ensure correct functionality.
"""
import pytest
import polars as pl
import matplotlib.pyplot as plt
import plotly.express as px
from datetime import datetime
from polarstory.report import Report


@pytest.fixture
def sample_df():
    return pl.DataFrame({
        'category': ['A', 'B', 'C', 'A', 'B'],
        'value': [1, 2, 3, 4, 5],
    })


@pytest.fixture
def report(tmp_path):
    return Report(
        title='Test Report',
        author='Test Author',
        out_dir=tmp_path
    )


def test_report_initialization(report):
    """Test basic report initialization and metadata"""
    assert report.title == 'Test Report'
    assert report.author == 'Test Author'
    assert isinstance(report.created, datetime)
    assert report._parts  # initial title and metadata
    assert len(report._parts) >= 2  # title + metadata line


def test_add_table(report, sample_df):
    """Test adding a Polars DataFrame as a table"""
    report.add_table('Sample Data', sample_df)

    md_path = report.save_markdown()
    content = md_path.read_text()

    assert '### Sample Data' in content
    assert '| category | value |' in content
    assert '| A | 1 |' in content


def test_add_summary_stats(report, sample_df):
    """Test adding summary statistics from a Polars DataFrame"""
    summary = sample_df.group_by('category').agg(
        pl.col('value').sum().alias('total'),
        pl.col('value').mean().alias('average')
    )

    report.add_table('Summary Statistics', summary)

    md_path = report.save_markdown()
    content = md_path.read_text()

    assert '### Summary Statistics' in content
    assert '| category | total | average |' in content


def test_add_matplotlib_plot(report, sample_df):
    """Test adding a Matplotlib plot"""
    fig, ax = plt.subplots()
    ax.scatter(sample_df['category'], sample_df['value'])
    ax.set_title('Sample Scatter Plot')

    report.add_plot(fig, caption='A scatter plot')

    # verify saved
    assert (report.assets_dir / 'figure-001.png').exists()

    md_path = report.save_markdown()
    content = md_path.read_text()
    assert '![Figure 1](assets/figure-001.png)' in content
    assert 'A scatter plot' in content


def test_add_plotly_plot(report, sample_df):
    """Test adding a Plotly plot"""
    fig = px.bar(sample_df, x='category', y='value')

    report.add_plot(fig, caption='A bar plot')

    # verify saved
    assert (report.assets_dir / 'figure-001.png').exists()

    md_path = report.save_markdown()
    content = md_path.read_text()
    assert '![Figure 1](assets/figure-001.png)' in content
    assert 'A bar plot' in content


def test_report_compilation(report, sample_df):
    """Test report compilation to different formats"""
    report.add_table('Data', sample_df)

    md_path = report.save_markdown()
    assert md_path.exists()

    try:  # test html (if pandoc is available)
        html_path = report.compile(to='html')
        assert html_path.exists()
        assert html_path.suffix == '.html'
    except RuntimeError:
        pytest.skip('Pandoc not available')


def test_report_with_multiple_components(report, sample_df):
    """Test a report with multiple components"""
    report.add_heading('Overview', level=2)
    report.add_paragraph('This is a test report with multiple components.')
    report.add_table('Raw Data', sample_df)

    summary = sample_df.group_by('category').agg(
        pl.col('value').sum().alias('total')
    )
    report.add_table('Summary', summary)

    fig, ax = plt.subplots()
    ax.bar(sample_df['category'], sample_df['value'])
    report.add_plot(fig, caption='Data visualization')

    md_path = report.save_markdown()
    content = md_path.read_text()

    assert '## Overview' in content
    assert 'This is a test report' in content
    assert '### Raw Data' in content
    assert '### Summary' in content
    assert '![Figure 1](assets/figure-001.png)' in content
    assert 'Data visualization' in content


def test_pdf_commandline(report, sample_df, capsys):
    """Test command line output for report in pdf pandoc generation."""
    report.compile(to='pdf', pdf_engine='weasyprint', print_command_only=True)
    today = datetime.today()
    cmd = capsys.readouterr().out.split('\n')[0].split(' ')  # first line of stdout
    assert ' '.join(cmd[0:4]) == 'pandoc -s --from gfm'
    assert cmd[4].endswith('report.md')
    assert cmd[5] == '-o'
    assert cmd[6].endswith('test-report.pdf')
    assert cmd[7] == '--resource-path'
    assert cmd[8].endswith('assets')
    assert ' '.join(cmd[9:12]) == '-M title=Test Report'
    assert ' '.join(cmd[12:15]) == '-M author=Test Author'
    assert ' '.join(cmd[15:17]) == f'-M date={today.year}-{today.month}-{today.day}'
    # cmd[17] is hour/minute which not be so stable
    assert ' '.join(cmd[18:20]) == '--pdf-engine weasyprint'


def test_pdf_commandline_wsl(report, sample_df, capsys):
    """Test command line output for report in pdf pandoc generation."""
    report.compile(to='pdf', pdf_engine='weasyprint', print_command_only=True, wsl_mount='mnt')
    today = datetime.today()
    cmd = capsys.readouterr().out.split('\n')[0].split(' ')  # first line of stdout
    assert ' '.join(cmd[0:4]) == 'pandoc -s --from gfm'
    assert cmd[4].startswith('/mnt/')
    assert cmd[4].endswith('report.md')
    assert cmd[5] == '-o'
    assert cmd[6].endswith('test-report.pdf')
    assert cmd[6].startswith('/mnt/')
    assert cmd[7] == '--resource-path'
    assert cmd[8].endswith('assets')
    assert cmd[8].startswith('/mnt/')
    assert ' '.join(cmd[9:12]) == '-M title=Test Report'
    assert ' '.join(cmd[12:15]) == '-M author=Test Author'
    assert ' '.join(cmd[15:17]) == f'-M date={today.year}-{today.month}-{today.day}'
    # cmd[17] is hour/minute which not be so stable
    assert ' '.join(cmd[18:20]) == '--pdf-engine weasyprint'
