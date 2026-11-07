// ---------- Music: Spotify Web Playback SDK + Web API (PKCE, ohne Server) ----------
const Music=(function(){
  const SCOPES='streaming user-read-email user-read-private user-modify-playback-state user-read-playback-state playlist-read-private playlist-read-collaborative';
  let cfg={clientId:'',baseVolume:.8,onTokens:null,onState:null,onTrackEnd:null,onReady:null};
  let tok={access:'',refresh:'',exp:0};
  let player=null,deviceId=null,ready=false,phaseVol=1,ducked=false,lastTrackId=null,lastPos=0,lastPaused=true,trackEndFired=false,curDur=0;

  function configure(c){cfg=Object.assign(cfg,c||{});}
  function setTokens(t){if(t)tok=Object.assign(tok,t);}
  function connected(){return !!tok.refresh||(!!tok.access&&tok.exp>Date.now());}
  function redirectUri(){return location.origin+location.pathname;}

  // ---- PKCE ----
  function rnd(n){const a=new Uint8Array(n);crypto.getRandomValues(a);return Array.from(a,b=>('0'+(b%36).toString(36)).slice(-1)).join('');}
  async function sha256b64(s){const d=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s));return btoa(String.fromCharCode(...new Uint8Array(d))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');}
  async function login(){
    if(!cfg.clientId)throw new Error('Keine Spotify Client-ID');
    const verifier=rnd(64);sessionStorage.setItem('sp_verifier',verifier);
    const challenge=await sha256b64(verifier);
    const u=new URL('https://accounts.spotify.com/authorize');
    u.search=new URLSearchParams({client_id:cfg.clientId,response_type:'code',redirect_uri:redirectUri(),scope:SCOPES,code_challenge_method:'S256',code_challenge:challenge}).toString();
    location.href=u.toString();
  }
  async function handleRedirect(){
    const p=new URLSearchParams(location.search);const code=p.get('code');
    if(!code)return false;
    const verifier=sessionStorage.getItem('sp_verifier')||'';
    const r=await fetch('https://accounts.spotify.com/api/token',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'authorization_code',code,redirect_uri:redirectUri(),client_id:cfg.clientId,code_verifier:verifier})});
    history.replaceState({},'',location.pathname+location.hash);
    if(!r.ok)throw new Error('Spotify-Login fehlgeschlagen ('+r.status+')');
    const j=await r.json();
    tok={access:j.access_token,refresh:j.refresh_token||tok.refresh,exp:Date.now()+(j.expires_in-60)*1000};
    cfg.onTokens&&cfg.onTokens(tok);
    return true;
  }
  async function token(){
    if(tok.access&&tok.exp>Date.now())return tok.access;
    if(!tok.refresh)throw new Error('Nicht bei Spotify angemeldet');
    const r=await fetch('https://accounts.spotify.com/api/token',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'refresh_token',refresh_token:tok.refresh,client_id:cfg.clientId})});
    if(!r.ok){tok={access:'',refresh:'',exp:0};cfg.onTokens&&cfg.onTokens(tok);throw new Error('Spotify-Sitzung abgelaufen, bitte neu anmelden');}
    const j=await r.json();
    tok={access:j.access_token,refresh:j.refresh_token||tok.refresh,exp:Date.now()+(j.expires_in-60)*1000};
    cfg.onTokens&&cfg.onTokens(tok);
    return tok.access;
  }
  function logout(){tok={access:'',refresh:'',exp:0};cfg.onTokens&&cfg.onTokens(tok);try{player&&player.disconnect();}catch(e){}player=null;ready=false;deviceId=null;}

  async function api(path,method,body){
    const t=await token();
    const r=await fetch('https://api.spotify.com/v1'+path,{method:method||'GET',headers:Object.assign({'authorization':'Bearer '+t},body?{'content-type':'application/json'}:{}),body:body?JSON.stringify(body):undefined});
    if(r.status===204||r.status===202)return null;
    if(!r.ok){const e=await r.text().catch(()=>'');throw new Error('Spotify '+r.status+(e?': '+e.slice(0,120):''));}
    const ct=r.headers.get('content-type')||'';return ct.includes('json')?r.json():null;
  }

  // ---- Player ----
  function loadSdk(){
    return new Promise((resolve,reject)=>{
      if(window.Spotify)return resolve();
      window.onSpotifyWebPlaybackSDKReady=()=>resolve();
      const s=document.createElement('script');s.src='https://sdk.scdn.co/spotify-player.js';s.onerror=()=>reject(new Error('Spotify-SDK nicht ladbar'));document.head.appendChild(s);
      setTimeout(()=>{if(!window.Spotify)reject(new Error('Spotify-SDK Zeitüberschreitung'));},15000);
    });
  }
  async function connect(){
    if(ready)return true;
    if(!connected())return false;
    await loadSdk();
    player=new Spotify.Player({name:'HIIT Kraft 30',getOAuthToken:cb=>{token().then(cb).catch(()=>cb(''));},volume:cfg.baseVolume});
    return new Promise((resolve)=>{
      player.addListener('ready',({device_id})=>{deviceId=device_id;ready=true;cfg.onReady&&cfg.onReady(true);resolve(true);});
      player.addListener('not_ready',()=>{ready=false;cfg.onReady&&cfg.onReady(false);});
      player.addListener('initialization_error',()=>resolve(false));
      player.addListener('authentication_error',()=>resolve(false));
      player.addListener('account_error',()=>resolve(false));
      player.addListener('player_state_changed',st=>{
        if(!st)return;
        const tr=st.track_window&&st.track_window.current_track;
        const id=tr?tr.id:null;
        if(id!==lastTrackId){lastTrackId=id;trackEndFired=false;}
        curDur=st.duration;lastPos=st.position;lastPaused=st.paused;
        // Liedende: Position 0, pausiert, vorher nahe Ende
        if(st.paused&&st.position===0&&!trackEndFired&&curDur>0){trackEndFired=true;cfg.onTrackEnd&&cfg.onTrackEnd(id);}
        cfg.onState&&cfg.onState({id,name:tr?tr.name:'',artist:tr&&tr.artists?tr.artists.map(a=>a.name).join(', '):'',duration:st.duration,position:st.position,paused:st.paused});
      });
      player.connect().then(ok=>{if(!ok)resolve(false);});
      setTimeout(()=>{if(!ready)resolve(false);},12000);
    });
  }
  async function transferHere(){if(!deviceId)return;await api('/me/player','PUT',{device_ids:[deviceId],play:false}).catch(()=>{});}

  async function playContext(uri){await transferHere();await api('/me/player/play?device_id='+deviceId,'PUT',{context_uri:uri});applyVolume();}
  async function playTracks(uris){await transferHere();await api('/me/player/play?device_id='+deviceId,'PUT',{uris});applyVolume();}
  async function next(){if(!player)return;await player.nextTrack();}
  async function pause(){if(player)await player.pause();}
  async function resume(){if(player)await player.resume();}
  async function state(){if(!player)return null;const st=await player.getCurrentState();if(!st)return null;const tr=st.track_window.current_track;return {id:tr.id,name:tr.name,artist:tr.artists.map(a=>a.name).join(', '),duration:st.duration,position:st.position,paused:st.paused};}

  // ---- Lautstärke: Basis × Phase × Ducking ----
  function applyVolume(){if(!player)return;const v=Math.max(0,Math.min(1,cfg.baseVolume*phaseVol*(ducked?.25:1)));player.setVolume(v).catch(()=>{});}
  function setPhase(p){phaseVol=p==='work'?1:p==='rest'?.65:p==='cool'?.5:1;applyVolume();}
  function duck(on){ducked=!!on;applyVolume();}
  function setBase(v){cfg.baseVolume=Math.max(0,Math.min(1,v));applyVolume();}
  function baseVolume(){return cfg.baseVolume;}

  // ---- Bibliothek ----
  async function playlists(){const j=await api('/me/playlists?limit=50');return (j.items||[]).map(p=>({id:p.id,uri:p.uri,name:p.name,tracks:p.tracks?p.tracks.total:0}));}
  async function search(q){const j=await api('/search?type=track&limit=8&q='+encodeURIComponent(q));return ((j.tracks&&j.tracks.items)||[]).map(t=>({id:t.id,uri:t.uri,name:t.name,artist:t.artists.map(a=>a.name).join(', '),duration:t.duration_ms}));}

  return {configure,setTokens,connected,login,handleRedirect,logout,connect,isReady:()=>ready,playContext,playTracks,next,pause,resume,state,setPhase,duck,setBase,baseVolume,playlists,search,redirectUri};
})();
