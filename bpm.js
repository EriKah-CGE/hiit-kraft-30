// ---------- Tempo: Takt-Tippen und Nachschlagen bei GetSongBPM ----------
// API: https://api.getsong.co/search/?api_key=…&type=both&lookup=song:… artist:…
// Antwort: {"search":[{title, artist:{name}, tempo:"128", …}]}, ohne Treffer {"search":{"error":"no result"}}.
// Die API sendet Access-Control-Allow-Origin: *, der Schlüssel geht als URL-Parameter (einfacher GET, kein Preflight).
const Tempo=(function(){
  const API='https://api.getsong.co/search/';
  const MIN=60,MAX=200,GAP=2500,KEEP=8;

  function fold(b){b=+b;if(!(b>0))return null;while(b<MIN)b*=2;while(b>MAX)b/=2;return Math.round(b);}
  function median(a){const s=[...a].sort((x,y)=>x-y),m=s.length>>1;return s.length%2?s[m]:(s[m-1]+s[m])/2;}

  // ---- Takt tippen ----
  let taps=[],count=0;
  function tap(now){
    if(taps.length&&now-taps[taps.length-1]>GAP){taps=[];count=0;}
    taps.push(now);count++;
    if(taps.length>KEEP)taps.shift();
    if(taps.length<4)return {n:count,bpm:null};
    const iv=[];for(let i=1;i<taps.length;i++)iv.push(taps[i]-taps[i-1]);
    return {n:count,bpm:fold(60000/median(iv))};
  }
  function resetTap(){taps=[];count=0;}
  function lastTap(){return taps.length?taps[taps.length-1]:0;}

  // ---- Normalisieren für den Vergleich ----
  function cleanTitle(s){return String(s||'').replace(/\s+-\s+.*$/,'').replace(/[([].*?[)\]]/g,' ').replace(/\s+/g,' ').trim();}
  function norm(s){
    return String(s||'').toLowerCase().replace(/ß/g,'ss').normalize('NFD').replace(/[̀-ͯ]/g,'')
      .replace(/\s+-\s+.*$/,'').replace(/[([].*?[)\]]/g,' ')
      .replace(/\b(feat|ft|featuring)\b.*$/,'').replace(/&/g,' and ')
      .replace(/^the\s+/,'').replace(/[^a-z0-9]+/g,' ').trim();
  }
  function sim(a,b){if(!a||!b)return 0;if(a===b)return 2;if(a.includes(b)||b.includes(a))return 1;return 0;}

  async function query(key,type,lookup){
    const r=await fetch(API+'?'+new URLSearchParams({api_key:key,type,lookup}).toString());
    let j=null;try{j=await r.json();}catch(e){}
    if(!r.ok){
      if(r.status===401)throw new Error('Schlüssel ungültig oder nicht aktiv');
      throw new Error('Fehler '+r.status+(j&&j.error?': '+String(j.error).slice(0,80):''));
    }
    return j&&Array.isArray(j.search)?j.search:[];
  }
  function best(items,title,artist){
    const nt=norm(title),nas=String(artist||'').split(/\s*,\s*/).map(norm).filter(Boolean);
    let top=null;
    items.forEach(it=>{
      const an=norm(it.artist&&typeof it.artist==='object'?it.artist.name:it.artist);
      const st=sim(norm(it.title||it.song_title),nt),sa=Math.max(0,...nas.map(a=>sim(an,a)));
      const bpm=fold(it.tempo);
      if(st&&sa&&bpm&&(!top||st+sa>top.s))top={s:st+sa,bpm};
    });
    return top?top.bpm:null;
  }
  // Gibt die BPM zurück oder null (nicht gefunden); wirft bei Netz- oder Schlüsselfehlern.
  async function lookup(key,title,artist){
    const t=cleanTitle(title),a=String(artist||'').split(/\s*,\s*/)[0];
    if(!t)return null;
    let bpm=best(await query(key,'both',`song:${t} artist:${a}`),title,artist);
    if(bpm==null)bpm=best(await query(key,'song',t),title,artist);
    return bpm;
  }

  return {tap,resetTap,lastTap,fold,lookup,_norm:norm,_best:best};
})();
