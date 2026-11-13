import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_site
import directory
import import_people
import sync_catalogues


def project(number='14'):
    return {'number': number, 'title': 'Financial research', 'short_title': 'Research theme',
            'host': 'Test University', 'source_url': 'https://example.org/research/irp-' + number,
            'candidate': {'id': 'researcher-one', 'name': 'Researcher Mollá', 'affiliations': ['Test University'],
                          'orcid': '0009-0005-5509-8652', 'links': {'ORCID': 'https://orcid.org/0009-0005-5509-8652'},
                          'source_url': 'https://example.org/people/researcher-one', 'research_interests': 'Forecasting'}}


def payload():
    vacant = project('3'); vacant['candidate'] = None
    return {'schema_version': 1, 'source_url': 'https://example.org/people/', 'projects': [vacant, project()]}


class IdentityTests(unittest.TestCase):
    def test_matches_orcid_full_names_accents_and_name_order(self):
        projects = payload()['projects']
        for creator in [{'name': 'Different display name', 'orcid': 'https://orcid.org/0009-0005-5509-8652'},
                        {'name': 'Molla, Researcher'}, {'name': 'RESEARCHER MOLLÁ'}]:
            self.assertEqual([p['number'] for p in directory.match_creators([creator], projects)], ['14'])

    def test_does_not_guess_initials_partial_names_or_conflicting_identifiers(self):
        projects = payload()['projects']
        for creator in [{'name': 'R. Molla'}, {'name': 'Molla'}, {'name': 'Researcher Mollá', 'orcid': '0000-0002-9123-3883'}]:
            self.assertEqual(directory.match_creators([creator], projects), [])
        duplicate = copy.deepcopy(project()); duplicate['number'] = '15'
        self.assertEqual(directory.match_creators([{'name': 'Researcher Mollá'}], projects + [duplicate]), [])

    def test_normalizes_old_irp_separator_and_resolves_canonical_names(self):
        row = directory.enrich({'IRP': '14, 3', 'researcher_names': 'Old spelling'}, payload()['projects'], 'IRP')
        self.assertEqual(row['IRP'], '14;3')
        self.assertEqual(row['researcher_names'], 'Researcher Mollá')
        self.assertEqual(row['irp_titles'], 'Financial research;Financial research')

    def test_rejects_duplicate_numbers_orcids_and_unsafe_social_links(self):
        for kind in ['number', 'orcid', 'url']:
            data = payload()
            if kind == 'number': data['projects'].append(project())
            if kind == 'orcid':
                other = project('15'); other['candidate']['id'] = 'researcher-two'; data['projects'].append(other)
            if kind == 'url': data['projects'][1]['candidate']['links']['LinkedIn'] = 'javascript:alert(1)'
            with self.subTest(kind=kind), self.assertRaises(ValueError): directory.validate(data)

    def test_orcid_enrichment_is_sourced_and_conflicts_are_left_unresolved(self):
        data = payload(); data['projects'][1]['candidate']['orcid'] = ''; data['projects'][1]['candidate']['links'] = {}
        records = [{'id': 10, 'metadata': {'creators': [{'name': 'Molla, Researcher', 'orcid': '0009-0005-5509-8652'}]}}]
        result = import_people.enrich_orcids(data, records)
        self.assertEqual(result['projects'][1]['candidate']['orcid_source'], 'https://zenodo.org/records/10')
        self.assertEqual(data['projects'][1]['candidate']['orcid'], '')
        records.append({'id': 11, 'metadata': {'creators': [{'name': 'Researcher Molla', 'orcid': '0000-0002-9123-3883'}]}})
        self.assertEqual(import_people.enrich_orcids(data, records)['projects'][1]['candidate']['orcid'], '')

    def test_invalid_or_shrinking_remote_dictionary_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory.write_json(root / 'data/people.json', payload())
            before = (root / 'data/people.json').read_bytes()
            for remote in [{}, {**payload(), 'projects': [project()]}]:
                with patch.object(directory, 'fetch_json', return_value=remote), self.assertRaises(ValueError): directory.sync(root)
                self.assertEqual((root / 'data/people.json').read_bytes(), before)


class ImportTests(unittest.TestCase):
    def test_source_cards_profiles_vacancies_affiliations_and_public_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'people.html').write_text('<a href="/research/irp-3">IRP 3</a><a class="candidate" href="/people/researcher-one"><span class="candidate-irp">IRP 14</span><span class="candidate-name">Researcher Mollá</span><span class="candidate-project">Research theme</span></a>')
            (root / 'people--researcher-one.html').write_text('<main><h1>Researcher Mollá</h1><p class="affiliation"><a>Test University</a></p><p class="prose">Forecasting</p><ul class="contact"><li><a href="mailto:private@example.org">Email</a></li><li><a href="https://orcid.org/0009-0005-5509-8652">ORCID</a></li></ul></main>')
            for number in ['3', '14']:
                (root / f'research--irp-{number}.html').write_text('<main><h1>Financial research</h1><div class="detail"><dt>Host institution</dt><dd>Test University<span>Country</span></dd></div></main>')
            with patch.object(import_people, 'load', return_value=[]): result = import_people.import_directory(root)
            self.assertIsNone(result['projects'][0]['candidate'])
            self.assertEqual(result['projects'][1]['host'], 'Test University')
            self.assertEqual(result['projects'][1]['candidate']['links'], {'ORCID': 'https://orcid.org/0009-0005-5509-8652'})
            with patch.object(import_people, 'load', return_value=[project('99')]), self.assertRaises(ValueError): import_people.import_directory(root)


class ProfileTests(unittest.TestCase):
    def test_builds_own_pages_safe_summaries_references_and_edit_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(build_site.ROOT / 'site', root / 'site')
            directory.write_json(root / 'data/people.json', payload())
            directory.write_json(root / 'data/catalogues.json', {'publications': [{'id': 'sample-paper', 'title': 'Sample paper', 'irp_numbers': '14', 'year': '2026'}]})
            (root / 'profiles').mkdir()
            for number in ['3', '14']: (root / f'profiles/irp-{number}.md').write_text('A summary <script>alert(1)</script>.')
            build_site.build(root)
            profile = (root / '_site/irps/irp-14.html').read_text()
            self.assertIn('Researcher Mollá', profile)
            self.assertIn('profiles/irp-14.md', profile)
            self.assertIn('/Publications/#publication/sample-paper', profile)
            self.assertIn('&lt;script&gt;', profile)
            self.assertNotIn('<script>alert(1)</script>', profile)
            self.assertIn('Candidate not currently assigned', (root / '_site/irps/irp-3.html').read_text())
            self.assertEqual((root / '_site/irps/index.html').read_text().count('data-irp-card'), 2)

    def test_local_catalogue_collection_rejects_bad_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp); root = parent / 'hub'; root.mkdir()
            for repo, filename, kinds in sync_catalogues.FEEDS:
                target = parent / repo / '_site/data' / filename
                target.parent.mkdir(parents=True)
                target.write_text(json.dumps({kind: [] for kind in kinds}))
            self.assertEqual(set(sync_catalogues.collect(True, root)), {'sources', 'datasets', 'publications', 'working_papers', 'software'})
            (parent / 'Publications/_site/data/research.json').write_text('{"publications": "not records"}')
            with self.assertRaises(ValueError): sync_catalogues.collect(True, root)


if __name__ == '__main__':
    unittest.main()
