# DIGITAL · Research resources

Organization hub and canonical doctoral candidate / IRP directory for the MSCA Digital Finance research resources.

Published at **https://msca-dn-digital-finance.github.io/**. GitHub Pages requires this organization site repository to be named **MSCA-DN-Digital-Finance.github.io**.

The existing project repositories remain independent:

- `/Data_inventory/` — data sources
- `/Data_inventory/datasets.html` — prepared datasets
- `/Publications/` — publications and preprints
- `/Publications/working-papers.html` — working papers and collaboration requests
- `/irps/` — searchable directory of all 17 IRPs and 14 current doctoral candidates
- `/irps/irp-14.html` — individual research profile (one page per IRP)
- `/Open_Software/` — research software, linked papers, repositories, indexing and data availability

The repositories share the DIGITAL and EU funding branding, navigation and the same candidate dictionary. Publication submissions and approvals are handled in Publications; data submissions in Data_inventory. Profiles show associated data sources, datasets, publications, working papers and open software. They refresh from the published catalogue JSON feeds when opened, with a committed reference index as the fallback for unavailable feeds or JavaScript being disabled.

## Shared candidate and IRP dictionary

`data/people.json` is the canonical source for IRP numbers, project titles, candidate names, affiliations, research interests and public social/profile links. It was built from the [network people directory](https://beta.digital-finance-msca.com/people/) and its linked candidate and research pages. IRPs 3, 5 and 6 currently have no candidate; their projects remain visible. Missing social links are left unknown. Public email addresses are not imported.

The dictionary can fill missing ORCIDs from Zenodo creators whose full names match exactly after normalizing accents, punctuation and name order. Conflicting or ambiguous identities are not guessed. Added identifiers retain the Zenodo record URL as provenance. Publications use ORCID first, then an exact full-name match, to fill candidate names and IRP numbers. Initials and partial names do not establish an association.

`scripts/directory.py` contains the shared dictionary validator and matching/enrichment functions. The same reviewed module is included in all three catalogue repositories. Each consumer keeps `data/people.json` as an offline snapshot and refreshes it from this repository's `main` branch. Catalogue builds resolve candidate names and project titles from IRP numbers and include them in the public JSON and CSV exports. Historical comma-separated IRP lists are normalized to semicolons in those exports.

**Sync people and research references** runs daily at **04:23 UTC** and can be run manually. It refreshes the source dictionary, fills missing ORCIDs from Zenodo, refreshes the reference index, validates and commits changes, then explicitly dispatches Pages. Summaries in `profiles/` are never overwritten by source synchronization. Publications refreshes its snapshot with the daily Zenodo job at **05:23 UTC**; Data_inventory has a directory sync at **05:43 UTC**; Open_Software refreshes its IRP and paper dictionaries at **06:03 UTC**. All four workflows use their repository's automatic `GITHUB_TOKEN`; no personal token or Zenodo key is required. Branch rules must permit the bot commits. Failed or incomplete imports are not committed.

For activation, merge this repository's dictionary into `main`, merge/deploy all three catalogue repositories (including their new JSON exports), and then run this repository's sync workflow. Until the consumer exports are deployed, profiles use the included reference index and any available live feed. No cross-repository write permission is needed.

## Edit a research summary

Every profile has **Edit research summary**, opening its `profiles/irp-N.md` file on GitHub. Candidates can edit the text and submit a pull request (GitHub can offer a fork for users without write access). A maintainer reviews and merges it; the Pages workflow publishes the result. Summaries support plain paragraphs, preserve line breaks, and escape HTML. Initial summaries are brief adaptations of the source descriptions; missing or abridged research descriptions are explicitly identified. Changing the shared identity dictionary is a separate reviewed change.

## Development

```sh
python3 scripts/build_site.py
python3 -m unittest discover -s tests -v
python3 -m http.server 8000 --directory _site
```

The build uses only Python's standard library. For a local preview with working links to the other projects, mount their generated sites at `Data_inventory/` and `Publications/` under the preview root.

To refresh public source data manually:

```sh
python3 scripts/import_people.py --zenodo              # Validate without writing
python3 scripts/import_people.py --zenodo --write      # Refresh identities only
python3 scripts/sync_catalogues.py                    # Published catalogue feeds
python3 scripts/sync_catalogues.py --local            # Or sibling repositories' _site exports
python3 scripts/build_site.py
```

The producer feeds are `/Data_inventory/data/inventory.json`, `/Publications/data/research.json` and `/Open_Software/data/software.json`. `data/catalogues.json` stores only record IDs, titles, years and explicit IRP associations for fallback rendering. Each IRP page includes an Open Software section with links to its associated code. A source is linked to an IRP because that relationship is recorded in the catalogue, not because it might be relevant to the research theme.

Enable **Settings → Pages → Source → GitHub Actions**. The workflow publishes pushes to `main` and manual runs; pull requests are built without deploying. No personal tokens or external runtime dependencies are needed.
