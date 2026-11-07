// ---------- Voice: Zuhören mit Aktivierungswort "Coach", Sprachausgabe ----------
const Voice=(function(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  const FAST=['pause','resume','skip','prev','hard','easy','remaining','whatNow','how','louder','quieter','musicOn','musicOff','nextTrack','abort'];
  let handledIdx=-1;
  let rec=null,active=false,speaking=false,awaiting=0,handlers={},cfg={tts:'browser',elKey:'',elVoice:'',onStatus:null},restartTimer=null,lastHeard='';
  const WAKE=/\b(coach|couch|kotsch|koutsch|kohtsch|kutsch|coatch|cotch|koch|kosch|coach's)\b/i;

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
    rec=new SR();rec.lang='de-DE';rec.continuous=true;rec.interimResults=true;rec.maxAlternatives=3;
    rec.onresult=e=>{
      for(let i=e.resultIndex;i<e.results.length;i++){
        const res=e.results[i];
        // Alternative mit Aktivierungswort bevorzugen
        let t=res[0].transcript.trim();
        for(let a=0;a<res.length;a++){if(WAKE.test(res[a].transcript)){t=res[a].transcript.trim();break;}}
        if(!res.isFinal){
          // Schnellpfad: eindeutige lokale Befehle schon im Zwischenergebnis ausführen
          if(handledIdx===i)continue;
          const m=t.match(WAKE);if(!m)continue;
          const cmd=t.slice(m.index+m[0].length).replace(/^[,.:!?\s]+/,'').trim();
          const c=cmd?classify(cmd):null;
          if(c&&FAST.includes(c.name)){handledIdx=i;awaiting=0;status('„'+cmd+'"');handlers.onCommand&&handlers.onCommand(cmd,parseNumber(cmd));}
          continue;
        }
        if(handledIdx===i){handledIdx=-1;continue;}
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
    status(classify(cmd)?'„'+cmd+'"':'an Claude: „'+cmd+'"');
    handlers.onCommand&&handlers.onCommand(cmd,parseNumber(cmd));
  }

  // Befehle lokal zuordnen; gibt {name,n} oder null zurück
  function classify(cmd){
    const c=' '+cmd.toLowerCase().replace(/[.,!?]/g,' ').replace(/\s+/g,' ').trim()+' ';
    const n=parseNumber(c);
    const has=re=>re.test(c);
    // Feste Fragen, die lokal beantwortet werden
    if(has(/ (wie lange|wie viel zeit|restzeit|wie lang noch) /))return {name:'remaining'};
    if(has(/ (was ist dran|welche übung|was kommt|was jetzt|was mache ich jetzt) /))return {name:'whatNow'};
    if(has(/ (wie geht das|wie geht die übung|wie mache ich das|ausführung|zeig mir die ausführung) /))return {name:'how'};
    // Alle anderen Fragen und längeren Sätze gehen an Claude
    if(has(/^ (wie|was|warum|wieso|weshalb|wann|wo|wohin|welche|welcher|welches|soll|sollte|kann|könnte|muss|darf|ist|sind|hab|habe|bin|mein|meine|mir|mich|ich) /)&&!has(/^ ich bin fertig /))return null;
    if(c.trim().split(' ').length>6)return null;
    if(has(/ (fertig|geschafft|done|erledigt) /))return {name:'finish',n};
    if(has(/ (musik aus|musik stopp|musik pause|musik anhalten) /))return {name:'musicOff'};
    if(has(/ (nächstes lied|nächster song|lied weiter|song weiter|anderes lied) /))return {name:'nextTrack'};
    if(has(/ (musik an|musik weiter|musik) /))return {name:'musicOn'};
    if(has(/ (lauter) /))return {name:'louder'};
    if(has(/ (leiser) /))return {name:'quieter'};
    if(has(/ (pause|stopp|stop|anhalten|warte|moment) /))return {name:'pause'};
    if(has(/ (zu hart|zu schwer|schaff ich nicht|zu viel|zu anstrengend) /))return {name:'hard'};
    if(has(/ (zu leicht|zu einfach) /))return {name:'easy'};
    if(has(/ (leichter|weniger gewicht|gewicht runter|gewicht weniger) /))return {name:'lighter'};
    if(has(/ (schwerer|mehr gewicht|gewicht hoch|gewicht rauf) /))return {name:'heavier'};
    if(has(/ (überspringen|skip|auslassen|nächste übung) /))return {name:'skip'};
    if(has(/ (zurück) /))return {name:'prev'};
    if(has(/ (weiter|los|start|fortsetzen|go|weitermachen) /))return {name:'resume'};
    if(has(/ (plus) /)&&n!=null)return {name:'addReps',n};
    if(has(/ (minus) /)&&n!=null)return {name:'addReps',n:-n};
    if(has(/ (abbrechen|aufhören|schluss für heute) /))return {name:'abort'};
    if(n!=null&&c.trim().split(' ').length<=2)return {name:'finish',n};
    return null;
  }

  // ---- Sprachausgabe ----
  let voiceDe=null;
  function pickVoice(){
    const vs=speechSynthesis.getVoices();
    voiceDe=vs.find(v=>/de[-_]DE/i.test(v.lang)&&/natural|neural|online|premium|google/i.test(v.name))||vs.find(v=>/^de/i.test(v.lang))||null;
  }
  if(window.speechSynthesis){pickVoice();speechSynthesis.onvoiceschanged=pickVoice;}

  async function elevenAudio(text){
    const key=(cfg.elKey||'').trim(),vid=(cfg.elVoice||'').trim()||'nPczCjzI2devNBz1zQrb';
    const r=await fetch('https://api.elevenlabs.io/v1/text-to-speech/'+encodeURIComponent(vid)+'?output_format=mp3_22050_32',{method:'POST',headers:{'xi-api-key':key,'content-type':'application/json'},body:JSON.stringify({text,model_id:'eleven_multilingual_v2',voice_settings:{stability:.5,similarity_boost:.75}})});
    if(!r.ok){
      let msg='Fehler '+r.status;
      try{const j=await r.json();const d=j.detail||j;msg+=': '+(d.message||d.status||JSON.stringify(d)).slice(0,160);}catch(e){}
      if(r.status===401)msg+=' (Schlüssel ungültig oder ohne Berechtigung „Text to Speech")';
      if(r.status===404||r.status===400&&/voice/i.test(msg))msg+=' (Voice-ID prüfen)';
      throw new Error(msg);
    }
    return r.blob();
  }
  // Test aus den Einstellungen: spielt einen Satz ab und gibt eine Meldung zurück
  async function testTts(key,voiceId){
    const prev={elKey:cfg.elKey,elVoice:cfg.elVoice};cfg.elKey=key;cfg.elVoice=voiceId;
    try{const b=await elevenAudio('Hier ist dein Coach. So klinge ich im Training.');const a=new Audio(URL.createObjectURL(b));await a.play();return 'ElevenLabs funktioniert.';}
    catch(e){return 'ElevenLabs: '+e.message;}
    finally{cfg.elKey=prev.elKey;cfg.elVoice=prev.elVoice;}
  }
  function speak(text){
    if(!text)return Promise.resolve();
    return new Promise(async resolve=>{
      speaking=true;handlers.onSpeakStart&&handlers.onSpeakStart();
      try{if(rec&&active)rec.stop();}catch(e){}
      const done=()=>{speaking=false;handlers.onSpeakEnd&&handlers.onSpeakEnd();if(active){clearTimeout(restartTimer);restartTimer=setTimeout(()=>{try{rec.start();}catch(e){}},400);}resolve();};
      if(cfg.tts==='elevenlabs'&&cfg.elKey){
        try{
          const blob=await elevenAudio(text);
          const a=new Audio(URL.createObjectURL(blob));a.onended=done;a.onerror=done;
          try{await a.play();return;}catch(e){status('ElevenLabs: Wiedergabe blockiert ('+e.message+'), Browser-Stimme');}
        }catch(e){status('ElevenLabs: '+e.message+' – Browser-Stimme');}
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
  return {testTts,supported,start,stop,speak,classify,parseNumber,configure,on,isActive:()=>active,isSpeaking:()=>speaking,lastHeard:()=>lastHeard};
})();
