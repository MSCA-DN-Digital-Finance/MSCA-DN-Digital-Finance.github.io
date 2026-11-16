#!/usr/bin/env python3
"""Import public candidate identities and IRP titles; preserve editable summaries."""
import argparse
import copy
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import time
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from directory import ROOT, fetch_json, load, match_creators, orcid_id, public_url, validate, write_json

BASE = 'https://beta.digital-finance-msca.com'


class Node:
    def __init__(self, tag='', attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or []), []

    def find(self, tag=None, cls=None):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (cls is None or cls in child.attrs.get('class', '').split()):
                    result.append(child)
                result += child.find(tag, cls)
        return result

    def text(self):
        return ' '.join(' '.join(c.text() if isinstance(c, Node) else c for c in self.children).split())

    def first(self, tag=None, cls=None):
        nodes = self.find(tag, cls)
        if not nodes:
            raise ValueError(f'Source markup changed: missing {tag or "element"}/{cls or ""}')
        return nodes[0]


class Tree(HTMLParser):
    def __init__(self, content):
        super().__init__(); self.root = Node(); self.stack = [self.root]; self.feed(content)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs); self.stack[-1].children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]; break

    def handle_data(self, value):
        self.stack[-1].children.append(value)


def import_directory(source_dir=None):
    def page(path):
        if source_dir:
            filename = 'people.html' if path == '/people/' else path.strip('/').replace('/', '--') + '.html'
            return Tree((source_dir / filename).read_text(encoding='utf-8')).root
        url = BASE + path.rstrip('/') + '/'
        for attempt in range(3):
            try:
                request = Request(url, headers={'User-Agent': 'DigitalFinanceDirectory/1.0 (+https://github.com/MSCA-DN-Digital-Finance)'})
                with urlopen(request, timeout=30) as response:
                    return Tree(response.read().decode('utf-8')).root
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    index = page('/people/')
    cards = index.find('a', 'candidate')
    if not cards:
        raise ValueError('No candidate cards found; refusing an empty directory')
    candidates, short_titles = {}, {}
    for card in cards:
        number = re.fullmatch(r'IRP (\d+)', card.first(cls='candidate-irp').text()).group(1)
        path = card.attrs['href']
        person = page(path).first('main')
        name = person.first('h1').text()
        if name != card.first(cls='candidate-name').text() or number in candidates:
            raise ValueError('Candidate name/IRP mismatch in source')
        contact = person.find(cls='contact')
        links = {a.text(): urljoin(BASE, a.attrs['href']) for a in contact[0].find('a')
                 if public_url(urljoin(BASE, a.attrs['href']))} if contact else {}
        interests = person.find('p', 'prose')
        candidates[number] = {
            'id': path.rstrip('/').split('/')[-1], 'name': name,
            'affiliations': [a.text() for a in person.first('p', 'affiliation').find('a')],
            'research_interests': interests[0].text() if interests else '',
            'orcid': orcid_id(links.get('ORCID')), 'links': links,
            'source_url': urljoin(BASE, path.rstrip('/') + '/'),
        }
        short_titles[number] = card.first(cls='candidate-project').text()
    numbers = set(candidates)
    for link in index.find('a'):
        match = re.fullmatch(r'/research/irp-(\d+)/?', link.attrs.get('href', ''))
        if match:
            numbers.add(match.group(1))
    previous = {p['number'] for p in load()}
    if previous - numbers:
        raise ValueError('Source removed projects unexpectedly; dictionary not changed')
    projects = []
    for number in sorted(numbers, key=int):
        path = f'/research/irp-{number}/'
        research = page(path).first('main')
        title = research.first('h1').text()
        host = ''
        for detail in research.find(cls='detail'):
            labels = detail.find('dt')
            if labels and labels[0].text() == 'Host institution':
                host = ' '.join(c for c in detail.first('dd').children if isinstance(c, str)).strip()
        projects.append({'number': number, 'title': title, 'short_title': short_titles.get(number, title),
                         'host': host, 'source_url': BASE + path, 'candidate': candidates.get(number)})
    return validate({'schema_version': 1, 'source_url': BASE + '/people/', 'projects': projects})


def zenodo_records():
    records, ids = [], set()
    expected = None
    for page_number in range(1, 1001):
        data = fetch_json(f'https://zenodo.org/api/records?communities=digitalfinance&type=publication&all_versions=false&size=25&page={page_number}')
        total = data['hits']['total']
        if isinstance(total, dict):
            if total.get('relation', 'eq') != 'eq':
                raise ValueError('Inexact Zenodo result count')
            total = total['value']
        if type(total) is not int or (expected is not None and total != expected):
            raise ValueError('Zenodo result count changed during pagination')
        expected = total
        for record in data['hits']['hits']:
            if str(record['id']) in ids or 'digitalfinance' not in {c['id'] for c in record['metadata'].get('communities', [])}:
                raise ValueError('Unexpected Zenodo record')
            ids.add(str(record['id'])); records.append(record)
        if len(records) == expected:
            return records
        if not data['hits']['hits'] or len(records) > expected:
            raise ValueError('Incomplete Zenodo result')
        time.sleep(2.1)
    raise ValueError('Too many Zenodo pages')


def enrich_orcids(payload, records):
    payload = copy.deepcopy(payload)
    candidates = {p['number']: p['candidate'] for p in payload['projects'] if p.get('candidate')}
    found = {}
    for record in records:
        for creator in record['metadata'].get('creators', []):
            identifier = orcid_id(creator.get('orcid'))
            if not identifier:
                continue
            for project in match_creators([creator], payload['projects']):
                found.setdefault(project['number'], {})[identifier] = f'https://zenodo.org/records/{record["id"]}'
    for number, identifiers in found.items():
        candidate = candidates[number]
        if not candidate.get('orcid') and len(identifiers) == 1:
            identifier, source = next(iter(identifiers.items()))
            candidate.update(orcid=identifier, orcid_source=source)
            candidate['links']['ORCID'] = 'https://orcid.org/' + identifier
    return validate(payload)


def apply_github_accounts(payload, configuration):
    """Apply maintained candidate identities after each website refresh."""
    if configuration.get('schema_version') != 1 or not isinstance(configuration.get('accounts'), dict):
        raise ValueError('Invalid GitHub account configuration')
    result = copy.deepcopy(payload)
    candidates = {p['candidate']['id']: p['candidate'] for p in result['projects'] if p.get('candidate')}
    seen = set()
    for candidate_id, login in configuration['accounts'].items():
        if candidate_id not in candidates:
            raise ValueError(f'GitHub mapping references an unknown candidate: {candidate_id}')
        if not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?', login):
            raise ValueError('Invalid GitHub username')
        if login.casefold() in seen:
            raise ValueError('A GitHub account cannot belong to two candidates')
        seen.add(login.casefold())
        candidates[candidate_id]['links']['GitHub'] = 'https://github.com/' + login
    return validate(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--zenodo', action='store_true', help='Fill missing ORCIDs from exact Zenodo creator matches')
    parser.add_argument('--zenodo-file', type=Path, help='Use a saved complete Zenodo response for a local import')
    args = parser.parse_args()
    payload = import_directory(args.source_dir)
    if args.zenodo or args.zenodo_file:
        if args.zenodo_file:
            records = json.loads(args.zenodo_file.read_text())['hits']['hits']
        else:
            records = zenodo_records()
        payload = enrich_orcids(payload, records)
    payload = apply_github_accounts(payload, json.loads((ROOT / 'data/github-accounts.json').read_text(encoding='utf-8')))
    if args.write:
        write_json(ROOT / 'data/people.json', payload)
    print(f'{"Imported" if args.write else "Validated"} {len(payload["projects"])} IRPs')
