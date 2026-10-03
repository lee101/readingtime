(function(){
  var input=document.querySelector('[data-rt-search]');
  if(!input)return;
  var browse=document.getElementById('browse'),box=document.getElementById('search-results'),
      grid=document.getElementById('search-grid'),title=document.getElementById('search-title');
  var docs=null,loading=null,seq=0;
  function tok(s){return (s||'').toLowerCase().split(/[^\p{L}\p{N}]+/u).filter(Boolean)}
  function pre(ws,q){for(var i=0;i<ws.length;i++)if(ws[i].indexOf(q)===0)return true;return false}
  function score(d,qs){
    var t=d._t||(d._t=tok(d.t)),a=d._a||(d._a=tok(d.a)),b=d._b||(d._b=tok(d.b)),n=0;
    for(var i=0;i<qs.length;i++){var q=qs[i];
      if(pre(t,q)){n+=6;if(t[0]&&t[0].indexOf(q)===0)n+=2}
      else if(pre(a,q))n+=3;
      else if(pre(b,q))n+=1;
      else return 0}
    return n}
  function search(q){
    var qs=tok(q),hits=[];
    for(var i=0;i<docs.length;i++){var s=score(docs[i],qs);if(s)hits.push([s,i,docs[i]])}
    hits.sort(function(x,y){return y[0]-x[0]||x[1]-y[1]});
    return hits.slice(0,60).map(function(h){return h[2]})}
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
  function card(d){
    return '<a class="card" href="'+esc(d.h)+'"><div class="card-cover">'+
      (d.c?'<img src="'+esc(d.c)+'" alt="'+esc(d.t)+'" loading="lazy">':'<div class="card-cover-blank">📖</div>')+
      '</div><div class="card-meta"><span class="card-title">'+esc(d.t)+'</span>'+
      (d.a?'<span class="card-author">by '+esc(d.a)+'</span>':'')+
      (d.m?'<span class="card-time">'+d.m+' min read</span>':'')+'</div></a>'}
  function show(q,res){
    var has=q.trim()!=='';
    if(browse)browse.hidden=has;
    box.hidden=!has;
    if(!has)return;
    title.textContent=res.length+' result'+(res.length===1?'':'s')+' for “'+q.trim()+'”';
    grid.innerHTML=res.length?res.map(card).join(''):'<p class="search-empty">No stories match. Try fewer letters, or <a href="/author">create one</a>.</p>'}
  function load(){
    if(docs)return Promise.resolve();
    if(!loading)loading=fetch('/api/search/index').then(function(r){return r.json()}).then(function(j){docs=j}).catch(function(){loading=null});
    return loading}
  function serverSearch(q,id){
    fetch('/api/search?q='+encodeURIComponent(q)).then(function(r){return r.json()}).then(function(j){
      if(id!==seq||docs)return;
      show(q,(j.results||[]).map(function(d){return d}))}).catch(function(){})}
  function run(){
    var q=input.value,id=++seq;
    syncURL(q);
    if(docs)return show(q,q.trim()?search(q):[]);
    if(q.trim())serverSearch(q,id);else show(q,[]);
    load().then(function(){if(docs&&id===seq)show(q,q.trim()?search(q):[])})}
  function syncURL(q){
    try{var u=new URL(location.href);if(q.trim())u.searchParams.set('q',q.trim());else u.searchParams.delete('q');
      history.replaceState(null,'',u)}catch(e){}}
  input.addEventListener('input',run);
  input.addEventListener('focus',load,{once:true});
  input.form.addEventListener('submit',function(e){e.preventDefault();run()});
  document.addEventListener('keydown',function(e){
    if(e.key==='/'&&!/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)&&!e.metaKey&&!e.ctrlKey){e.preventDefault();input.focus()}
    else if(e.key==='Escape'&&document.activeElement===input){input.value='';run();input.blur()}});
})();
