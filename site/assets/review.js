'use strict';

(() => {
  const owner = 'MSCA-DN-Digital-Finance';
  const repositories = [
    { name: 'Data_inventory', label: 'Data inventory', feed: '/Data_inventory/data/inventory.json', kinds: ['source', 'dataset'] },
    { name: 'Publications', label: 'Publications', feed: '/Publications/data/research.json', kinds: ['publication', 'working-paper', 'collaboration-request'] },
    { name: 'Open_Software', label: 'Open Software', feed: '/Open_Software/data/software.json', kinds: ['software'] },
    { name: 'MSCA-DN-Digital-Finance.github.io', label: 'Research hub', kinds: [] }
  ];
  const proposals = {
    source: ['Data source', 'sources', 'inventory-approved'],
    dataset: ['Dataset', 'datasets', 'inventory-approved'],
    publication: ['Publication or preprint', 'publications', 'publication-approved'],
    'working-paper': ['Working paper', 'working_papers', 'publication-approved'],
    'collaboration-request': ['Collaboration request', 'collaboration_requests', 'collaboration-approved'],
    software: ['Software', 'software', 'software-approved']
  };
  const appliedLabels = new Set(Object.values(proposals).map(([, , label]) => label.replace('-approved', '-applied')));
  const list = document.getElementById('review-items');
  const status = document.getElementById('review-status');
  const refresh = document.getElementById('review-refresh');
  const empty = document.getElementById('review-empty');
  const feeds = new Map();

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  async function request(url) {
    const response = await fetch(url, { cache: 'no-cache', signal: AbortSignal.timeout(12000) });
    if (!response.ok) throw new Error(`Request returned ${response.status}`);
    return response;
  }

  async function githubList(repo, path, query = {}) {
    const url = new URL(`https://api.github.com/repos/${owner}/${repo.name}/${path}`);
    url.search = new URLSearchParams({ ...query, per_page: '100' });
    const rows = [];
    let page = 1;
    let hasNext;
    do {
      url.searchParams.set('page', page++);
      const response = await request(url);
      rows.push(...await response.json());
      hasNext = (response.headers.get('Link') || '').includes('rel="next"');
    } while (hasNext);
    return rows;
  }

  function readProposal(body, kinds) {
    const blocks = [...(body || '').matchAll(/^```json[ \t]*\r?\n([\s\S]*?)^```[ \t]*\r?$/gm)];
    if (blocks.length !== 1) return null;
    try {
      const proposal = JSON.parse(blocks[0][1]);
      if (proposal && Object.keys(proposal).length === 3 && kinds.includes(proposal.kind) && ['add', 'update'].includes(proposal.action)
          && proposal.record && !Array.isArray(proposal.record) && typeof proposal.record === 'object'
          && Object.values(proposal.record).every(value => typeof value === 'string')) return proposal;
    } catch {
      // Leave unstructured or invalid bodies available for review as text.
    }
    return null;
  }

  function proposalFields(record, current) {
    const comparable = Boolean(current);
    const table = element('table', '', 'review-fields');
    const header = table.createTHead().insertRow();
    const columns = comparable ? ['Field', 'Published value', 'Proposed value'] : ['Field', 'Proposed value'];
    for (const column of columns) {
      const th = element('th', column);
      th.scope = 'col';
      header.append(th);
    }
    const rows = table.createTBody();
    const entries = Object.entries(record).filter(([field, value]) => comparable ? value !== (current[field] ?? '') : value !== '');
    for (const [field, value] of entries) {
      const row = rows.insertRow();
      const label = element('th', field.replaceAll('_', ' '));
      label.scope = 'row';
      row.append(label);
      if (comparable) row.insertCell().textContent = current[field] || '—';
      row.insertCell().textContent = value || '—';
    }
    return entries.length ? table : element('p', comparable ? 'No differences from the published values.' : 'No proposed values.');
  }

  async function previewIssue(container, repo, issue, proposal) {
    if (!proposal) {
      container.append(element('p', 'Automatic approval needs one structured proposal in the issue body.', 'muted'));
      if (issue.body) container.append(element('pre', issue.body));
      return;
    }
    const [, collection, approvalLabel] = proposals[proposal.kind];
    let current;
    if (proposal.action === 'update') {
      if (!feeds.has(repo.feed)) feeds.set(repo.feed, request(repo.feed).then(response => response.json()));
      try {
        const feed = await feeds.get(repo.feed);
        current = feed[collection]?.find(row => row.id === proposal.record.id);
      } catch {
        feeds.delete(repo.feed);
      }
      if (!current) container.append(element('p', 'The corresponding published record could not be loaded.', 'muted'));
    }
    const fields = element('div', '', 'review-table-scroll');
    fields.append(proposalFields(proposal.record, current));
    container.append(fields, element('p', `Approval label on GitHub: ${approvalLabel}`, 'muted'));
  }

  async function previewPull(container, repo, number) {
    const files = await githubList(repo, `pulls/${number}/files`);
    for (const file of files) {
      const block = element('section', '', 'review-file');
      block.append(element('h3', file.filename));
      if (file.previous_filename) block.append(element('p', `Previously ${file.previous_filename}`, 'muted'));
      block.append(file.patch ? element('pre', file.patch)
        : element('p', 'GitHub has no inline diff for this file. Open the pull request for the full change.', 'muted'));
      container.append(block);
    }
    if (!files.length) container.append(element('p', 'No changed files were returned by GitHub.', 'muted'));
  }

  function card(repo, issue) {
    const pull = Boolean(issue.pull_request);
    const proposal = pull ? null : readProposal(issue.body, repo.kinds);
    const type = pull ? 'Pull request' : proposal ? proposals[proposal.kind][0] : 'Issue';
    const action = proposal ? (proposal.action === 'add' ? 'New record' : 'Update') : '';
    const approved = proposal && issue.labels.some(label => label.name === proposals[proposal.kind][2]);
    const metadata = [repo.label, `#${issue.number}`, type, action, issue.user?.login, issue.created_at.slice(0, 10)];
    if (approved) metadata.push('Approval label applied');
    if (issue.draft) metadata.push('Draft');
    const item = element('li', '', 'review-item');
    const heading = element('div', '', 'review-item-heading');
    const title = element('div');
    title.append(element('p', metadata.filter(Boolean).join(' · '), 'review-meta'), element('h2', issue.title));
    const link = element('a', 'Review on GitHub ↗', 'button secondary small');
    link.href = `https://github.com/${owner}/${repo.name}/${pull ? 'pull' : 'issues'}/${issue.number}`;
    heading.append(title, link);
    const details = element('details', '', 'review-details');
    details.append(element('summary', pull ? 'Inspect file changes' : 'Inspect proposal'));
    const body = element('div', '', 'review-detail-body');
    details.append(body);
    let requested = false;
    details.addEventListener('toggle', async () => {
      if (!details.open || requested) return;
      requested = true;
      body.textContent = 'Loading details…';
      const content = element('div');
      try {
        if (pull) await previewPull(content, repo, issue.number);
        else await previewIssue(content, repo, issue, proposal);
        body.replaceChildren(content);
      } catch {
        requested = false;
        body.textContent = 'Details could not be loaded. Reopen to retry, or review this item on GitHub.';
      }
    });
    item.append(heading, details);
    return item;
  }

  async function loadQueue() {
    refresh.disabled = true;
    empty.hidden = true;
    status.textContent = 'Loading open items from GitHub…';
    const results = await Promise.allSettled(repositories.map(async repo => {
      const issues = await githubList(repo, 'issues', { state: 'open', sort: 'created', direction: 'desc' });
      return issues.filter(issue => issue.pull_request || (repo.feed
        && !issue.labels.some(label => appliedLabels.has(label.name)))).map(issue => ({ repo, issue }));
    }));
    const items = results.flatMap(result => result.status === 'fulfilled' ? result.value : []);
    const unavailable = repositories.filter((_, i) => results[i].status === 'rejected');
    items.sort((a, b) => b.issue.created_at.localeCompare(a.issue.created_at));
    list.replaceChildren(...items.map(({ repo, issue }) => card(repo, issue)));
    const count = `${items.length} open ${items.length === 1 ? 'item' : 'items'}`;
    status.textContent = unavailable.length
      ? `${count} loaded. GitHub did not return items from ${unavailable.map(repo => repo.label).join(', ')}.`
      : count;
    empty.hidden = items.length > 0 || unavailable.length > 0;
    refresh.disabled = false;
  }

  document.getElementById('review-toolbar').hidden = false;
  refresh.addEventListener('click', () => { feeds.clear(); loadQueue(); });
  loadQueue();
})();
