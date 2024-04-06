# -*- coding: utf-8 -*-
from __future__ import annotations

import dataclasses
import datetime
import decimal
import json
import pathlib
from collections import deque
from collections.abc import Sequence

from codecov import log


# The dataclasses in this module are accessible in the template, which is overridable by the user.
# As a coutesy, we should do our best to keep the existing fields for backward compatibility,
# and if we really can't and can't add properties, at least bump the major version.
@dataclasses.dataclass
class CoverageMetadata:
    version: str
    timestamp: datetime.datetime
    branch_coverage: bool
    show_contexts: bool


@dataclasses.dataclass
class CoverageInfo:  # pylint: disable=too-many-instance-attributes
    covered_lines: int
    num_statements: int
    percent_covered: decimal.Decimal
    percent_covered_display: str
    missing_lines: int
    excluded_lines: int
    num_branches: int | None
    num_partial_branches: int | None
    covered_branches: int | None
    missing_branches: int | None


@dataclasses.dataclass
class FileCoverage:
    path: pathlib.Path
    executed_lines: list[int]
    missing_lines: list[int]
    excluded_lines: list[int]
    info: CoverageInfo


@dataclasses.dataclass
class Coverage:
    meta: CoverageMetadata
    info: CoverageInfo
    files: dict[pathlib.Path, FileCoverage]


# The format for Diff Coverage objects may seem a little weird, because it
# was originally copied from diff-cover schema.


@dataclasses.dataclass
class FileDiffCoverage:
    path: pathlib.Path
    percent_covered: decimal.Decimal
    covered_statements: list[int]
    missing_statements: list[int]
    added_statements: list[int]
    # Added lines tracks all the lines that were added in the diff, not just
    # the statements (so it includes comments, blank lines, etc.)
    added_lines: list[int]

    # for backward compatibility
    @property
    def violation_lines(self) -> list[int]:
        return self.missing_statements


@dataclasses.dataclass
class DiffCoverage:
    total_num_lines: int
    total_num_violations: int
    total_percent_covered: decimal.Decimal
    num_changed_lines: int
    files: dict[pathlib.Path, FileDiffCoverage]


def compute_coverage(num_covered: int, num_total: int) -> decimal.Decimal:
    if num_total == 0:
        return decimal.Decimal('1')
    return decimal.Decimal(num_covered) / decimal.Decimal(num_total)


def get_coverage_info(coverage_path: pathlib.Path) -> tuple[dict, Coverage]:
    try:
        with coverage_path.open() as coverage_data:
            json_coverage = json.loads(coverage_data.read())
    except FileNotFoundError:
        log.error('Coverage report file not found: %s', coverage_path)
        raise
    except json.JSONDecodeError:
        log.error('Invalid JSON format in coverage report file: %s', coverage_path)
        raise

    return json_coverage, extract_info(data=json_coverage)


def extract_info(data: dict) -> Coverage:
    """
    {
        "meta": {
            "version": "5.5",
            "timestamp": "2021-12-26T22:27:40.683570",
            "branch_coverage": True,
            "show_contexts": False,
        },
        "files": {
            "codebase/code.py": {
                "executed_lines": [1, 2, 5, 6, 9],
                "summary": {
                    "covered_lines": 42,
                    "num_statements": 46,
                    "percent_covered": 88.23529411764706,
                    "percent_covered_display": "88",
                    "missing_lines": 4,
                    "excluded_lines": 0,
                    "num_branches": 22,
                    "num_partial_branches": 4,
                    "covered_branches": 18,
                    "missing_branches": 4
                },
                "missing_lines": [7],
                "excluded_lines": [],
            }
        },
        "totals": {
            "covered_lines": 5,
            "num_statements": 6,
            "percent_covered": 75.0,
            "percent_covered_display": "75",
            "missing_lines": 1,
            "excluded_lines": 0,
            "num_branches": 2,
            "num_partial_branches": 1,
            "covered_branches": 1,
            "missing_branches": 1,
        },
    }
    """
    return Coverage(
        meta=CoverageMetadata(
            version=data['meta']['version'],
            timestamp=datetime.datetime.fromisoformat(data['meta']['timestamp']),
            branch_coverage=data['meta']['branch_coverage'],
            show_contexts=data['meta']['show_contexts'],
        ),
        files={
            pathlib.Path(path): FileCoverage(
                path=pathlib.Path(path),
                excluded_lines=file_data['excluded_lines'],
                executed_lines=file_data['executed_lines'],
                missing_lines=file_data['missing_lines'],
                info=CoverageInfo(
                    covered_lines=file_data['summary']['covered_lines'],
                    num_statements=file_data['summary']['num_statements'],
                    percent_covered=file_data['summary']['percent_covered'],
                    percent_covered_display=file_data['summary']['percent_covered_display'],
                    missing_lines=file_data['summary']['missing_lines'],
                    excluded_lines=file_data['summary']['excluded_lines'],
                    num_branches=file_data['summary'].get('num_branches'),
                    num_partial_branches=file_data['summary'].get('num_partial_branches'),
                    covered_branches=file_data['summary'].get('covered_branches'),
                    missing_branches=file_data['summary'].get('missing_branches'),
                ),
            )
            for path, file_data in data['files'].items()
        },
        info=CoverageInfo(
            covered_lines=data['totals']['covered_lines'],
            num_statements=data['totals']['num_statements'],
            percent_covered=data['totals']['percent_covered'],
            percent_covered_display=data['totals']['percent_covered_display'],
            missing_lines=data['totals']['missing_lines'],
            excluded_lines=data['totals']['excluded_lines'],
            num_branches=data['totals'].get('num_branches'),
            num_partial_branches=data['totals'].get('num_partial_branches'),
            covered_branches=data['totals'].get('covered_branches'),
            missing_branches=data['totals'].get('missing_branches'),
        ),
    )


# pylint: disable=too-many-locals
def get_diff_coverage_info(added_lines: dict[pathlib.Path, list[int]], coverage: Coverage) -> DiffCoverage:
    files = {}
    total_num_lines = 0
    total_num_violations = 0
    num_changed_lines = 0

    for path, added_lines_for_file in added_lines.items():
        num_changed_lines += len(added_lines_for_file)

        try:
            file = coverage.files[path]
        except KeyError:
            continue

        executed = set(file.executed_lines) & set(added_lines_for_file)
        count_executed = len(executed)

        missing = set(file.missing_lines) & set(added_lines_for_file)
        count_missing = len(missing)

        added = executed | missing
        count_total = len(added)

        total_num_lines += count_total
        total_num_violations += count_missing

        percent_covered = compute_coverage(num_covered=count_executed, num_total=count_total)

        files[path] = FileDiffCoverage(
            path=path,
            percent_covered=percent_covered,
            covered_statements=sorted(executed),
            missing_statements=sorted(missing),
            added_statements=sorted(added),
            added_lines=added_lines_for_file,
        )
    final_percentage = compute_coverage(
        num_covered=total_num_lines - total_num_violations,
        num_total=total_num_lines,
    )

    return DiffCoverage(
        total_num_lines=total_num_lines,
        total_num_violations=total_num_violations,
        total_percent_covered=final_percentage,
        num_changed_lines=num_changed_lines,
        files=files,
    )


def parse_diff_output(diff: str, coverage: Coverage) -> dict[pathlib.Path, list[int]]:
    current_file: pathlib.Path | None = None
    added_filename_prefix = '+++ b/'
    result: dict[pathlib.Path, list[int]] = {}
    diff_lines: deque[str] = deque()
    diff_lines.extend(diff.splitlines())
    while diff_lines:
        line = diff_lines.popleft()
        if line.startswith(added_filename_prefix):
            current_file = pathlib.Path(line.removeprefix(added_filename_prefix))
            continue
        if line.startswith('@@'):

            def parse_line_number_diff_line(diff_line: str) -> Sequence[int]:
                """
                Parse the "added" part of the line number diff text:
                    @@ -60,0 +61 @@ def compute_files(  -> [64]
                    @@ -60,0 +61,9 @@ def compute_files(  -> [64, 65, 66]

                Github API returns default context lines 3 at start and end, we need to remove them.
                """
                start, length = (int(i) for i in (diff_line.split()[2][1:] + ',1').split(',')[:2])
                current_file_coverage = current_file and coverage.files.get(current_file)

                # TODO: sometimes the file might not be in the coverage report
                # Then we might as well just return the whole range since they are also not covered
                # But this will make the new statements in report in github comment inaccurate

                # Alternatively, we can get the number of statements in the file from github API
                # But it can be not good performance-wise since we need to make a request for each file
                if not (current_file_coverage and current_file_coverage.executed_lines):
                    return range(start if start == 1 else start + 3, start + length)

                current_file_num_statements = current_file_coverage.executed_lines[-1] + 1
                end = start + length

                # For the first 4 lines of the file, the start is always 1
                # So we need to check the next lines to get the context lines and remove them
                if start == 1:
                    while diff_lines:
                        next_line = diff_lines.popleft()
                        if next_line.startswith(' '):
                            start += 1
                            continue
                        diff_lines.appendleft(next_line)
                        break
                else:
                    start += 3

                # If the end is less then number of statements in the file
                # Then the last 3 lines could be context lines and we need to remove them
                if end < current_file_num_statements:
                    end -= 3
                else:
                    # If the end is same as the number of statements in the file
                    # Then the last 3 lines could be context lines and we need to remove them
                    last_3_lines: deque[str] = deque(maxlen=3)
                    while diff_lines:
                        next_line = diff_lines.popleft()
                        if next_line.startswith(' ') or next_line.startswith('+') or next_line.startswith('-'):
                            last_3_lines.append(next_line)
                            continue
                        diff_lines.appendleft(next_line)
                        break

                    while last_3_lines:
                        last_line = last_3_lines.pop()
                        if last_line.startswith(' '):
                            end -= 1
                        else:
                            break

                return range(start, end)

            lines = parse_line_number_diff_line(diff_line=line)
            if len(lines) > 0:
                if current_file is None:
                    raise ValueError(f'Unexpected diff output format: \n{diff}')
                result.setdefault(current_file, []).extend(lines)

    return result
