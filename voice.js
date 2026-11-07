// ---------- Voice: Zuhören mit Aktivierungswort "Coach", Sprachausgabe ----------
const Voice=(function(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  let rec=null,active=false,speaking=false,awaiting=0,handlers={},cfg={tts:'browser',elKey:'',elVoice:'',onStatus:null},restartTimer=null,lastHeard='';
  const WAKE=/\b(coach|couch|kotsch|koutsch|kohtsch|kutsch|coatch)\b/i;

  const NUM={null:0,'null':0,'eins':1,'ein':1,'eine':1,'zwei':2,'zwo':2,'drei':3,'vier':4,'fünf':5,'sechs':6,'sieben':7,'acht':8,'neun':9,'zehn':10,'elf':11,'zwölf':12,'dreizehn':13,'vierzehn':14,'fünfzehn':15,'sechzehn':16,'siebzehn':17,'achtzehn':18,'neunzehn':19,'zwanzig':20,'dreißig':30,'vierzig':40,'fünfzig':50};
  function parseNumber(t){
    const d=t.match(/\d+/);if(d)return parseInt(d[0],10);
    const w=t.toLowerCase().replace(/ß/g,'ß');
    // einundzwanzig etc.
    const m=w.match(/\b(ein|zwei|drei|vier|fünf|sechs|sieben|acht|neun)und(zwanzig|dreißig|vierzig|fünfzig)\b/);
    if(m)return NUM[m[1]]+NUM[m[2]];
    for(const k of Object.keys(NUM).sort((a,b)=>b.length-a.length)){if(k&&new RegExp('\\b'+k+'\\b').test(w))return NUM[k];}
    return null;
  }

  function supported(){return !!SR;}
  function status(s){cfg.onStatus&&cfg.onStatus(s);}

  function start(){
    if(!SR||active)return;
    active=true;
    rec=new SR();rec.lang='de-DE';rec.continuous=true;rec.interimResults=false;rec.maxAlternatives=1;
    rec.onresult=e=>{
      for(let i=e.resultIndex;i<e.results.length;i++){
        if(!e.results[i].isFinal)continue;
        const t=e.results[i][0].transcript.trim();
        lastHeard=t;
        handle(t);
      }
    };
    rec.onerror=e=>{ if(e.error==='not-allowed'){active=false;status('Mikrofon nicht erlaubt');} };
    rec.onend=()=>{ if(active&&!speaking){clearTimeout(restartTimer);restartTimer=setTimeout(()=>{try{rec.start();}catch(err){}},250);} };
    try{rec.start();status('hört zu');}catch(err){status('Start fehlgeschlagen');}
  }
  function stop(){active=false;clearTimeout(restartTimer);try{rec&&rec.stop();}catch(e){}status('aus');}

  function handle(text){
    if(speaking)return;
    let cmd=null;
    const m=text.match(WAKE);
    if(m){
      cmd=text.slice(m.index+m[0].length).replace(/^[,.:!?\s]+/,'').trim();
      if(!cmd){awaiting=Date.now()+7000;status('ja?');handlers.onWake&&handlers.onWake();return;}
    } else if(awaiting&&Date.now()<awaiting){cmd=text.trim();}
    else return;
    awaiting=0;
    status('„'+cmd+'"');
    handlers.onCommand&&handlers.onCommand(cmd,parseNumber(cmd));
  }

  // Befehle lokal zuordnen; gibt {name,n} oder null zurück
  function classify(cmd){
    const c=cmd.toLowerCase();
    const n=parseNumber(c);
    if(/\b(fertig|geschafft|done|erledigt)\b/.test(c))return {name:'finish',n};
    // Musikbefehle vor pause/weiter prüfen, sonst greifen "Musik pause" oder "Lied weiter" falsch
    if(/\b(nächstes lied|nächster song|lied weiter|song weiter)\b/.test(c))return {name:'nextTrack'};
    if(/\b(musik aus|musik stopp|musik pause)\b/.test(c))return {name:'musicOff'};
    if(/\b(musik an|musik weiter)\b/.test(c))return {name:'musicOn'};
    if(/\b(pause|stopp|stop|anhalten|warte)\b/.test(c))return {name:'pause'};
    if(/\b(weiter|los|start|fortsetzen|go)\b/.test(c))return {name:'resume'};
    if(/\b(zu hart|zu schwer|schaff ich nicht|zu viel|zu anstrengend)\b/.test(c))return {name:'hard'};
    if(/\b(zu leicht|zu einfach)\b/.test(c))return {name:'easy'};
    if(/\b(leichter|weniger gewicht|runter)\b/.test(c))return {name:'lighter'};
    if(/\b(schwerer|mehr gewicht|hoch)\b/.test(c))return {name:'heavier'};
    // \b greift nicht vor Umlauten (ASCII-Wortgrenze), daher "überspringen" separat
    if(/(^|\s)überspringen\b/.test(c)||/\b(skip|nächste|weiter zur nächsten|auslassen)\b/.test(c))return {name:'skip'};
    if(/\b(zurück)\b/.test(c))return {name:'prev'};
    if(/\b(plus)\b/.test(c)&&n!=null)return {name:'addReps',n};
    if(/\b(minus)\b/.test(c)&&n!=null)return {name:'addReps',n:-n};
    if(/\b(lauter)\b/.test(c))return {name:'louder'};
    if(/\b(leiser)\b/.test(c))return {name:'quieter'};
    if(/\bmusik\b/.test(c))return {name:'musicOn'};
    if(/\b(wie lange|wie viel zeit|restzeit)\b/.test(c))return {name:'remaining'};
    if(/\b(was ist dran|welche übung|was kommt|was jetzt)\b/.test(c))return {name:'whatNow'};
    if(/\b(wie geht|wie mache ich|ausführung|technik|worauf)\b/.test(c))return {name:'how'};
    if(/\b(abbrechen|aufhören|schluss für heute)\b/.test(c))return {name:'abort'};
    if(/^\d+$/.test(c.trim())||(n!=null&&c.trim().split(/\s+/).length<=2))return {name:'finish',n};
    return null;
  }

  // ---- Sprachausgabe ----
  let voiceDe=null;
  function pickVoice(){
    const vs=speechSynthesis.getVoices();
    voiceDe=vs.find(v=>/de[-_]DE/i.test(v.lang)&&/natural|neural|online|premium|google/i.test(v.name))||vs.find(v=>/^de/i.test(v.lang))||null;
  }
  if(window.speechSynthesis){pickVoice();speechSynthesis.onvoiceschanged=pickVoice;}

  function speak(text){
    if(!text)return Promise.resolve();
    return new Promise(async resolve=>{
      speaking=true;handlers.onSpeakStart&&handlers.onSpeakStart();
      try{if(rec&&active)rec.stop();}catch(e){}
      const done=()=>{speaking=false;handlers.onSpeakEnd&&handlers.onSpeakEnd();if(active){clearTimeout(restartTimer);restartTimer=setTimeout(()=>{try{rec.start();}catch(e){}},400);}resolve();};
      if(cfg.tts==='elevenlabs'&&cfg.elKey){
        try{
          const vid=cfg.elVoice||'21m00Tcm4TlvDq8ikWAM';
          const r=await fetch('https://api.elevenlabs.io/v1/text-to-speech/'+vid+'?output_format=mp3_22050_32',{method:'POST',headers:{'xi-api-key':cfg.elKey,'content-type':'application/json'},body:JSON.stringify({text,model_id:'eleven_multilingual_v2',voice_settings:{stability:.5,similarity_boost:.75}})});
          if(r.ok){const b=await r.blob();const a=new Audio(URL.createObjectURL(b));a.onended=done;a.onerror=done;a.play().catch(done);return;}
        }catch(e){}
      }
      if(!window.speechSynthesis){done();return;}
      try{
        speechSynthesis.cancel();
        const u=new SpeechSynthesisUtterance(text);u.lang='de-DE';if(voiceDe)u.voice=voiceDe;u.rate=1.05;
        u.onend=done;u.onerror=done;speechSynthesis.speak(u);
        setTimeout(()=>{if(speaking)done();},Math.min(20000,2500+text.length*90));
      }catch(e){done();}
    });
  }

  function configure(c){cfg=Object.assign(cfg,c||{});}
  function on(h){handlers=Object.assign(handlers,h||{});}
  return {supported,start,stop,speak,classify,parseNumber,configure,on,isActive:()=>active,isSpeaking:()=>speaking,lastHeard:()=>lastHeard};
})();
