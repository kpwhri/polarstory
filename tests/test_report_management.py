"""Report management tests."""

import pytest

import polarstory as ps


def test_report_add_remove_and_move(df):
    profile = ps.profile(df, columns=['enctype', 'age'])
    report = ps.Report('Curated findings')
    first = report.add(profile.item('age', 'histogram'))
    second = report.add(profile.item('enctype', 'frequency'))
    third = report.add_text('Reviewed by analysts.', title='Comment')
    assert [i.id for i in report.items] == [first.id, second.id, third.id]
    report.move(third.id, before=first.id)
    assert [i.id for i in report.items] == [third.id, first.id, second.id]
    removed = report.remove(first.id)
    assert removed.id == first.id
    assert first.id not in [i.id for i in report.items]
    assert '<svg' not in report.to_html()
    assert '<script' not in report.to_html()
    with pytest.raises(KeyError):
        report.remove('does-not-exist')


def test_report_ids_and_cross_section_move(df):
    report = ps.Report('Test')
    first = report.add_text('one', id='note_one')
    with report.section('Next'):
        second = report.add_text('two')
    report.move(first.id, before=second.id)
    assert report.sections[1].items[0].id == first.id
    with pytest.raises(ValueError, match='Duplicate'):
        report.add_text('duplicate', id=first.id)
    with pytest.raises(ValueError, match='only letters'):
        report.add_text('invalid', id='not safe!')
