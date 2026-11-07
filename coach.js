// ---------- Coach: Claude-Anbindung direkt aus dem Browser ----------
// Key und Modell kommen aus den Einstellungen der App (localStorage). Ohne Key greifen lokale Regeln.
const Coach=(function(){
  const API='https://api.anthropic.com/v1/messages';
  let cfg={apiKey:'',model:'claude-sonnet-5-5',fastModel:'claude-haiku-5-5'};
  function configure(c){cfg=Object.assign(cfg,c||{});}
  function ready(){return !!(cfg.apiKey&&cfg.apiKey.length>10);}

  const SYSTEM=`Du bist der Trainings-Coach in der App "HIIT Kraft 30". Nutzer: Mann, 34, 180 cm, 82 kg, früher viel Sport, Wiedereinsteiger, trainiert zu Hause im Wohnzimmer mit zwei verstellbaren Kurzhanteln (max. 15 kg je Hantel), 3x pro Woche, ca. 30 Minuten. Ziele: Muskelaufbau, schnell messbare Fortschritte, Motivation. Er will keine Standard-Ausreden und kein Aufgeben, sondern konkrete Anpassungen.
Plan: Tag A und Tag B, je 3 Übungspaare, 2-3 Runden, Sätze nach Wiederholungsbereich bis zur angegebenen Reserve, 25 s Wechsel, Finisher-AMRAP (5 Thruster + 5 Burpees). Progression: erst Wiederholungen, dann Gewicht +2,5 kg, bei 15 kg dann Stufen (3 s exzentrisch, 1,5er, Rest-Pause).
Sicherheit: Bei Schmerz (stechend, Gelenk, Wirbelsäule) immer die Übung tauschen oder streichen, nie durchziehen lassen. Bei Rückenbeschwerden einbeiniges Kreuzheben und vorgebeugtes Rudern vermeiden (Alternative: Hüftbrücke, einarmiges Rudern abgestützt, Dead Bug).
Antworte knapp, direkt, auf Deutsch, ohne Floskeln, ohne Emojis. "say"-Texte werden vorgelesen: maximal 2 kurze Sätze, keine Listen, keine Zahlen in Klammern.
Gib deine Antwort immer über das Tool "antwort" zurück.`;

  // Antwort wird über einen erzwungenen Tool-Aufruf mit festem Schema geholt, damit immer gültiges JSON kommt.
  const S_NUM={type:'number'},S_STR={type:'string'},S_BOOL={type:'boolean'};
  const SCHEMAS={
    test:{type:'object',properties:{ok:S_BOOL,say:S_STR},required:['ok']},
    plan:{type:'object',properties:{say:S_STR,rounds:S_NUM,weightDelta:S_NUM,rirShift:S_NUM,finisher:S_BOOL,finisherSec:S_NUM,swaps:{type:'object',additionalProperties:S_STR},skipPairs:{type:'array',items:S_NUM}},required:['say']},
    ask:{type:'object',properties:{say:S_STR,actions:{type:'array',items:{type:'object',properties:{type:S_STR,ex:S_STR,delta:S_NUM,n:S_NUM,on:S_BOOL,reason:S_STR},required:['type']}}},required:['say','actions']},
    summary:{type:'object',properties:{say:S_STR,next:{type:'object',properties:{weights:{type:'object',additionalProperties:S_NUM},note:S_STR}}},required:['say']},
    progression:{type:'object',properties:{say:S_STR,changes:{type:'object',additionalProperties:{type:'object',properties:{weight:S_NUM,stage:S_NUM}}},note:S_STR},required:['say']}
  };
  let lastRaw='';
  async function call(messages,maxTokens,kind,model){
    if(!ready())throw new Error('Kein API-Schlüssel');
    const body={model:model||cfg.model||'claude-sonnet-5-5',max_tokens:Math.max(maxTokens||0,1200),system:SYSTEM,messages};
    if(kind&&SCHEMAS[kind]){
      body.tools=[{name:'antwort',description:'Gibt die Antwort des Coaches strukturiert zurück.',input_schema:SCHEMAS[kind]}];
      body.tool_choice={type:'auto'};
    }
    const r=await fetch(API,{method:'POST',headers:{'content-type':'application/json','x-api-key':cfg.apiKey,'anthropic-version':'2023-06-01','anthropic-dangerous-direct-browser-access':'true'},body:JSON.stringify(body)});
    if(!r.ok){const t=await r.text().catch(()=>'');throw new Error('API '+r.status+(t?': '+t.slice(0,160):''));}
    const j=await r.json();
    const tu=(j.content||[]).find(c=>c.type==='tool_use');
    if(tu&&tu.input&&typeof tu.input==='object'){lastRaw=JSON.stringify(tu.input);return tu.input;}
    const txt=(j.content||[]).map(c=>c.text||'').join('');
    lastRaw=txt;
    if(j.stop_reason==='max_tokens')throw new Error('Antwort abgeschnitten');
    return parseJSON(txt);
  }
  function parseJSON(txt){
    const m=txt.match(/\{[\s\S]*\}/);
    if(!m){console.warn('Coach-Antwort ohne JSON:',txt);throw new Error('Keine JSON-Antwort');}
    return JSON.parse(m[0]);
  }
  async function test(){
    const j=await call([{role:'user',content:'Verbindungstest. Rufe das Tool mit ok=true und say="Verbindung steht." auf.'}],200,'test');
    return !!j.ok;
  }

  // ---- 1) Plananpassung nach Check-in ----
  // ctx: {day,week,plan,checkin,lastSessions,exercises,weights,notes}
  // Antwort: {say, rounds, weightDelta, rirShift, finisher, finisherSec, swaps:{orig:neu}, skipPairs:[n]}
  async function planAdjust(ctx){
    const prompt=`Check-in vor der Einheit und aktueller Plan. Passe den Plan an den Zustand an und begründe in einem Satz.
Regeln: rounds 2 oder 3. weightDelta nur -5, -2.5 oder 0 (gilt für alle Hantelübungen). rirShift 0 oder 1 (mehr Reserve). finisher true/false, finisherSec 120 oder 180. swaps nur aus den erlaubten Varianten (Feld "lighter" je Übung). skipPairs: Paarnummern 1-3, die entfallen (nur bei Zeitmangel oder Beschwerden). Bei Zeit 15 min: rounds 2 und finisher false. Bei 20 min: rounds 2. Bei starkem Muskelkater oder Energie unter 3: weightDelta -2.5 und rirShift 1. Wenn alles gut ist: nichts ändern und kurz motivieren.
Antwortformat: {"say":"...","rounds":3,"weightDelta":0,"rirShift":0,"finisher":true,"finisherSec":180,"swaps":{},"skipPairs":[]}
Daten:
${JSON.stringify(ctx)}`;
    const j=await call([{role:'user',content:prompt}],500,'plan');
    return sanitizeAdjust(j);
  }
  function sanitizeAdjust(j){
    const out={say:String(j.say||'').slice(0,300)};
    if([2,3].includes(+j.rounds))out.rounds=+j.rounds;
    if([-5,-2.5,0].includes(+j.weightDelta))out.weightDelta=+j.weightDelta;
    if([0,1].includes(+j.rirShift))out.rirShift=+j.rirShift;
    if(typeof j.finisher==='boolean')out.finisher=j.finisher;
    if([120,180].includes(+j.finisherSec))out.finisherSec=+j.finisherSec;
    out.swaps=(j.swaps&&typeof j.swaps==='object')?j.swaps:{};
    out.skipPairs=Array.isArray(j.skipPairs)?j.skipPairs.map(Number).filter(n=>n>=1&&n<=3):[];
    return out;
  }

  // ---- 2) Freitext während des Trainings ----
  // Antwort: {say, actions:[{type:'weight',ex,delta}|{type:'variant',ex}|{type:'skipSet'}|{type:'skipPair'}|{type:'rounds',n}|{type:'finisher',on}|{type:'pause'}|{type:'resume'}|{type:'abort',reason}]}
  async function ask(text,ctx){
    const prompt=`Der Nutzer sagt während des Trainings: "${text}"
Aktueller Zustand: ${JSON.stringify(ctx)}
Antworte kurz (max. 2 Sätze) über das Tool mit {"say":"...","actions":[...]}. Erlaubte actions: {"type":"weight","ex":"<key>","delta":-2.5|2.5}, {"type":"variant","ex":"<key>"} (wechselt auf die leichtere Variante), {"type":"skipSet"}, {"type":"skipPair"}, {"type":"rounds","n":2|3}, {"type":"finisher","on":true|false}, {"type":"pause"}, {"type":"resume"}, {"type":"abort","reason":"schmerz"|"zeit"|"zu_hart"|"sonstiges"}. Leeres Array, wenn nur eine Antwort nötig ist (z. B. Technikfrage). Bei Schmerz in Gelenk oder Rücken: variant oder skipSet, nie weitermachen lassen. Keine Aktion, die der Nutzer nicht sinngemäß gewollt hat.`;
    let j;
    try{j=await call([{role:'user',content:prompt}],500,'ask',cfg.fastModel||cfg.model);}
    catch(e){
      // Antwort ohne Format: Text trotzdem vorlesen, keine Aktionen
      if(/JSON/.test(e.message)&&lastRaw)return {say:lastRaw.replace(/\s+/g,' ').trim().slice(0,400),actions:[]};
      // schnelles Modell nicht verfügbar: mit dem Hauptmodell erneut
      if(/API 4(00|04)/.test(e.message)&&cfg.fastModel&&cfg.fastModel!==cfg.model){j=await call([{role:'user',content:prompt}],500,'ask',cfg.model);}
      else throw e;
    }
    const acts=Array.isArray(j.actions)?j.actions.filter(a=>a&&typeof a.type==='string').slice(0,4):[];
    return {say:String(j.say||'').slice(0,400),actions:acts};
  }

  // ---- 3) Auswertung nach der Einheit ----
  // Antwort: {say, next:{weights:{ex:kg}, note:"..."}}
  async function summary(session,history){
    const prompt=`Einheit beendet. Werte kurz aus (2 Sätze, konkret: was lief, was nächstes Mal anders) und schlage für das nächste Mal Gewichte vor, nur wo sich etwas ändern soll (2,5-kg-Schritte, max 15).
Antwortformat: {"say":"...","next":{"weights":{},"note":"ein Satz für den Startbildschirm der nächsten Einheit"}}
Einheit: ${JSON.stringify(session)}
Letzte Einheiten (kompakt): ${JSON.stringify(history)}`;
    const j=await call([{role:'user',content:prompt}],500,'summary');
    const w={};if(j.next&&j.next.weights&&typeof j.next.weights==='object')for(const k in j.next.weights){const v=+j.next.weights[k];if(v>=0&&v<=15&&Math.abs(v*2-Math.round(v*2))<1e-9)w[k]=v;}
    return {say:String(j.say||'').slice(0,400),next:{weights:w,note:String((j.next&&j.next.note)||'').slice(0,240)}};
  }

  // ---- 4) Progressionscheck alle 12 Einheiten ----
  // Antwort: {say, changes:{ex:{weight,stage}}, note}
  async function progression(sessions,stages,weights){
    const prompt=`Progressionscheck nach ${sessions.length} Einheiten. Analysiere Trend je Übung (Wiederholungen, Gewicht, Rückmeldungen leicht/passt/zu hart, Abbrüche). Schlage je Übung vor: Gewicht (2,5-kg-Schritte, max 15) und/oder Stufe (0 Standard, 1 Tempo, 2 Eineinhalber, 3 Rest-Pause). Nur Übungen mit Änderung. Dazu 2-3 Sätze Einordnung.
Antwortformat: {"say":"...","changes":{"<ex>":{"weight":12.5,"stage":1}},"note":"..."}
Stufen jetzt: ${JSON.stringify(stages)} Gewichte jetzt: ${JSON.stringify(weights)}
Einheiten: ${JSON.stringify(sessions)}`;
    const j=await call([{role:'user',content:prompt}],900,'progression');
    const ch={};if(j.changes&&typeof j.changes==='object')for(const k in j.changes){const c=j.changes[k]||{};const o={};if(c.weight!=null&&+c.weight>=0&&+c.weight<=15)o.weight=+c.weight;if(c.stage!=null&&[0,1,2,3].includes(+c.stage))o.stage=+c.stage;if(Object.keys(o).length)ch[k]=o;}
    return {say:String(j.say||'').slice(0,600),changes:ch,note:String(j.note||'').slice(0,240)};
  }

  // ---- Lokale Regeln ohne Key ----
  function localAdjust(ci){
    const out={say:'',rounds:null,weightDelta:0,rirShift:0,finisher:null,finisherSec:null,swaps:{},skipPairs:[]};
    const msgs=[];
    if(ci.time===15){out.rounds=2;out.finisher=false;msgs.push('Kurze Einheit: 2 Runden, kein Finisher.');}
    else if(ci.time===20){out.rounds=2;msgs.push('20 Minuten: 2 Runden pro Paar.');}
    if(ci.sore>=2||ci.energy<=2){out.weightDelta=-2.5;out.rirShift=1;msgs.push('Heute 2,5 kg weniger und mehr Reserve.');}
    if(ci.sleep<=2&&out.finisher!==false){out.finisherSec=120;msgs.push('Finisher nur 2 Minuten.');}
    out.say=msgs.length?msgs.join(' '):'Alles im grünen Bereich, Plan wie vorgesehen.';
    return out;
  }
  function localAnswer(text){
    return {say:'Dafür brauche ich den API-Schlüssel in den Einstellungen. Feste Befehle gehen auch so: fertig, Pause, weiter, zu hart, leichter, überspringen.',actions:[]};
  }

  return {lastRaw:()=>lastRaw,configure,ready,test,planAdjust,ask,summary,progression,localAdjust,localAnswer};
})();
