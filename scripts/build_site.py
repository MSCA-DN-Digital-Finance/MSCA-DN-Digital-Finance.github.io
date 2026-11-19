#!/usr/bin/env python3
"""Build the DIGITAL hub, shared directory and individual IRP profiles."""
import html
import json
from pathlib import Path
import re
import shutil

from directory import ROOT, load

KINDS = [('sources', 'Data sources', '/Data_inventory/?irp='),
         ('datasets', 'Datasets', '/Data_inventory/datasets.html?irp='),
         ('publications', 'Publications & preprints', '/Publications/?irp='),
         ('working_papers', 'Working papers', '/Publications/working-papers.html?irp='),
         ('software', 'Open Software', '/Open_Software/?irp=')]
REPO = 'https://github.com/MSCA-DN-Digital-Finance/MSCA-DN-Digital-Finance.github.io'


def e(value):
    return html.escape(str(value or ''), quote=True)


def summaries(root, projects):
    result = {}
    for project in projects:
        path = root / 'profiles' / f'irp-{project["number"]}.md'
        if not path.exists():
            raise ValueError(f'Missing research summary: {path}')
        value = path.read_text(encoding='utf-8').strip()
        if not value or len(value) > 12000:
            raise ValueError(f'{path}: summary must contain 1–12000 characters')
        result[project['number']] = value
    return result


def related_html(kind, records, number):
    matches = [r for r in records if number in [n.strip() for n in re.split(r'[;,]', r.get('irp_numbers') or r.get('IRP') or '')]]
    if not matches:
        return '<p class="muted related-empty">No records listed for this IRP yet.</p>'
    items = []
    for row in matches:
        title = row.get('title') or row.get('name') or row.get('dataset_name')
        if kind in {'sources', 'datasets'}:
            prefix = '/Data_inventory/' + ('datasets.html' if kind == 'datasets' else '')
            link = prefix + '#' + ('dataset' if kind == 'datasets' else 'source') + '/' + row['id']
        elif kind == 'software':
            link = '/Open_Software/#software/' + row['id']
        else:
            link = '/Publications/' + ('working-papers.html' if kind == 'working_papers' else '') + '#' + ('working-paper' if kind == 'working_papers' else 'publication') + '/' + row['id']
        items.append(f'<li><a href="{e(link)}">{e(title)}</a>{"<span>" + e(row.get("year")) + "</span>" if row.get("year") else ""}</li>')
    return '<ul class="related-list">' + ''.join(items) + '</ul>'


def build(root=None):
    root = root or ROOT
    projects = load(root)
    if not projects:
        raise ValueError('The hub requires the canonical people dictionary')
    summary = summaries(root, projects)
    cache_path = root / 'data/catalogues.json'
    catalogues = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    out = root / '_site'
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(root / 'site', out)
    shutil.copytree(root / 'data', out / 'data')
    template = (root / 'site/index.html').read_text()

    def page(content, title, active_path, script):
        rendered = re.sub(r'<title>.*?</title>', '<title>' + e(title) + ' · DIGITAL</title>', template)
        rendered = rendered.replace('href="/" class="active" aria-current="page"', 'href="/"')
        rendered = rendered.replace(f'href="{active_path}"', f'href="{active_path}" class="active" aria-current="page"', 1)
        rendered = rendered.replace('href="assets/', 'href="/assets/').replace('src="assets/', 'src="/assets/')
        rendered = re.sub(r'<main id="main">.*?</main>', lambda _: '<main id="main">' + content + '</main>', rendered, flags=re.S)
        return rendered.replace('</head>', f'<script src="/assets/{script}" defer></script></head>')

    review = out / 'review'
    review.mkdir()
    review_content = '''<section class="catalogue profile-page review-page">
  <div class="source-heading">
    <h1>Pending edits</h1>
    <p>Inspect catalogue proposals and pull requests before approving them on GitHub.</p>
  </div>
  <div class="review-toolbar" id="review-toolbar" hidden>
    <p id="review-status" role="status" aria-live="polite"></p>
    <button id="review-refresh" class="button secondary small" type="button">Refresh</button>
  </div>
  <ul id="review-items" class="review-items" aria-label="Open proposals and pull requests"></ul>
  <p id="review-empty" class="empty" hidden>No proposals or pull requests are awaiting review.</p>
  <noscript><p>Enable JavaScript to load the queue here, or browse the open items on GitHub below.</p></noscript>
  <div class="review-links inline-links" aria-label="Open items on GitHub">
    <a href="https://github.com/MSCA-DN-Digital-Finance/Data_inventory/issues">Data inventory issues</a>
    <a href="https://github.com/MSCA-DN-Digital-Finance/Publications/issues">Publication issues</a>
    <a href="https://github.com/MSCA-DN-Digital-Finance/Open_Software/issues">Software issues</a>
    <a href="https://github.com/MSCA-DN-Digital-Finance/MSCA-DN-Digital-Finance.github.io/pulls">Research hub pull requests</a>
  </div>
</section>'''
    (review / 'index.html').write_text(page(review_content, 'Pending edits', '/review/', 'review.js'), encoding='utf-8')

    profiles = out / 'irps'
    profiles.mkdir()
    cards = []
    for project in projects:
        number, candidate = project['number'], project.get('candidate')
        name = candidate['name'] if candidate else 'Candidate not currently assigned'
        search = ' '.join([number, name, project['title'], project['short_title'], project['host']])
        cards.append(f'<a class="irp-card" data-irp-card data-search="{e(search.lower())}" href="irp-{number}.html"><span class="irp-number">IRP {number}</span><h2>{e(project["short_title"])}</h2><p class="candidate-name">{e(name)}</p><p class="muted">{e(project["host"])}</p><span class="resource-link">Research profile →</span></a>')
        links = ''.join(f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">{e(label)} ↗</a>' for label, url in (candidate['links'] if candidate else {}).items())
        affiliations = '; '.join(candidate['affiliations']) if candidate else project['host']
        paragraphs = ''.join(f'<p>{e(part)}</p>' for part in re.split(r'\n\s*\n', summary[number]))
        interests = f'<p><strong>Research interests:</strong> {e(candidate.get("research_interests"))}</p>' if candidate and candidate.get('research_interests') else ''
        sections = ''.join(f'<section class="profile-records" aria-labelledby="{kind}-title"><div class="profile-section-heading"><h2 id="{kind}-title">{label}</h2><a href="{prefix}{number}">Browse catalogue ↗</a></div><div data-related="{kind}">{related_html(kind, catalogues.get(kind, []), number)}</div></section>' for kind, label, prefix in KINDS)
        source = candidate['source_url'] if candidate else project['source_url']
        content = f'''<section class="catalogue profile-page" data-irp="{number}"><a class="text-link" href="/irps/">← All doctoral candidates & IRPs</a><header class="profile-heading"><p class="irp-number">Individual Research Project {number}</p><h1>{e(name)}</h1><h2>{e(project['title'])}</h2><p class="muted">{e(affiliations)}</p><div class="profile-links">{links}<a href="{e(source)}" target="_blank" rel="noopener noreferrer">Network profile ↗</a></div></header><section class="research-summary"><div class="profile-section-heading"><h2>Research summary</h2><a href="{REPO}/edit/main/profiles/irp-{number}.md">Edit research summary ↗</a></div>{paragraphs}{interests}<p class="summary-note">Initial summary adapted from the <a href="{e(project['source_url'])}">network project description</a>. Candidates can propose updates through GitHub; changes are published after review.</p></section><div class="profile-section-heading"><h2>Related research & data</h2><p id="catalogue-status" class="muted" role="status">Records associated with IRP {number} in the research catalogues.</p></div>{sections}</section>'''
        (profiles / f'irp-{number}.html').write_text(page(content, f'IRP {number} · {name}', '/irps/', 'irps.js'), encoding='utf-8')
    assigned = sum(bool(p.get('candidate')) for p in projects)
    content = f'''<section class="catalogue directory-page"><div class="source-heading"><p class="irp-number">People & research projects</p><h1>Doctoral candidates & IRPs</h1><p>{assigned} doctoral candidates · {len(projects)} individual research projects</p></div><div class="search-wrap"><label for="irp-search" class="muted">Find an IRP</label><input type="search" id="irp-search" placeholder="Name, number, research theme or institution…" aria-label="Find an IRP by name, number, research theme or institution"></div><p id="irp-count" role="status">{len(projects)} projects</p><div class="irp-grid">{''.join(cards)}</div><p id="irp-empty" class="empty" hidden>No matching projects. Try another name or research theme.</p><p class="directory-source muted">Identities, institutions and project titles come from the <a href="https://beta.digital-finance-msca.com/people/">DIGITAL people directory</a>. Public ORCIDs may also be verified against matched Zenodo records.</p></section>'''
    (profiles / 'index.html').write_text(page(content, 'Doctoral candidates & IRPs', '/irps/', 'irps.js'), encoding='utf-8')
    (out / '.nojekyll').touch()
    print(f'Built research hub, {len(projects)} IRP pages and {assigned} candidate profiles → {out}')


if __name__ == '__main__':
    build()
