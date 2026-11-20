// Renders the project cards on research-projects.html.
// Data comes from projects-data.js (window.RESEARCH_PROJECTS); no network requests are needed.
(function () {
  const root = document.getElementById('projectList');
  if (!root) return;

  const SAFE_ID = /^[a-z0-9][a-z0-9-]*$/;
  const SAFE_FILE = /^[a-zA-Z0-9][a-zA-Z0-9._ -]*$/;
  const SAFE_ICON = /^fa-(solid|regular) fa-[a-z0-9-]+$/;
  const CATEGORIES = [
    { key: 'excel', label: 'Excel datasets', icon: 'fa-regular fa-file-excel', empty: 'No Excel datasets published yet.' },
    { key: 'code', label: 'Python scripts', icon: 'fa-solid fa-code', empty: 'No scripts published yet.' },
    { key: 'results', label: 'Research results', icon: 'fa-solid fa-chart-column', empty: 'No research results published yet.' },
    { key: 'methodology', label: 'Methodology', icon: 'fa-regular fa-file-lines', empty: 'No methodology published yet.' }
  ];

  const el = (tag, attrs = {}, text) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const icon = cls => el('i', { class: cls, 'aria-hidden': 'true' });
  const projects = Array.isArray(window.RESEARCH_PROJECTS) ? window.RESEARCH_PROJECTS : null;
  if (!projects) {
    root.replaceChildren(el('p', { class: 'project-load-error' }, 'Projects could not be loaded (projects-data.js is missing).'));
    return;
  }

  for (const project of projects) {
    if (!project || !SAFE_ID.test(project.id || '') || !SAFE_ID.test(project.folder || '')) continue;
    const manifest = project.files || {};

    const card = el('article', { class: 'research-project-card', id: project.id });
    const heading = el('div', { class: 'project-heading' });
    if (SAFE_ICON.test(project.icon || '')) heading.appendChild(icon(project.icon));
    heading.appendChild(el('h3', {}, project.title || project.id));
    card.appendChild(heading);
    if (project.status) card.appendChild(el('p', { class: 'project-tag' }, project.status));

    if (project.overview) {
      card.appendChild(el('h4', {}, 'Research overview'));
      card.appendChild(el('p', { class: 'research-overview' }, project.overview));
    }

    card.appendChild(el('div', { class: 'project-divider' }));
    card.appendChild(el('h4', {}, 'Research materials'));

    const groups = el('div', { class: 'research-downloads' });
    for (const cat of CATEGORIES) {
      const group = el('section', { class: 'download-group', 'aria-label': cat.label });
      const h = el('h4');
      h.append(icon(cat.icon), ' ' + cat.label);
      group.appendChild(h);

      const items = (Array.isArray(manifest[cat.key]) ? manifest[cat.key] : [])
        .filter(i => i && typeof i.path === 'string' && SAFE_FILE.test(i.path) && !i.path.includes('..'));
      if (!items.length) {
        group.appendChild(el('p', { class: 'download-empty' }, cat.empty));
      } else {
        const ul = el('ul', { class: 'download-list' });
        for (const item of items) {
          const li = el('li');
          const ext = (item.path.split('.').pop() || '').toUpperCase();
          const a = el('a', {
            class: 'download-button',
            href: `files/${project.folder}/${encodeURIComponent(item.path)}`,
            download: item.path,
            'aria-label': `Download ${item.title || item.path} (${ext})`
          });
          a.append(icon('fa-solid fa-download'), ' Download ' + ext);
          li.append(el('strong', { class: 'download-title' }, item.title || item.path));
          if (item.description) li.appendChild(el('small', {}, item.description));
          li.appendChild(a);
          ul.appendChild(li);
        }
        group.appendChild(ul);
      }
      groups.appendChild(group);
    }
    card.appendChild(groups);
    root.appendChild(card);
  }

  // Honour a deep link such as research-projects.html#cybersecurity after rendering
  if (location.hash) {
    const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (target) target.scrollIntoView();
  }
})();
