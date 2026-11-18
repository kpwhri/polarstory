"""Regression tests for optional Altair and plotnine chart support."""

import pytest
from matplotlib.figure import Figure

from polarstory.report import Report


SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 40 20">'
    '<defs><clipPath id="shape"><rect width="40" height="20"/></clipPath></defs>'
    '<g clip-path="url(#shape)"><use xlink:href="#shape"/></g>'
    '</svg>'
)


def plotnine_stub(result):
    return type('Plot', (), {
        '__module__': 'plotnine.ggplot',
        'draw': lambda self: result,
    })()


def altair_stub(svg=SVG):
    def save(self, output, *, format):
        assert format == 'svg'
        output.write(svg)

    return type('Chart', (), {
        '__module__': 'altair.vegalite.v6.api',
        'save': save,
    })()


def test_matplotlib_chart_unchanged():
    figure = Figure()
    figure.subplots().plot([1, 2], [4, 5])
    report = Report('Charts')
    report.add_chart(figure, title='Matplotlib')
    assert '<svg' in report.to_html()
    assert '<svg' in report._to_notebook_html()


def test_plotnine_draws_once_and_stores_figure():
    figure = Figure()
    result = Report('Charts').add_chart(plotnine_stub(figure), title='plotnine')
    assert result.content is figure


def test_plotnine_requires_matplotlib_figure():
    with pytest.raises(TypeError, match='plotnine draw'):
        Report().add_chart(plotnine_stub('wrong'), title='Bad')


def test_altair_is_rendered_to_static_svg_for_both_outputs():
    report = Report('Charts')
    report.add_chart(altair_stub(), title='First')
    report.add_chart(altair_stub(), title='Second')
    html = report.to_html()
    notebook = report._to_notebook_html()
    for document in (html, notebook):
        assert document.count('<svg') == 2
        assert 'id="polarstory-0-shape"' in document
        assert 'id="polarstory-1-shape"' in document
        assert 'url(#polarstory-0-shape)' in document
        assert 'href="#polarstory-1-shape"' in document
        assert '<script' not in document


def test_altair_svg_xml_declaration_is_removed():
    svg = '<?xml version="1.0"?>\n' + SVG
    report = Report('Charts')
    report.add_chart(altair_stub(svg), title='Altair')
    assert '<?xml' not in report.to_html()


def test_altair_text_labels_can_contain_code_words():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><text>javascript: label</text></svg>'
    report = Report('Charts')
    report.add_chart(altair_stub(svg), title='Altair')
    assert 'javascript: label' in report.to_html()


def test_altair_converter_error_is_actionable():
    def missing_converter(self, output, *, format):
        raise ImportError('no vl_convert')

    chart = type('Chart', (), {
        '__module__': 'altair.vegalite.v6.api',
        'save': missing_converter,
    })()
    with pytest.raises(ImportError, match='pip install vl-convert-python'):
        Report().add_chart(chart, title='Altair')


@pytest.mark.parametrize('svg', [
    '<svg><script>alert(1)</script></svg>',
    '<svg><rect onload="alert(1)"/></svg>',
    '<svg><use href="https://example.com"/></svg>',
    '<svg><rect style="fill:url(https://example.com/a)"/></svg>',
    '<svg><foreignObject><p>text</p></foreignObject></svg>',
    '<svg><image href="https://example.com/a.png"/></svg>',
    '<svg><style>@import "https://example.com/s";</style></svg>',
    '<svg><rect fill="javascript:alert(1)"/></svg>',
    '<div>not svg</div>',
    '<svg><rect></svg>',
])
def test_altair_svg_must_be_static_and_self_contained(svg):
    with pytest.raises(ValueError):
        Report().add_chart(altair_stub(svg), title='Unsupported')


def test_reject_unsupported_objects():
    with pytest.raises(TypeError, match='Matplotlib Figure, plotnine plot, or Altair chart'):
        Report().add_chart(object(), title='Bad')


def test_actual_plotnine_when_installed():
    plotnine = pytest.importorskip('plotnine')
    pandas = pytest.importorskip('pandas')
    chart = (
        plotnine.ggplot(pandas.DataFrame({'age': [20, 30], 'score': [1, 2]}),
                        plotnine.aes('age', 'score'))
        + plotnine.geom_point()
    )
    report = Report('Example')
    report.add_chart(chart, title='Plotnine scatter')
    assert '<svg' in report.to_html()


def test_actual_altair_when_installed():
    altair = pytest.importorskip('altair')
    pytest.importorskip('vl_convert')
    chart = (altair.Chart(altair.Data(values=[
        {'age': 20, 'score': 1}, {'age': 30, 'score': 2},
    ])).mark_point().encode(x='age:Q', y='score:Q'))
    report = Report('Example')
    report.add_chart(chart, title='Altair scatter')
    assert '<svg' in report.to_html()


def test_polars_plot_via_altair_when_installed():
    altair = pytest.importorskip('altair')
    pytest.importorskip('vl_convert')
    polars = pytest.importorskip('polars')
    data = polars.DataFrame({'day': ['Mon', 'Tue'], 'value': [2, 4]})
    chart = data.plot.bar(x='day', y='value')
    report = Report('Example')
    report.add_chart(chart, title='Polars Altair plot')
    assert '<svg' in report.to_html()
