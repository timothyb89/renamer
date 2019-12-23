#!/usr/bin/env python3
import json
import math
import re
import statistics
import subprocess
import sys

from argparse import ArgumentParser
from pathlib import Path

from typing import (
    Iterable, Dict, Any, Optional, Callable, TypeVar, Tuple, Union
)

import attr
import humanfriendly
import scipy.stats as stats


def ffprobe(path: Path) -> Dict[str, Any]:
    result = subprocess.check_output([
        'ffprobe',
        '-loglevel', 'quiet',
        '-print_format', 'json', '-show_format',
        str(path)
    ])

    return json.loads(result)


@attr.s()
class Entry(object):
    abs_path: Path = attr.ib()
    rel_path: Path = attr.ib()
    size: int = attr.ib()
    duration: float = attr.ib()

    @classmethod
    def new(cls, abs_path: Path) -> 'Entry':
        rel_path = abs_path.relative_to(abs_path.parent.parent)
        stat = abs_path.stat()
        print('checking: ', abs_path, file=sys.stderr)
        probe = ffprobe(abs_path)

        duration = float(probe['format']['duration'])

        return Entry(
            abs_path=abs_path,
            rel_path=rel_path,
            size=stat.st_size,
            duration=duration
        )


def scan(directory: Path) -> Iterable[Entry]:
    for entry in directory.iterdir():
        if not entry.is_file():
            continue

        yield Entry.new(entry)


T = TypeVar('T')


def confidence_interval(
    entries: Iterable[T],
    confidence: float,
    key: Optional[Callable[[T], float]]
) -> Tuple[float, float]:
    if key is None:
        key = float

    entries = [key(e) for e in entries]
    
    mean = statistics.mean(entries)
    stdev = statistics.stdev(entries, xbar=mean)

    # halve confidence to get 0-100% range (1-tailed interval rather than 2)
    confidence = 1 - ((1 - confidence) / 2)
    z = stats.norm.ppf(confidence)

    ci_size = z * (stdev / math.sqrt(len(entries)))
    print('n:', len(entries), 'mean:', mean / 60, 'stdev:', stdev / 60, 'ci_size:', ci_size / 60)

    lower = max(0, mean - ci_size)
    upper = min(max(entries), mean + ci_size)

    return lower, upper


def ranged_float(v_min: float, v_max: float) -> float:
    def ret(v: str):
        f = float(v)

        if f < v_min:
            raise ValueError(
                'value must be greater than {}: {}'.format(v_min, v)
            )

        if f > v_max:
            raise ValueError('value must be less than {}: {}'.format(v_max, v))

        return f
    
    return ret


def maybe_convert_int(s: str) -> Union[int, str]:
    try:
        # try to convert and see what happens
        conv = int(s)

        # make sure the human-readable value hasn't changed
        if str(conv) == s:
            return conv
        else:
            return  s
    except ValueError:
        return s


def main():
    parser = ArgumentParser()
    parser.add_argument('directories', nargs='+', type=Path)
    parser.add_argument(
        '--exclude-after',
        type=int,
        help='count of expected entries per directory, entries beyond it are '
             'skipped'
    )
    parser.add_argument(
        '--exclude',
        action='append',
        help='path to exclude'
    )
    parser.add_argument(
        '--offset',
        type=int,
        default=0,
        help='episode index offset from zero if some episodes should be '
             'skipped'
    )
    parser.add_argument(
        '--min-duration', '-m',
        help='sets the minimum clip duration, below which files are ignored; '
             'calculated automatically if unset'
    )
    parser.add_argument(
        '--confidence', '-z',
        default=0.5,
        type=ranged_float(0.0, 1),
        help='sets the confidence level for expected durations; 0<x<1'
    )
    parser.add_argument(
        '--input-regex',
        help='regex to apply to input filenames; captured groups are '
             'available to --output-format; non-matches are skipped'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='base output directory'
    )
    parser.add_argument(
        '--output-format',
        help='python format-style string to override output filename; '
             'includes any captured groups from --input-regex'
    )
    parser.add_argument(
        '--expect',
        type=int,
        help='expect some number of episodes; errors if final count does not '
             'match'
    )
    parser.add_argument(
        '--max',
        action='store_true',
        help='if set, also exclude excessively long episodes per the the '
             '--confidence setting'
    )

    args = parser.parse_args()

    files = []
    for d in args.directories:
        entries = sorted(sorted(scan(d), key=lambda e: str(e.rel_path)))
        if args.exclude_after:
            entries = entries[:args.exclude_after + 1]

        files.extend(entries)
    
    if args.exclude:
        for exclude in args.exclude:
            files = [
                e for e in files
                if not e.rel_path.match(exclude)
            ]

    duration_lower, duration_upper = confidence_interval(
        entries=files,
        confidence=args.confidence,
        key=lambda e: e.duration,
    )

    print('duration interval: {:.2f}min - {:.2f}min'.format(
        duration_lower / 60,
        duration_upper / 60
    ), file=sys.stderr)
    
    if args.min_duration:
        minimum_duration = humanfriendly.parse_timespan(args.min_duration)
        print(
            'user minimum size:',
            humanfriendly.format_timespan(minimum_duration),
            file=sys.stderr
        )
    else:
        minimum_duration = duration_lower
        print(
            'calculated minimum size:',
            humanfriendly.format_timespan(minimum_duration),
            file=sys.stderr
        )

    keep = [e for e in files if e.duration >= minimum_duration]

    if args.max:
        print(
            'excluding titles longer than',
            humanfriendly.format_timespan(duration_upper),
            file=sys.stderr
        )
        keep = [e for e in keep if e.duration <= duration_upper]

    for i, entry in enumerate(keep):
        print('{:3} {} {}'.format(
            i + 1,
            entry.rel_path,
            humanfriendly.format_timespan(entry.duration, max_units=2)
        ), file=sys.stderr)
    
    print('keep count:', len(keep), file=sys.stderr)

    if args.expect is not None and args.expect != len(keep):
        print('error: expected {} episodes but found {}'.format(
            args.expect, len(keep)
        ), file=sys.stderr)
        sys.exit(1)

    print('\n---\n', file=sys.stderr)

    if args.input_regex:
        input_regex = re.compile(args.input_regex)
    else:
        input_regex = None

    if args.output_format:
        output_format = args.output_format
    else:
        output_format = 'E{offset_index}{extension}'

    # (input abs path, output path)
    paths = []

    for i, entry in enumerate(keep):
        format_args = []
        format_kwargs = {}

        if input_regex:
            m = input_regex.match(str(entry.rel_path))
            if m:
                format_args = [
                    maybe_convert_int(g) for g in m.groups()
                ]
                format_kwargs = {
                    k: maybe_convert_int(v) for k, v in m.groupdict().items()
                }
            else:
                continue
        
        format_kwargs.update({
            'index': args.offset + i,
            'offset_index': args.offset + i + 1,
            'extension': ''.join(entry.rel_path.suffixes)
        })
        
        new_path = Path(output_format.format(*format_args, **format_kwargs))

        if args.output:
            new_path = args.output / new_path
        
        paths.append((entry.abs_path, new_path))
    
    # find all parent dirs
    dirs = set()
    for _, dest in paths:
        if not dest.parent.is_dir():
            dirs.add(str(dest.parent))
    
    for dir_name in dirs:
        print('mkdir -p \'{}\''.format(dir_name))
    
    for src, dest in paths:
        print('mv \'{}\' \'{}\''.format(
            str(src), str(dest)
        ))


if __name__ == '__main__':
    main()
