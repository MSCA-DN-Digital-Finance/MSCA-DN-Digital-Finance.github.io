# DIGITAL · Research resources

Organization landing page for the MSCA Digital Finance research resources.

Published at **https://msca-dn-digital-finance.github.io/**. GitHub Pages requires this organization site repository to be named **MSCA-DN-Digital-Finance.github.io**.

The existing project repositories remain independent:

- `/Data_inventory/` — data sources
- `/Data_inventory/datasets.html` — prepared datasets
- `/Publications/` — publications and preprints
- `/Publications/working-papers.html` — working papers and collaboration requests

The repositories share the DIGITAL and EU funding branding and a consistent navigation. The landing page contains links, not copied research records, so it does not need rebuilding when the catalogues change. Publication submissions and approvals are handled in the Publications repository; data submissions in Data_inventory.

## Development

```sh
python3 scripts/build_site.py
python3 -m http.server 8000 --directory _site
```

The build uses only Python's standard library. For a local preview with working links to the other projects, mount their generated sites at `Data_inventory/` and `Publications/` under the preview root.

Enable **Settings → Pages → Source → GitHub Actions**. The workflow publishes pushes to `main` and manual runs; pull requests are built without deploying. No personal tokens or external runtime dependencies are needed.
