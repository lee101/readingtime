async function subscribe(plan, btn){
  const t = btn && btn.textContent; if(btn){ btn.disabled = true; btn.textContent = 'One moment…'; }
  try{
    const r = await fetch('/api/billing/checkout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan})});
    const d = await r.json();
    if(!r.ok) throw new Error(d.error||'failed');
    if(window.th){ th('track','begin_checkout',{plan,currency:'USD',value:plan==='year'?90:9,surface:location.pathname.split('/')[1]||'home'}); th('flush'); }
    location.href = d.url;
  }catch(e){ alert(e.message); if(btn){ btn.disabled=false; btn.textContent=t; } }
}
async function manageBilling(btn){
  btn.disabled = true;
  try{
    const r = await fetch('/api/billing/portal',{method:'POST'}); const d = await r.json();
    if(!r.ok) throw new Error(d.error||'failed'); location.href = d.url;
  }catch(e){ alert(e.message); btn.disabled=false; }
}
