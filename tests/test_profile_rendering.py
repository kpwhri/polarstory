"""Profile rendering tests."""

import re

import polarstory as ps


def test_date_chart_is_static(df):
    p = ps.profile(df, columns=['tx_ep_start'])
    v = p.variable('tx_ep_start')
    assert v.kind == 'temporal'
    assert v.chart is not None
    html = p.to_html()
    assert '<svg' in html
    assert '<script' not in html


def test_two_charts_have_separate_svg_identifiers(df):
    p = ps.profile(df, columns=['enctype', 'age'])
    html = p.to_html()
    svgs = re.findall(r'<svg\b.*?</svg>', html, flags=re.DOTALL)
    assert len(svgs) >= 2
    identifiers = re.findall(r'\bid="([^"]+)"', html)
    assert len(identifiers) == len(set(identifiers))
    for svg in svgs:
        local_ids = set(re.findall(r'\bid="([^"]+)"', svg))
        hrefs = re.findall(r'(?:xlink:)?href="#([^"]+)"', svg)
        urls = re.findall(r'url\(#([^\)]+)\)', svg)
        assert set(hrefs + urls) <= local_ids
    assert '@media print' in html
