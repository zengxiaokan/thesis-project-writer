#!/usr/bin/env python3
"""Verify retained raw files and measure logged reads, not writing quality."""
import sys
sys.dont_write_bytecode = True
from collections import Counter
import hashlib
import json
from pathlib import Path


CASE = Path(__file__).resolve().parent / 'case/input'
PLAN = Path(__file__).resolve().parent / 'change-plan.json'


def material_versions():
    first = {p.relative_to(CASE).as_posix(): p.read_bytes() for p in CASE.rglob('*') if p.is_file()}
    second = dict(first)
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    for change in plan['modifications']:
        name = change['path']
        text = second[name].decode('utf-8').replace('\r\n', '\n')
        for replacement in change['replacements']:
            if text.count(replacement['before']) != 1:
                raise ValueError('Patch is not unique: ' + name)
            text = text.replace(replacement['before'], replacement['after'], 1)
        second[name] = text.encode('utf-8')
    for addition in plan['new_files']:
        if addition['path'] in second:
            raise ValueError('New source already exists')
        second[addition['path']] = addition['content'].encode('utf-8')
    return first, second


def fingerprint(data):
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def logged_reads(log, materials):
    counts = Counter()
    hashes = []
    for line in log.read_text(encoding='utf-8').splitlines():
        event = json.loads(line)
        if event['action'] == 'content_read':
            for item in event['files']:
                if item['path'] not in materials or item['sha256_text_lf'] != fingerprint(materials[item['path']]):
                    raise ValueError('Logged content baseline differs: ' + item['path'])
                counts[item['path']] += 1
        elif event['action'] == 'inventory':
            report = event['report']
            indexed = {item['path']: item for item in report['files']}
            if set(indexed) != set(materials):
                raise ValueError('Inventory paths do not match material scope')
            for name, item in indexed.items():
                if item['sha256'] != fingerprint(materials[name]):
                    raise ValueError('Inventory fingerprint differs: ' + name)
            hashes.append(report['coverage'])
        else:
            raise ValueError('Unknown read event')
    if not hashes:
        raise ValueError('No tool-generated inventory retained')
    return {
        'content_file_events': sum(counts.values()),
        'unique_content_paths': sorted(counts),
        'unique_content_files': len(counts),
        'repeated_content_events': sum(count - 1 for count in counts.values()),
        'inventory_scans': len(hashes),
        'hash_disk_reads': sum(item['content_hash_reads'] for item in hashes),
        'hash_disk_bytes': sum(item['content_hash_bytes'] for item in hashes),
    }


def summarize(result):
    result = Path(result)
    expected = json.loads((result / 'integrity.json').read_text(encoding='utf-8'))['sha256']
    actual = {p.relative_to(result).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for folder in ['raw', 'reviews'] for p in (result / folder).rglob('*') if p.is_file()}
    if actual != expected:
        raise ValueError('Retained output or review integrity mismatch')
    first, second = material_versions()
    changed = sorted(name for name in first.keys() | second.keys()
                     if name not in first or name not in second or fingerprint(first[name]) != fingerprint(second[name]))
    observed = {}
    for phase, materials in [('first', first), ('resume', second)]:
        observed[phase] = logged_reads(result / 'raw' / phase / 'read-log.jsonl', materials)
        unchanged = json.loads((result / 'raw' / phase / 'source-unchanged.json').read_text(encoding='utf-8'))
        if not all(unchanged[key] is True for key in ['same_paths', 'same_bytes', 'same_mtime']):
            raise ValueError('Runtime materials were modified by a writer')
        before = json.loads((result / 'raw' / phase / 'source-before.json').read_text(encoding='utf-8'))
        after = json.loads((result / 'raw' / phase / 'source-after.json').read_text(encoding='utf-8'))
        if before != after:
            raise ValueError('Runtime source snapshots differ')
    resumed_paths = set(observed['resume']['unique_content_paths'])
    observed['changed_source_paths'] = changed
    observed['resume']['changed_paths_read'] = sorted(resumed_paths & set(changed))
    observed['resume']['unchanged_paths_read'] = sorted(resumed_paths - set(changed))
    scope = json.loads((result / 'raw/resume/artifacts/read-scope.json').read_text(encoding='utf-8'))
    reported_current = {item['path'] for item in scope['wrapper_current_content_reads']}
    if reported_current != resumed_paths:
        raise ValueError('Supplemental scope disagrees with current-source log')
    cached = [item['path'] for item in scope['model_previous_source_cache_rereads']]
    for name in cached:
        if name not in first or name not in second or fingerprint(first[name]) != fingerprint(second[name]):
            raise ValueError('Cached source was not unchanged: ' + name)
    observed['resume']['cached_source_paths_self_reported'] = cached
    observed['resume']['current_and_cached_source_paths_union_self_reported'] = sorted(resumed_paths | set(cached))
    observed['resume']['previous_cache_packages_loaded_self_reported'] = scope['python_loaded_previous_cache_files']
    observed['resume']['previous_cache_package_bytes_self_reported'] = scope['python_loaded_previous_cache_json_bytes']
    observed['resume']['previous_artifact_read_events_measured'] = False
    observed['limits'] = [
        'Log records content returned by the instructed reader, not mental understanding or an OS-enforced audit.',
        'Hash scans read all selected file bytes; content-read counts do not measure total disk I/O or elapsed time.',
        'A fresh agent tests checkpoint handoff, not desktop restart, device migration, or broad quality gain.',
        'Semantic coverage and claim correctness require the separate reviews.',
        'Three current-source files are not total model source reading: old cached text was also displayed, with supplemental self-report rather than reader events.',
    ]
    return observed


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise ValueError('Usage: summarize.py <result-directory>')
        print(json.dumps(summarize(sys.argv[1]), ensure_ascii=True, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=True))
        raise SystemExit(1)
