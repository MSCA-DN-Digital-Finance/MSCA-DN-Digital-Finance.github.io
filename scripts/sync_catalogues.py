#!/usr/bin/env python3
"""Cache profile references from the published catalogues or sibling local builds."""
import argparse
from pathlib import Path
import re
import json

from directory import ROOT, fetch_json, write_json

FEEDS = [('Data_inventory', 'inventory.json', ['sources', 'datasets']),
         ('Publications', 'research.json', ['publications', 'working_papers']),
         ('Open_Software', 'software.json', ['software'])]


def collect(local=False, root=None):
    root = root or ROOT
    result = {}
    for repo, filename, kinds in FEEDS:
        if local:
            payload = json.loads((root.parent / repo / '_site/data' / filename).read_text(encoding='utf-8'))
        else:
            payload = fetch_json(f'https://msca-dn-digital-finance.github.io/{repo}/data/{filename}')
        for kind in kinds:
            rows = payload.get(kind)
            if not isinstance(rows, list):
                raise ValueError(f'{repo}: invalid {kind} export')
            result[kind] = []
            ids = set()
            for row in rows:
                rid = row.get('id', '')
                title = row.get('title') or row.get('name') or row.get('dataset_name')
                if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', rid) or rid in ids or not isinstance(title, str) or not title:
                    raise ValueError(f'{repo}: invalid or duplicate catalogue record')
                ids.add(rid)
                numbers = row.get('irp_numbers') or row.get('IRP') or ''
                if numbers and not re.fullmatch(r'[1-9]\d*(?:;[1-9]\d*)*', numbers):
                    raise ValueError(f'{repo}: invalid IRP association')
                result[kind].append({'id': rid, 'title': title, 'irp_numbers': numbers, 'year': row.get('year', '')})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local', action='store_true')
    args = parser.parse_args()
    result = collect(args.local)
    changed = write_json(ROOT / 'data/catalogues.json', result)
    print(f'Indexed {sum(map(len, result.values()))} catalogue records; {"updated" if changed else "unchanged"}')
