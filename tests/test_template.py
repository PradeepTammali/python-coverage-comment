# -*- coding: utf-8 -*-
import decimal
import hashlib
import pathlib

import pytest

from codecov import coverage, template


@pytest.mark.parametrize(
    'value, displayed_coverage',
    [
        (decimal.Decimal('0.83'), '83%'),
        (decimal.Decimal('0.99999'), '99.99%'),
        (decimal.Decimal('0.00001'), '0%'),
        (decimal.Decimal('0.0501'), '5.01%'),
        (decimal.Decimal('1'), '100%'),
        (decimal.Decimal('0.2'), '20%'),
        (decimal.Decimal('0.8392'), '83.92%'),
    ],
)
def test_pct(value, displayed_coverage):
    assert template.pct(value) == displayed_coverage


@pytest.mark.parametrize(
    'value, displayed_percentage',
    [
        (decimal.Decimal('0.83'), decimal.Decimal('83.00')),
        (decimal.Decimal('0.99'), decimal.Decimal('99.00')),
        (decimal.Decimal('0.00'), decimal.Decimal('0.00')),
        (decimal.Decimal('0.0501'), decimal.Decimal('5.01')),
        (decimal.Decimal('1'), decimal.Decimal('100.00')),
        (decimal.Decimal('0.2'), decimal.Decimal('20.00')),
        (decimal.Decimal('0.8392'), decimal.Decimal('83.92')),
    ],
)
def test_x100(value, displayed_percentage):
    assert template.x100(value) == displayed_percentage


@pytest.mark.parametrize(
    'number, singular, plural, expected',
    [
        (1, '', 's', ''),
        (2, '', 's', 's'),
        (0, '', 's', 's'),
        (1, 'y', 'ies', 'y'),
        (2, 'y', 'ies', 'ies'),
    ],
)
def test_pluralize(number, singular, plural, expected):
    assert template.pluralize(number=number, singular=singular, plural=plural) == expected


@pytest.mark.parametrize(
    'marker_id, result',
    [
        (None, '<!-- This comment was generated by CI codecov -->'),
        (
            'foo',
            '<!-- This comment was generated by CI codecov (id: foo) -->',
        ),
    ],
)
def test_get_marker(marker_id, result):
    assert template.get_marker(marker_id=marker_id) == result


def test_template_no_marker(coverage_obj, diff_coverage_obj):
    with pytest.raises(template.MissingMarker):
        marker = '<!-- foobar -->'
        template.get_comment_markdown(
            coverage=coverage_obj,
            diff_coverage=diff_coverage_obj,
            files=[],
            count_files=0,
            coverage_files=[],
            count_coverage_files=0,
            base_ref='main',
            max_files=25,
            minimum_green=decimal.Decimal('100'),
            minimum_orange=decimal.Decimal('70'),
            repo_name='org/repo',
            pr_number=1,
            base_template=template.read_template_file('comment.md.j2')[: -len(marker)],
            marker=marker,
        )


def test_template_error(coverage_obj, diff_coverage_obj):
    with pytest.raises(template.TemplateError):
        template.get_comment_markdown(
            coverage=coverage_obj,
            diff_coverage=diff_coverage_obj,
            files=[],
            count_files=0,
            coverage_files=[],
            count_coverage_files=0,
            base_ref='main',
            max_files=25,
            minimum_green=decimal.Decimal('100'),
            minimum_orange=decimal.Decimal('70'),
            repo_name='org/repo',
            pr_number=1,
            base_template='{% for i in range(5) %}{{ i }{% endfor %}',
            marker='<!-- foo -->',
        )


def test_get_comment_markdown(coverage_obj, diff_coverage_obj):
    chaned_files, total, files = template.select_changed_files(
        coverage=coverage_obj,
        diff_coverage=diff_coverage_obj,
        max_files=25,
    )
    result = (
        template.get_comment_markdown(
            coverage=coverage_obj,
            diff_coverage=diff_coverage_obj,
            coverage_files=chaned_files,
            count_coverage_files=total,
            files=files,
            count_files=total,
            max_files=25,
            minimum_green=decimal.Decimal('100'),
            minimum_orange=decimal.Decimal('70'),
            base_ref='main',
            marker='<!-- foo -->',
            repo_name='org/repo',
            pr_number=1,
            base_template="""
        {{ coverage.info.percent_covered | pct }}
        {{ diff_coverage.total_percent_covered | pct }}
        {% block foo %}foo{% endblock foo %}
        {{ marker }}
        """,
        )
        .strip()
        .split(maxsplit=3)
    )

    expected = ['60%', '50%', 'foo', '<!-- foo -->']

    assert result == expected


def test_comment_template(coverage_obj, diff_coverage_obj):
    chaned_files, total, files = template.select_changed_files(
        coverage=coverage_obj,
        diff_coverage=diff_coverage_obj,
        max_files=25,
    )
    result = template.get_comment_markdown(
        coverage=coverage_obj,
        diff_coverage=diff_coverage_obj,
        coverage_files=chaned_files,
        count_coverage_files=total,
        files=files,
        count_files=total,
        max_files=25,
        minimum_green=decimal.Decimal('100'),
        minimum_orange=decimal.Decimal('70'),
        base_ref='main',
        marker='<!-- foo -->',
        repo_name='org/repo',
        pr_number=1,
        base_template=template.read_template_file('comment.md.j2'),
    )
    assert result.startswith('## Coverage report')
    assert '<!-- foo -->' in result


def test_comment_template_branch_coverage(coverage_obj, diff_coverage_obj):
    chaned_files, total, files = template.select_changed_files(
        coverage=coverage_obj,
        diff_coverage=diff_coverage_obj,
        max_files=25,
    )
    result = template.get_comment_markdown(
        coverage=coverage_obj,
        diff_coverage=diff_coverage_obj,
        coverage_files=chaned_files,
        count_coverage_files=total,
        files=files,
        count_files=total,
        max_files=25,
        minimum_green=decimal.Decimal('100'),
        minimum_orange=decimal.Decimal('70'),
        base_ref='main',
        marker='<!-- foo -->',
        repo_name='org/repo',
        pr_number=1,
        base_template=template.read_template_file('comment.md.j2'),
        branch_coverage=True,
    )
    assert result.startswith('## Coverage report')
    assert '<!-- foo -->' in result
    assert '<th>Branches</th><th>Missing</th>' in result
    assert 'Branches missing' in result
    assert 'colspan="9"' in result


def test_template_no_files(coverage_obj):
    diff_coverage = coverage.DiffCoverage(
        total_num_lines=0,
        total_num_violations=0,
        total_percent_covered=decimal.Decimal('1'),
        num_changed_lines=0,
        files={},
    )
    result = template.get_comment_markdown(
        coverage=coverage_obj,
        diff_coverage=diff_coverage,
        files=[],
        count_files=0,
        coverage_files=[],
        count_coverage_files=0,
        minimum_green=decimal.Decimal('79'),
        minimum_orange=decimal.Decimal('40'),
        repo_name='org/repo',
        base_ref='main',
        pr_number=5,
        max_files=25,
        base_template=template.read_template_file('comment.md.j2'),
        marker='<!-- foo -->',
        subproject_id='foo',
    )
    assert '_This PR does not seem to contain any modification to coverable code.' in result
    assert 'code.py' not in result
    assert 'other.py' not in result


@pytest.mark.parametrize(
    'current_code_and_diff, max_files, expected_files, expected_total, expected_total_files',
    [
        pytest.param(
            """
            # file: a.py
            1 covered
            """,
            2,
            [],
            0,
            [],
            id='unmodified',
        ),
        pytest.param(
            """
            # file: a.py
            1
            2 covered
            """,
            2,
            [],
            0,
            [],
            id='info_did_not_change',
        ),
        pytest.param(
            """
            # file: a.py
            1 missing
            """,
            2,
            [],
            0,
            [],
            id='info_did_change',
        ),
        pytest.param(
            """
            # file: a.py
            + 1 covered
            """,
            2,
            ['a.py'],
            1,
            ['a.py'],
            id='with_diff',
        ),
        pytest.param(
            """
            # file: b.py
            + 1 covered
            # file: a.py
            + 1 covered
            """,
            2,
            ['a.py', 'b.py'],
            2,
            ['a.py', 'b.py'],
            id='ordered',
        ),
        pytest.param(
            """
            # file: a.py
            + 1 covered
            + 2 covered
            # file: b.py
            + 1 missing
            """,
            1,
            ['b.py'],
            2,
            ['a.py', 'b.py'],
            id='info_did_change',
        ),
        pytest.param(
            """
            # file: a.py
            + 1 covered
            # file: c.py
            + 1 missing
            # file: b.py
            + 1 missing
            """,
            2,
            ['b.py', 'c.py'],
            3,
            ['a.py', 'b.py', 'c.py'],
            id='truncated_and_ordered',
        ),
        pytest.param(
            """
            # file: a.py
            1
            2 covered
            # file: c.py
            + 1 covered
            # file: b.py
            + 1 covered
            + 1 covered
            """,
            2,
            ['b.py', 'c.py'],
            2,
            ['b.py', 'c.py'],
            id='truncated_and_ordered_sort_order_advanced',
        ),
        pytest.param(
            """
            # file: a.py
            + 1 covered
            + 2 covered
            # file: b.py
            + 1 missing
            """,
            None,
            ['a.py', 'b.py'],
            2,
            ['a.py', 'b.py'],
            id='max_none',
        ),
    ],
)
def test_select_changed_files(
    make_coverage_and_diff,
    current_code_and_diff,
    max_files,
    expected_files,
    expected_total,
    expected_total_files,
):
    cov, diff_cov = make_coverage_and_diff(current_code_and_diff)
    files, total, total_files = template.select_changed_files(
        coverage=cov,
        diff_coverage=diff_cov,
        max_files=max_files,
    )
    assert [str(e.path) for e in files] == expected_files
    assert total == expected_total
    assert all(str(e.path) in expected_total_files for e in total_files)


@pytest.mark.parametrize(
    'current_code_and_diff, max_files, expected_files, expected_total',
    [
        pytest.param(
            """
            # file: a.py
            1 covered
            """,
            2,
            ['a.py'],
            1,
            id='unmodified',
        ),
        pytest.param(
            """
            # file: a.py
            1
            2 covered
            """,
            2,
            ['a.py'],
            1,
            id='info_did_not_change',
        ),
        pytest.param(
            """
            # file: a.py
            1 missing
            """,
            2,
            ['a.py'],
            1,
            id='info_did_change',
        ),
        pytest.param(
            """
            # file: a.py
            + 1 covered
            """,
            2,
            [],
            0,
            id='with_diff',
        ),
        pytest.param(
            """
            # file: b.py
            + 1 covered
            # file: a.py
            + 1 covered
            """,
            2,
            [],
            0,
            id='ordered',
        ),
        pytest.param(
            """
            # file: a.py
            + 1 covered
            # file: c.py
            1 missing
            # file: b.py
            1 missing
            """,
            2,
            ['b.py', 'c.py'],
            2,
            id='truncated_and_ordered',
        ),
        pytest.param(
            """
            # file: a.py
            1
            2 covered
            # file: c.py
            + 1 covered
            # file: b.py
            1 covered
            1 covered
            """,
            2,
            ['a.py', 'b.py'],
            2,
            id='truncated_and_ordered_sort_order_advanced',
        ),
        pytest.param(
            """
            # file: a.py
            1 covered
            2 covered
            # file: b.py
            1 missing
            """,
            None,
            ['a.py', 'b.py'],
            2,
            id='max_none',
        ),
    ],
)
def test_select_files(
    make_coverage_and_diff,
    current_code_and_diff,
    max_files,
    expected_files,
    expected_total,
):
    cov, diff_cov = make_coverage_and_diff(current_code_and_diff)
    _, _, changed_files_info = template.select_changed_files(coverage=cov, diff_coverage=diff_cov, max_files=max_files)
    files, total = template.select_files(
        coverage=cov,
        changed_files_info=changed_files_info,
        max_files=max_files,
    )
    assert [str(e.path) for e in files] == expected_files
    assert total == expected_total


def test_select_files_no_statements(make_coverage_and_diff):
    code = """
        # file: a.py
        1 covered
        """
    cov, diff_cov = make_coverage_and_diff(code)
    _, _, changed_files_info = template.select_changed_files(coverage=cov, diff_coverage=diff_cov, max_files=2)
    cov.files[pathlib.Path('a.py')].info.num_statements = 0
    files, total = template.select_files(
        coverage=cov,
        changed_files_info=changed_files_info,
        max_files=2,
    )
    assert [str(e.path) for e in files] == []
    assert total == 0


@pytest.mark.parametrize(
    'current_code_and_diff, expected_new_missing, expected_added, expected_new_covered',
    [
        pytest.param(
            """
            # file: a.py
            + 1
            2 covered
            + 3 missing
            + 4 missing
            + 5 covered
            """,
            2,
            3,
            2,
            id='added_code',
        ),
        pytest.param(
            """
            # file: a.py
            + 1 missing
            """,
            1,
            1,
            0,
            id='removed_code',
        ),
    ],
)
def test_sort_order(
    make_coverage_and_diff,
    current_code_and_diff,
    expected_new_missing,
    expected_added,
    expected_new_covered,
):
    cov, diff_cov = make_coverage_and_diff(current_code_and_diff)
    path = pathlib.Path('a.py')
    file_info = template.FileInfo(
        path=path,
        coverage=cov.files[path],
        diff=diff_cov.files[path],
    )
    new_missing, added, new_covered = template.sort_order(file_info=file_info)
    assert new_missing == expected_new_missing
    assert added == expected_added
    assert new_covered == expected_new_covered


def test_sort_order_none(make_coverage):
    cov = make_coverage(
        """
        # file: a.py
        1 covered
        """
    )
    file_info = template.FileInfo(
        path=pathlib.Path('a.py'),
        coverage=cov.files[pathlib.Path('a.py')],
        diff=None,
    )
    new_missing, added, new_covered = template.sort_order(file_info=file_info)
    assert new_missing == 0
    assert added == 0
    assert new_covered == 1


def test_read_template_file():
    result = template.read_template_file('comment.md.j2')
    assert result.startswith('{%- block title -%}## Coverage report')


def test_get_file_url_base():
    filename = pathlib.Path('test_file.py')
    lines = (1, 10)
    repo_name = 'my_repo'
    pr_number = 123
    base_ref = 'main'

    expected_url = f'https://github.com/{repo_name}/blob/{base_ref}/{str(filename)}#L1-L10'
    assert (
        template.get_file_url(filename, lines, base=True, repo_name=repo_name, pr_number=pr_number, base_ref=base_ref)
        == expected_url
    )


def test_get_file_url_pr_base():
    filename = pathlib.Path('test_file.py')
    lines = (1, 10)
    repo_name = 'my_repo'
    pr_number = 123
    base_ref = 'main'

    expected_url = f'https://github.com/{repo_name}/blob/{base_ref}/{str(filename)}#L1-L10'
    assert (
        template.get_file_url(filename, lines, True, repo_name=repo_name, pr_number=pr_number, base_ref=base_ref)
        == expected_url
    )


def test_get_file_url_pr_base_no_lines():
    filename = pathlib.Path('test_file.py')
    lines = None
    repo_name = 'my_repo'
    pr_number = 123
    base_ref = 'main'

    expected_url = f'https://github.com/{repo_name}/blob/{base_ref}/{str(filename)}'
    assert (
        template.get_file_url(filename, lines, True, repo_name=repo_name, pr_number=pr_number, base_ref=base_ref)
        == expected_url
    )


def test_get_file_url_pr():
    filename = pathlib.Path('test_file.py')
    lines = (1, 10)
    repo_name = 'my_repo'
    pr_number = 123
    base_ref = 'main'

    expected_hash = hashlib.sha256(str(filename).encode('utf-8')).hexdigest()
    expected_url = f'https://github.com/{repo_name}/pull/{pr_number}/files#diff-{expected_hash}R1-R10'
    assert (
        template.get_file_url(filename, lines, repo_name=repo_name, pr_number=pr_number, base_ref=base_ref)
        == expected_url
    )


def test_get_file_url_no_lines():
    filename = pathlib.Path('test_file.py')
    lines = None
    repo_name = 'my_repo'
    pr_number = 123
    base_ref = 'main'

    expected_url = f"https://github.com/{repo_name}/pull/{pr_number}/files#diff-{hashlib.sha256(str(filename).encode('utf-8')).hexdigest()}"
    assert (
        template.get_file_url(filename, lines, repo_name=repo_name, pr_number=pr_number, base_ref=base_ref)
        == expected_url
    )
