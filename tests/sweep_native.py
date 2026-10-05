#!/usr/bin/env python3
"""Run every native suite, covering every case/group/size choice once.

Each ci_native_*.py suite is introspected (its argparse parser is captured
without running it), and its options with choices are expanded so that every
choice value runs in at least one job: the primary dimension (--case, --group,
--app) runs each value, other dimensions run each non-default value once.
Boolean flags that add coverage run once each; flags that only shrink a run
(--quick, --host-only, --recovery-only) are skipped.

A job passes only when the process exits 0 AND, if it wrote a report, the
report says "passed": true. Results go to <out>/summary.json, one log and one
report per job.

Usage:
  sweep_native.py --out DIR [--group cpu|vice|all] [--jobs N] [--only NAME...]
                  [--list] [--timeout SECONDS]
"""
import argparse
import concurrent.futures as futures
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT/'tests'
PYTHON = os.environ.get('KESTREL_TEST_PYTHON', sys.executable)  # the interpreter with py65 (tests/requirements.txt)

# Suites that start VICE. They need the localhost monitor socket, a display
# server and exclusive-ish CPU, so they run with low parallelism.
VICE = {
    'ci_native', 'ci_native_apps', 'ci_native_heap', 'ci_native_aes_vice', 'ci_native_boot_vice',
    'ci_native_banked_vice', 'ci_native_reu_vice', 'ci_native_gemdesk_vice', 'ci_native_gemdesk_prtscr_vice', 'ci_native_gemdesk_diskcopy_vice', 'ci_native_gemdesk_copy_vice', 'ci_native_gemdesk_print_vice', 'ci_native_gemdesk_acc_vice', 'ci_native_gemdesk_format_vice', 'ci_native_gemdesk_lock_vice',
    'ci_native_claude_iec', 'ci_native_desktop_iec', 'ci_native_editor_iec',
    'ci_native_editor_gui_iec', 'ci_native_files_copy_iec', 'ci_native_browser_iec',
    'ci_native_files_iec', 'ci_native_sheet_iec', 'ci_native_pointer_iec',
    'ci_native_suite_iec', 'ci_native_keyboard_iec', 'ci_native_editor_print_vice',
}

# VICE suites whose boolean flags select distinct scenarios. Each tuple is one
# job; the empty tuple is the default run.
VICE_MATRIX = {
    'ci_native_desktop_iec': [(), ('--desktop-boot', '--running-layout'), ('--desktop-boot', '--80col'),
                              ('--desktop-boot', '--missing-calc'), ('--desktop-boot', '--missing-desktop'),
                              ('--desktop-boot', '--hardware-sequence'), ('--desktop-boot', '--transport-sequence'),
                              ('--desktop-boot', '--nested-irq'), ('--desktop-boot', '--input-during-capture')],
    'ci_native_claude_iec': [(), ('--host-exit', '--80col')],
    'ci_native_editor_iec': [('--format', 'd64'), ('--format', 'd71'), ('--format', 'd81'),
                             ('--format', 'd81', '--search')],
    'ci_native_files_iec': [('--format', 'd64'), ('--format', 'd71'), ('--format', 'd81')],
    'ci_native_browser_iec': [('--format', 'd64'), ('--format', 'd71'), ('--format', 'd81')],
    # Prerequisites asserted by the suite: --controls-clock needs --controls-only;
    # --files-open-with needs --files-only; --files-find also --files-open-with;
    # --editor-selection/--editor-clipboard need --editor-only; --editor-history
    # also --editor-clipboard; --editor-large needs --editor-only --d81 and an
    # REU of 512 KiB or more (qualified 2026-09-14 with --80col --vdc64). The open-with
    # fixtures need 36 free blocks; the shipped D64 now has 16, so they run on the D81.
    'ci_native_pointer_iec': [(), ('--80col',), ('--calc-only',), ('--paint-only',), ('--controls-only',),
                              ('--controls-only', '--controls-clock'), ('--files-only',),
                              ('--files-only', '--files-open-with', '--d81'),
                              ('--files-only', '--files-open-with', '--files-find', '--d81'), ('--editor-only',),
                              ('--editor-only', '--editor-clipboard'),
                              ('--editor-only', '--editor-clipboard', '--editor-history'),
                              ('--editor-only', '--editor-selection'),
                              ('--editor-only', '--editor-selection', '--editor-large', '--80col', '--vdc64',
                               '--d81', '--reu-kib', '512'),
                              ('--claude-only',)],
    'ci_native_sheet_iec': [(), ('--80col',), ('--clipboard',), ('--reu-kib', '512')],
}

PRIMARY = ('case', 'group', 'app')
# Choice values that only exist together with another option's value. VDC
# address decoding can never exceed the chip's RAM (64 KiB addressing on a
# 16 KiB 8563 is not a real configuration and is not qualified anywhere).
PAIRED = {'addressing': lambda value: {'size': value}}
# Case preconditions the suites assert (configurations the project qualified).
REQUIRES = {
    ('ci_native_editor_history', 'case', 'large'): {'vdc_kib': '64', 'reu_kib': '512'},
    ('ci_native_editor_selection', 'case', 'display'): {'vdc_kib': '64'},
    ('ci_native_editor_selection', 'case', 'large'): {'vdc_kib': '64', 'reu_kib': '512'},
    ('ci_native_open_with', 'reu_kib', '512'): {'vdc_kib': '64'},
}
SHRINKING = {'quick', 'host_only', 'recovery_only', 'boot_frame_only', 'cpu_observation'}


class Captured(Exception):
    def __init__(self, parser):
        self.parser = parser


def capture(path):
    """Return the suite's argparse parser without running the suite."""
    if 'parse_args' not in path.read_text():
        return None                                     # no options: running it would run the suite
    original = argparse.ArgumentParser.parse_args

    def grab(self, *args, **kwargs):
        raise Captured(self)
    argparse.ArgumentParser.parse_args = grab
    old_argv, old_path = sys.argv, list(sys.path)
    sys.argv = [str(path)]
    # Suites reach repo-root helpers through an import side effect of
    # ci_native_heap, which runs only once per process; add both roots.
    sys.path[:0] = [str(path.parent), str(ROOT)]
    try:
        runpy.run_path(str(path), run_name='__main__')
    except Captured as caught:
        return caught.parser
    except SystemExit:
        return None
    except Exception as error:                              # import-time checks of the suite
        print(f'note: {path.stem} not introspected ({type(error).__name__}: {error}); '
              'running it with defaults', file=sys.stderr)
        return None
    finally:
        argparse.ArgumentParser.parse_args = original
        sys.argv, sys.path[:] = old_argv, old_path
    return None


def option(action):
    return max(action.option_strings, key=len)


def cpu_jobs(name, parser):
    """Expand one CPU suite into jobs that cover every choice value once."""
    dims, flags, report = [], [], None
    for action in parser._actions:
        if not action.option_strings or action.dest == 'help':
            continue
        if action.dest == 'report':
            report = option(action)
        elif action.choices is not None and action.nargs in (None, '?'):
            dims.append(action)
        elif isinstance(action, argparse._StoreTrueAction) and action.dest not in SHRINKING:
            flags.append(action)
    primary = next((d for d in dims if d.dest in PRIMARY), None)
    others = [d for d in dims if d is not primary]

    def base_value(action):
        """The value the suite runs with when the option is left out.

        None means the option is omitted, which for optional choice options
        without a default is itself a configuration (e.g. no REU, no VDC)."""
        choices = [str(c) for c in action.choices]
        if action.default is not None:
            return str(action.default)
        if action.required:
            return next((c for c in choices if c != 'all'), choices[0])
        return None

    def args_for(overrides):
        result = []
        for action in dims:
            value = overrides.get(action.dest)
            if value is None and action.required:
                value = base_value(action)
            if value is not None:
                result += [option(action), value]
        return result

    jobs = []
    if primary is not None:
        values = [str(c) for c in primary.choices]
        if 'all' in values and len(values) > 1:
            values = [v for v in values if v != 'all']          # split for parallelism
        for value in values:
            jobs.append(args_for({primary.dest: value, **REQUIRES.get((name, primary.dest, value), {})}))
    else:
        jobs.append(args_for({}))
    first = {primary.dest: jobs[0][jobs[0].index(option(primary))+1]} if primary else {}
    for action in others:
        base = base_value(action)
        for value in (str(c) for c in action.choices):
            if value != base and value != 'all':
                jobs.append(args_for({**first, action.dest: value, **PAIRED.get(action.dest, lambda v: {})(value),
                                      **REQUIRES.get((name, action.dest, value), {})}))
    for action in flags:
        jobs.append(args_for(first) + [option(action)])
    return [(name, job, report) for job in jobs]


def vice_jobs(name, parser):
    report = next((option(a) for a in parser._actions if a.dest == 'report'), None)
    return [(name, list(job), report) for job in VICE_MATRIX.get(name, [()])]


def label(name, args):
    tail = '_'.join(a.lstrip('-').replace('/', '_') for a in args)
    return name + ('__'+tail if tail else '')


def run(job, out, timeout, port):
    name, args, report_opt = job
    tag = label(name, args)
    report = out/f'{tag}.json'
    command = [PYTHON, '-B', str(TESTS/f'{name}.py'), *args]
    if report_opt:
        command += [report_opt, str(report)]
    started = time.time()
    with (out/f'{tag}.log').open('w') as log:
        try:
            env = dict(os.environ, KESTREL_VICE_PORT=str(port))     # distinct VICE monitor per job
            code = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                  timeout=timeout, env=env).returncode
        except subprocess.TimeoutExpired:
            code = 'timeout'
    seconds = round(time.time()-started, 1)
    reported = None
    if report.exists():
        try:
            reported = json.loads(report.read_text()).get('passed')
        except (ValueError, AttributeError):
            reported = 'unreadable'
    passed = code == 0 and reported in (None, True)
    return dict(job=tag, suite=name, args=args, exit=code, report_passed=reported,
                passed=passed, seconds=seconds)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--group', choices=('cpu', 'vice', 'all'), default='cpu')
    parser.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2)-1))
    parser.add_argument('--only', nargs='+', help='suite names (ci_native_x) to include')
    parser.add_argument('--list', action='store_true', help='print the job list and exit')
    parser.add_argument('--timeout', type=int, default=4*3600)
    parser.add_argument('--shard', default='0/1', help='I/N: run every Nth job starting at I (split across machines)')
    args = parser.parse_args()
    shard, shards = (int(part) for part in args.shard.split('/'))

    jobs = []
    for path in sorted(TESTS.glob('ci_native*.py')):
        name = path.stem
        if args.only and name not in args.only:
            continue
        is_vice = name in VICE
        if (args.group == 'cpu' and is_vice) or (args.group == 'vice' and not is_vice):
            continue
        suite_parser = capture(path)
        if suite_parser is None:
            jobs.append((name, [], None))
            continue
        jobs += vice_jobs(name, suite_parser) if is_vice else cpu_jobs(name, suite_parser)
    jobs = jobs[shard::shards]
    if args.list:
        for name, job_args, _ in jobs:
            print(label(name, job_args))
        print(f'{len(jobs)} jobs', file=sys.stderr)
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    summary_path = args.out/'summary.json'
    results = []
    print(f'{len(jobs)} jobs, {args.jobs} at a time -> {args.out}', flush=True)
    with futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        pending = {pool.submit(run, job, args.out, args.timeout, 62900+index): job
                   for index, job in enumerate(jobs)}
        for done in futures.as_completed(pending):
            result = done.result()
            results.append(result)
            mark = 'PASS' if result['passed'] else 'FAIL'
            print(f"{mark} {result['job']} exit={result['exit']} report={result['report_passed']} "
                  f"{result['seconds']}s [{len(results)}/{len(jobs)}]", flush=True)
            failed = sorted(r['job'] for r in results if not r['passed'])
            summary_path.write_text(json.dumps(dict(
                total=len(jobs), finished=len(results),
                passed=sum(r['passed'] for r in results), failed=failed,
                results=sorted(results, key=lambda r: r['job'])), indent=2)+'\n')
    failed = [r for r in results if not r['passed']]
    print(f'{len(results)-len(failed)}/{len(results)} passed', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
