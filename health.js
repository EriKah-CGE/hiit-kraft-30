// ---------- Health: Schlaf- und Ruhewerte vom eigenen Cloudflare Worker ----------
// Der iPhone-Kurzbefehl schickt die Werte per POST an den Worker, die App liest sie hier mit demselben Token.
const Health=(function(){
  let cfg={url:'',token:''};
  function configure(c){cfg=Object.assign(cfg,c||{});}
  function ready(){return !!(cfg.url&&cfg.token);}
  function base(){return cfg.url.trim().replace(/\/+$/,'').replace(/\/health$/,'');}
  async function get(path){
    if(!ready())throw new Error('Health-Server-URL oder Token fehlt');
    let r;
    try{r=await fetch(base()+path,{headers:{authorization:'Bearer '+cfg.token.trim()},cache:'no-store'});}
    catch(e){throw new Error('Server nicht erreichbar');}
    let j=null;try{j=await r.json();}catch(e){}
    if(!r.ok)throw new Error((r.status===401?'Token falsch':'Fehler '+r.status)+(j&&j.error&&r.status!==401?': '+j.error:''));
    return j;
  }
  async function latest(){const j=await get('/health/latest');return j&&j.latest||null;}
  async function days(n){const j=await get('/health?days='+(n||8));return j&&Array.isArray(j.days)?j.days:[];}

  // Auswertung für Startbildschirm und Coach
  const ymd=d=>{const x=new Date(d);return x.getFullYear()+'-'+String(x.getMonth()+1).padStart(2,'0')+'-'+String(x.getDate()).padStart(2,'0');};
  function mean(a){a=a.filter(v=>typeof v==='number'&&isFinite(v));return a.length?a.reduce((x,y)=>x+y,0)/a.length:null;}
  // Datensatz von heute oder gestern plus Mittel der 7 Tage davor
  function summarize(list,now){
    now=now||Date.now();
    const today=ymd(now),yest=ymd(now-864e5);
    const sorted=[...(list||[])].filter(d=>d&&d.date).sort((a,b)=>a.date<b.date?-1:1);
    const last=sorted.length?sorted[sorted.length-1]:null;
    if(!last||(last.date!==today&&last.date!==yest))return null;
    const prev=sorted.filter(d=>d.date<last.date).slice(-7);
    return {last,avg7:{restingHr:mean(prev.map(d=>d.restingHr)),hrv:mean(prev.map(d=>d.hrv)),sleepHours:mean(prev.map(d=>d.sleepHours)),n:prev.length}};
  }
  // Schlaf-Skala für den Check-in
  function sleepScale(h){if(typeof h!=='number')return null;return h<5?1:h<6?2:h<7?3:h<8?4:5;}
  return {configure,ready,latest,days,summarize,sleepScale};
})();
