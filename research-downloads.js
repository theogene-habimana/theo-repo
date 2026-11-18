// Static research file download listing. No external services required.
(async function(){
  const script = document.querySelector('script[data-project]');
  const project = script && script.dataset.project;
  if (!['cybersecurity','artificial-intelligence'].includes(project)) return;
  const base = `files/${project}/`;
  const categories = ['excel','code','results','methodology'];
  let data;
  try {
    const response = await fetch(base + 'manifest.json', {cache:'no-store'});
    if (!response.ok) return;
    data = await response.json();
  } catch(e){ return; }
  for (const category of categories){
    const list = document.querySelector(`[data-file-category="${category}"]`);
    if (!list || !Array.isArray(data[category])) continue;
    const items = data[category].filter(item => item && typeof item.path === 'string' && /^[a-zA-Z0-9][a-zA-Z0-9._ -]*$/.test(item.path) && !item.path.startsWith('.') && !item.path.includes('..'));
    if (!items.length) continue;
    list.replaceChildren();
    for (const item of items){
      const li=document.createElement('li');
      const a=document.createElement('a');
      a.href=base + encodeURIComponent(item.path);
      a.setAttribute('download','');
      a.textContent=(item.title || item.path) + ' ↓';
      li.appendChild(a);
      if(item.description){const small=document.createElement('small');small.textContent=item.description;li.appendChild(small)}
      list.appendChild(li);
    }
  }
})();
