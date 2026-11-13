'use strict';
(() => {
  const search=document.getElementById('irp-search');
  if(search){
    const cards=[...document.querySelectorAll('[data-irp-card]')];
    search.addEventListener('input',()=>{
      const words=search.value.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
      let count=0;
      cards.forEach(card=>{card.hidden=!words.every(word=>card.dataset.search.includes(word));if(!card.hidden)count++;});
      document.getElementById('irp-count').textContent=`${count} ${count===1?'project':'projects'}`;
      document.getElementById('irp-empty').hidden=count>0;
    });
  }
  const profile=document.querySelector('[data-irp]');
  if(!profile)return;
  const number=profile.dataset.irp;
  const split=value=>(value||'').split(/[;,]/).map(s=>s.trim()).filter(Boolean);
  function render(kind, rows){
    if(!Array.isArray(rows))throw new Error('Invalid catalogue');
    const selected=rows.filter(row=>split(row.irp_numbers||row.IRP).includes(number));
    const container=profile.querySelector(`[data-related="${kind}"]`);
    if(!selected.length){const empty=document.createElement('p');empty.className='muted related-empty';empty.textContent='No records listed for this IRP yet.';container.replaceChildren(empty);return;}
    const list=document.createElement('ul');list.className='related-list';
    selected.forEach(row=>{
      if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(row.id))throw new Error('Invalid record ID');
      const item=document.createElement('li'),link=document.createElement('a');
      const paths={sources:'/Data_inventory/#source/',datasets:'/Data_inventory/datasets.html#dataset/',publications:'/Publications/#publication/',working_papers:'/Publications/working-papers.html#working-paper/',software:'/Open_Software/#software/'};
      link.href=paths[kind]+row.id;link.textContent=row.title||row.name||row.dataset_name;item.append(link);
      if(row.year){const year=document.createElement('span');year.textContent=row.year;item.append(year);}
      list.append(item);
    });
    container.replaceChildren(list);
  }
  const sources=[['/Data_inventory/data/inventory.json',['sources','datasets']],['/Publications/data/research.json',['publications','working_papers']],['/Open_Software/data/software.json',['software']]];
  Promise.allSettled(sources.map(async([url,kinds])=>{
    const response=await fetch(url,{signal:AbortSignal.timeout(10000)});
    if(!response.ok)throw new Error('Catalogue unavailable');
    const data=await response.json();
    if(kinds.some(kind=>!Array.isArray(data[kind])))throw new Error('Invalid catalogue');
    kinds.forEach(kind=>render(kind,data[kind]));
  })).then(results=>{
    document.getElementById('catalogue-status').textContent=results.every(r=>r.status==='fulfilled')?'Showing the latest published catalogue records.':'Some catalogues could not be refreshed. Previously indexed records are shown where available.';
  });
})();
