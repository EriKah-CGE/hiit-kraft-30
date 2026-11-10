// ---------- Figur: realistisches 3D-Modell (models/*.glb) mit Muskelfärbung und Beschriftung ----------
// Braucht THREE r128 mit THREE.GLTFLoader und THREE.DRACOLoader, exercises-anatomy.js (MUSCLES, ANATOMY).
// Rückfall: rig.js (Rig), wenn das Modell nicht lädt; der Status geht sichtbar an onStatus.
const Figure=(function(){
  const MODELS={man:'models/man.glb',woman:'models/woman.glb'};
  const DRACO='https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/libs/draco/';
  const ALIAS={probe:'splitsquat'};
  const VIEW_EL={stand:4,lying:16};
  // Gelenke des Rigs für Formhinweise
  const LM={hip:'thigh',knee:'calf',ankle:'foot',toe:'ball',shoulder:'upperarm',elbow:'lowerarm',wrist:'hand',
    spine_lower:'spine_01',spine_upper:'spine_03',neck:'neck_01',head:'head',pelvis:'pelvis'};

  const css=n=>{try{const v=getComputedStyle(document.documentElement).getPropertyValue(n).trim();return v||null;}catch(e){return null;}};
  const col=(n,d)=>new THREE.Color(css(n)||d);

  let root=null,host=null,renderer=null,scene=null,camera=null,svg=null,lab=null,ro=null,raf=0,floorLine=null;
  let modelKey='man',cur=null,exKey=null,view='side',slow=false,cycle=null,labelsOn=true;
  let status={mode:'loading',error:null},onSt=[];
  const cache={};          // modelKey -> Promise<model>
  let M=null;              // aktives Modell
  let fb=null;             // Rückfall-Container für Rig
  let lastT=0,camAnim=null,layout=null;

  function setStatus(mode,error){status={mode,error:error||null};onSt.forEach(f=>{try{f(status);}catch(e){}});}

  // ---------- Shader ----------
  const VS=`
    #include <common>
    #include <skinning_pars_vertex>
    varying vec3 vN; varying vec3 vC;
    void main(){
      #include <skinbase_vertex>
      #include <beginnormal_vertex>
      #include <skinnormal_vertex>
      #include <defaultnormal_vertex>
      #include <begin_vertex>
      #include <skinning_vertex>
      #include <project_vertex>
      vN=normalize(transformedNormal);
      #ifdef USE_COLOR
        vC=color.rgb;
      #else
        vC=vec3(0.0);
      #endif
    }`;
  const FS=`
    uniform vec3 uSkin,uActive,uSupport,uShorts,uTop,uEye,uHair;
    uniform float uL[16]; uniform float uR[16];
    varying vec3 vN; varying vec3 vC;
    void main(){
      float id=floor(vC.r*20.0+0.5), cl=floor(vC.g*10.0+0.5), sd=vC.b;
      vec3 base=uSkin;
      if(cl>0.5&&cl<1.5)base=uShorts; else if(cl>1.5&&cl<2.5)base=uTop; else if(cl>2.5&&cl<3.5)base=uEye; else if(cl>3.5)base=uHair;
      float st=0.0;
      for(int i=1;i<16;i++){
        if(abs(float(i)-id)<0.5){
          float l=uL[i], r=uR[i];
          st = sd>0.75 ? l : (sd<0.25 ? r : max(l,r));
        }
      }
      if(st>1.5)base=uActive; else if(st>0.5)base=uSupport;
      vec3 n=normalize(vN);
      float k=0.70+0.22*max(dot(n,normalize(vec3(-0.35,0.55,0.75))),0.0)+0.08*max(dot(n,normalize(vec3(0.6,0.2,0.5))),0.0);
      k=mix(k,1.0,0.12);
      gl_FragColor=vec4(base*k,1.0);
    }`;
  const VS_OUT=`
    #include <common>
    #include <skinning_pars_vertex>
    uniform float uW; uniform vec2 uRes;
    void main(){
      #include <skinbase_vertex>
      #include <beginnormal_vertex>
      #include <skinnormal_vertex>
      #include <defaultnormal_vertex>
      #include <begin_vertex>
      #include <skinning_vertex>
      #include <project_vertex>
      vec3 nn=normalize(transformedNormal);
      #ifdef FLIP_SIDED
        nn=-nn;
      #endif
      vec4 cn=projectionMatrix*vec4(nn,0.0);
      vec2 d=normalize(cn.xy+1e-6);
      gl_Position.xy+=d*uW*2.0/uRes*gl_Position.w;
    }`;
  const FS_FLAT=`uniform vec3 uC; void main(){gl_FragColor=vec4(uC,1.0);}`;
  const VS_SOLID=`varying vec3 vN; void main(){vN=normalize(normalMatrix*normal);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`;
  const FS_SOLID=`uniform vec3 uC; varying vec3 vN; void main(){float k=0.72+0.28*max(dot(normalize(vN),normalize(vec3(-0.35,0.55,0.75))),0.0);gl_FragColor=vec4(uC*k,1.0);}`;

  function bodyMat(){
    const u={uSkin:{value:col('--skin','#EAC9A2')},uActive:{value:col('--muscle','#B23A1E')},uSupport:{value:col('--muscle-support','#E3A57C')},
      uShorts:{value:new THREE.Color('#7D6249')},uTop:{value:new THREE.Color('#8A6A4E')},uEye:{value:new THREE.Color('#C9A27C')},uHair:{value:new THREE.Color('#5A3E2B')},
      uL:{value:new Array(16).fill(0)},uR:{value:new Array(16).fill(0)}};
    return new THREE.ShaderMaterial({uniforms:u,vertexShader:VS,fragmentShader:FS,skinning:true,vertexColors:true});
  }
  function outlineMat(){
    return new THREE.ShaderMaterial({uniforms:{uC:{value:col('--ink','#3A2619')},uW:{value:1.1},uRes:{value:new THREE.Vector2(800,600)}},
      vertexShader:VS_OUT,fragmentShader:FS_FLAT,skinning:true,side:THREE.BackSide});
  }
  function solidMat(c){return new THREE.ShaderMaterial({uniforms:{uC:{value:new THREE.Color(c)}},vertexShader:VS_SOLID,fragmentShader:FS_SOLID});}

  // ---------- Aufbau ----------
  function ensureRoot(){
    if(root)return;
    injectCss();
    root=document.createElement('div');root.className='figRoot';
    const cv=document.createElement('div');cv.className='figCanvas';root.appendChild(cv);
    svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('class','figLines');root.appendChild(svg);
    lab=document.createElement('div');lab.className='figLabels';root.appendChild(lab);
    if(typeof THREE==='undefined'){setStatus('fallback','Three.js nicht geladen (Internet?)');return;}
    if(!THREE.GLTFLoader||!THREE.DRACOLoader){startFallback('GLTFLoader/DRACOLoader nicht geladen (Internet?)');return;}
    try{
      renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
      renderer.setClearColor(0x000000,0);
      renderer.setPixelRatio(Math.min(2,window.devicePixelRatio||1));
      cv.appendChild(renderer.domElement);
    }catch(e){startFallback('WebGL nicht verfügbar ('+e.message+')');return;}
    scene=new THREE.Scene();
    camera=new THREE.PerspectiveCamera(20,1,0.1,60);
    const g=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-1,0,0),new THREE.Vector3(1,0,0)]);
    floorLine=new THREE.Line(g,new THREE.LineBasicMaterial({color:col('--ink','#3A2619')}));
    scene.add(floorLine);
    if(window.ResizeObserver){ro=new ResizeObserver(()=>resize());}
    window.addEventListener('resize',resize);
    loop();
  }
  function injectCss(){
    if(document.getElementById('figCss'))return;
    const s=document.createElement('style');s.id='figCss';
    s.textContent=`.figRoot{position:absolute;inset:0;overflow:hidden}
.figCanvas{position:absolute;inset:0}.figCanvas canvas{display:block;width:100%!important;height:100%!important}
.figLines{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible}
.figLabels{position:absolute;inset:0;pointer-events:none}
.figLab{position:absolute;font-family:var(--f-label,'Spectral',serif);color:var(--ink,#3A2619);line-height:1.2;font-size:.95rem;width:max-content}
.figLab b{display:block;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.figLab span{display:block;font-size:.85rem;color:var(--ink,#3A2619)}
.figLab.l{text-align:right}
.figFallback{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
.figFallback>div{width:min(100%,100vh*.5);aspect-ratio:1}`;
    document.head.appendChild(s);
  }

  function resize(){
    if(!root||!host)return;
    const w=host.clientWidth,h=host.clientHeight;
    if(!w||!h)return;
    if(renderer){renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
      if(M)M.outline.material.uniforms.uRes.value.set(w,h);
      if(M)M.outline.material.uniforms.uW.value=Math.max(1,Math.min(2.2,h/600));
      frameCamera(true);}
    svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
    if(fb&&typeof Rig!=='undefined')Rig.resize();
  }

  // ---------- Modell laden ----------
  function load(key){
    if(cache[key])return cache[key];
    cache[key]=new Promise((res,rej)=>{
      const L=new THREE.GLTFLoader();
      const dl=new THREE.DRACOLoader();dl.setDecoderPath(DRACO);L.setDRACOLoader(dl);
      L.load(MODELS[key],g=>{try{res(prepare(g));}catch(e){rej(e);}},undefined,e=>rej(new Error((e&&e.message)||('Datei '+MODELS[key]+' nicht gefunden'))));
    });
    return cache[key];
  }
  function prepare(g){
    const sc=g.scene;let body=null,rig=null,meta=null;const db={};
    sc.traverse(o=>{
      if(o.isSkinnedMesh&&!body)body=o;
      if(o.userData&&o.userData.hiit&&!meta){try{meta=JSON.parse(o.userData.hiit);rig=o;}catch(e){}}
      if(/^db_(l|r|goblet|hip)$/.test(o.name))db[o.name]=o;
    });
    if(!body)throw new Error('kein Körper im Modell');
    if(!meta)throw new Error('Modell ohne Übungsdaten');
    body.material=bodyMat();body.frustumCulled=false;
    const ol=new THREE.SkinnedMesh(body.geometry,outlineMat());
    ol.bind(body.skeleton,body.bindMatrix);ol.frustumCulled=false;ol.renderOrder=-1;
    body.parent.add(ol);ol.position.copy(body.position);ol.quaternion.copy(body.quaternion);ol.scale.copy(body.scale);
    Object.values(db).forEach(o=>o.traverse(m=>{if(m.isMesh){const n=(m.material&&m.material.name)||'';m.material=solidMat(/grip/.test(n)?'#7D6249':'#3A2619');m.frustumCulled=false;}}));
    // alle Übungen liegen hintereinander in einer Animation "all" (24 Bilder/s), Bereiche stehen in meta
    const clips={},all=g.animations.find(a=>a.name==='all')||g.animations[0];
    if(!all)throw new Error('Modell ohne Animation');
    Object.entries(meta.exercises).forEach(([n,me])=>{clips[n]=THREE.AnimationUtils.subclip(all,n,me.start-0.5,me.start+me.frames+0.5,meta.fps||24);});
    const mixer=new THREE.AnimationMixer(sc);
    const bones={};body.skeleton.bones.forEach(b=>bones[b.name]=b);
    const anchors=computeAnchors(body);
    return {scene:sc,body,outline:ol,db,clips,mixer,meta,bones,anchors,action:null,clipName:null,loops:0};
  }
  // Ankerpunkte je Muskelgruppe und Seite: Vertex nahe dem Schwerpunkt der Gruppe
  function computeAnchors(body){
    const g=body.geometry,pos=g.attributes.position,c=g.attributes.color,nor=g.attributes.normal;
    if(!c)return {};
    const div=c.normalized?(c.array instanceof Uint8Array?255:c.array instanceof Uint16Array?65535:1):1;
    const groups={};
    for(let i=0;i<pos.count;i++){
      const id=Math.round(c.getX(i)/div*20);if(!id)continue;
      const b=c.getZ(i)/div,side=b>0.75?'l':b<0.25?'r':'c';
      [side==='c'?['l','r']:[side]].flat().forEach(s=>{const k=id+s;(groups[k]=groups[k]||[]).push(i);});
    }
    const out={},v=new THREE.Vector3(),cen=new THREE.Vector3();
    for(const k in groups){
      const L=groups[k];cen.set(0,0,0);
      L.forEach(i=>{v.fromBufferAttribute(pos,i);cen.add(v);});cen.multiplyScalar(1/L.length);
      let best=-1,bd=1e9;
      L.forEach(i=>{v.fromBufferAttribute(pos,i);const d=v.distanceToSquared(cen);if(d<bd){bd=d;best=i;}});
      const n=new THREE.Vector3().fromBufferAttribute(nor,best);
      out[k]={i:best,n};
    }
    return out;
  }

  // Skinning eines Punkts mit den Gewichten eines Vertex (für Anker und Sichtbarkeit)
  const _m=new THREE.Matrix4(),_v=new THREE.Vector3(),_acc=new THREE.Vector3();
  const GET=['getX','getY','getZ','getW'];
  function comp(a,i,j){let v=a[GET[j]](i);if(a.normalized){const A=a.array;v/=A instanceof Uint8Array?255:A instanceof Uint16Array?65535:A instanceof Int16Array?32767:A instanceof Int8Array?127:1;}return v;}
  function skinPoint(body,i,p,out){
    const sk=body.skeleton,si=body.geometry.attributes.skinIndex,sw=body.geometry.attributes.skinWeight;
    _acc.set(0,0,0);
    const b=_v.copy(p).applyMatrix4(body.bindMatrix);
    for(let j=0;j<4;j++){
      const w=comp(sw,i,j);if(!w)continue;
      const bi=si[GET[j]](i);
      _m.multiplyMatrices(sk.bones[bi].matrixWorld,sk.boneInverses[bi]);
      _acc.add(b.clone().applyMatrix4(_m).multiplyScalar(w));
    }
    return out.copy(_acc).applyMatrix4(body.bindMatrixInverse).applyMatrix4(body.matrixWorld);
  }

  // ---------- Übung zeigen ----------
  function setMuscles(k){
    if(!M)return;
    const a=(typeof ANATOMY!=='undefined'&&ANATOMY[ALIAS[k]||k])||null;
    const L=M.body.material.uniforms.uL.value,R=M.body.material.uniforms.uR.value;
    L.fill(0);R.fill(0);
    if(!a)return;
    const put=(m,v)=>{const g=MUSCLES[m[0]];if(!g)return;const s=m[3];if(s!=='r')L[g.id]=Math.max(L[g.id],v);if(s!=='l')R[g.id]=Math.max(R[g.id],v);};
    a.support.forEach(m=>put(m,1));a.active.forEach(m=>put(m,2));
  }
  function exMeta(k){return M&&M.meta.exercises[ALIAS[k]||k]||null;}
  function play(k){
    if(!M)return;
    const name=ALIAS[k]||k;
    const me=exMeta(k);
    const clipName=me?name:null;
    if(!clipName||!M.clips[clipName]){return;}
    M.exClips=(me.clips&&me.clips.filter(c=>M.clips[c]))||[clipName];
    M.exIdx=0;M.loops=0;
    startClip(M.exClips[0],0.35);
    const db=me.db||'none';
    Object.entries(M.db).forEach(([n,o])=>{o.visible=(n==='db_l'&&(db==='both'||db==='l'))||(n==='db_r'&&(db==='both'||db==='r'))||(n==='db_goblet'&&db==='goblet')||(n==='db_hip'&&db==='hip');});
    setMuscles(k);
    layout=null;
    frameCamera(false);
  }
  function startClip(name,fade){
    const clip=M.clips[name];if(!clip)return;
    const act=M.mixer.clipAction(clip);
    act.reset();act.setLoop(THREE.LoopRepeat,Infinity);act.enabled=true;
    if(M.action&&M.action!==act){act.crossFadeFrom(M.action,fade||0.3,false);}
    act.play();M.action=act;M.clipName=name;
    applySpeed();
  }
  function applySpeed(){
    if(!M||!M.action)return;
    const d=M.action.getClip().duration;
    let ts=1;
    if(cycle&&d>0&&!(M.exClips&&M.exClips.length>1))ts=d/cycle;
    M.action.timeScale=ts*(slow?0.5:1);
  }

  // ---------- Kamera ----------
  function viewDir(){
    const me=exMeta(exKey);const side=me&&me.side==='l'?1:-1;
    if(view==='front')return new THREE.Vector3(0,0,1);
    if(view==='back')return new THREE.Vector3(0,0,-1);
    return new THREE.Vector3(side,0,0);
  }
  function frameCamera(instant){
    if(!M||!camera)return;
    const me=exMeta(exKey);if(!me)return;
    const [mn,mx]=me.box;
    const c=new THREE.Vector3((mn[0]+mx[0])/2,(mn[1]+mx[1])/2,(mn[2]+mx[2])/2);
    const dir=viewDir();
    const wSpan=Math.abs(dir.x)>0.5?(mx[2]-mn[2]):(mx[0]-mn[0]);
    const hSpan=Math.max(0.6,mx[1]-mn[1]);
    const el=(me.lying?VIEW_EL.lying:VIEW_EL.stand)*Math.PI/180;
    // Figur nimmt etwa 58 % der Breite ein, Rest für Beschriftungen
    // stehend: Figur in der Mitte (Beschriftung links/rechts); liegend: Figur unten, Beschriftung darüber
    const lying=!!me.lying;
    const fw=lying?0.84:0.44,fh=lying?0.42:0.88;
    const dSpan=Math.abs(dir.x)>0.5?(mx[0]-mn[0]):(mx[2]-mn[2]);
    const needH=Math.max(hSpan/fh,(wSpan/fw)/camera.aspect,0.9);
    const dist=(needH/2)/Math.tan(camera.fov*Math.PI/360)+dSpan/2;
    const target=new THREE.Vector3(c.x,(mn[1]+mx[1])/2+(lying?needH*0.24:0),c.z);
    const pos=dir.clone().multiplyScalar(Math.cos(el)*dist).add(new THREE.Vector3(0,Math.sin(el)*dist,0)).add(target);
    const tgt={pos,target};
    if(instant||!camAnim){camAnim={from:tgt,to:tgt,t0:0,d:0};applyCam(tgt);}
    else camAnim={from:{pos:camera.position.clone(),target:camAnim.cur||target},to:tgt,t0:performance.now(),d:450};
    // Bodenlinie quer zur Blickrichtung
    const perp=new THREE.Vector3(-dir.z,0,dir.x).normalize();
    const half=Math.max(wSpan,0.6)*0.75+0.25;
    const g=floorLine.geometry;const p=g.attributes.position;
    p.setXYZ(0,c.x-perp.x*half,0,c.z-perp.z*half);p.setXYZ(1,c.x+perp.x*half,0,c.z+perp.z*half);p.needsUpdate=true;
    g.computeBoundingSphere();
    layout=null;
  }
  function applyCam(t){camera.position.copy(t.pos);camera.lookAt(t.target);if(camAnim)camAnim.cur=t.target.clone();}

  // ---------- Beschriftung ----------
  function labelItems(){
    const a=(typeof ANATOMY!=='undefined'&&ANATOMY[ALIAS[exKey]||exKey])||null;if(!a)return [];
    const items=[];let n=0;
    a.active.concat(a.support).forEach(m=>{const g=MUSCLES[m[0]];if(!g)return;n++;items.push({kind:'m',tag:String(n),name:m[2]||g.name,fn:m[1],g:g.id,side:m[3]||null});});
    a.hints.forEach((h,i)=>items.push({kind:'h',tag:String.fromCharCode(65+i),name:h[1],fn:h[2],lm:h[0]}));
    return items;
  }
  const _p=new THREE.Vector3(),_q=new THREE.Vector3(),_cam=new THREE.Vector3();
  function anchorWorld(it,out){
    if(!M)return null;
    camera.getWorldPosition(_cam);
    if(it.kind==='m'){
      const sides=it.side?[it.side]:['l','r'];let best=null,bs=-1e9;
      sides.forEach(s=>{
        const A=M.anchors[it.g+s];if(!A)return;
        const p=new THREE.Vector3().fromBufferAttribute(M.body.geometry.attributes.position,A.i);
        const w=skinPoint(M.body,A.i,p,new THREE.Vector3());
        const wn=skinPoint(M.body,A.i,p.clone().addScaledVector(A.n,0.06),new THREE.Vector3());
        const vis=wn.clone().sub(w).normalize().dot(_cam.clone().sub(w).normalize());
        if(vis>bs){bs=vis;best=w;}
      });
      if(!best||bs<-0.15)return null;
      return out.copy(best);
    }
    const m=/^(.*?)(?:_(l|r))?$/.exec(it.lm);const base=LM[m[1]];if(!base)return null;
    if(!/^(thigh|calf|foot|ball|upperarm|lowerarm|hand)$/.test(base)){const b=M.bones[base];return b?b.getWorldPosition(out):null;}
    const cands=m[2]?[m[2]]:['l','r'];let best=null,bd=1e9;
    cands.forEach(s=>{const b=M.bones[base+'_'+s];if(!b)return;const p=b.getWorldPosition(new THREE.Vector3());const d=p.distanceTo(_cam);if(d<bd){bd=d;best=p;}});
    return best?out.copy(best):null;
  }
  function toScreen(p,w,h){const v=p.clone().project(camera);return {x:(v.x+1)/2*w,y:(1-v.y)/2*h,z:v.z};}
  function renderLabels(){
    if(!root||!host)return;
    const w=host.clientWidth,h=host.clientHeight;
    if(!labelsOn||!M||!exKey||!w){svg.innerHTML='';lab.innerHTML='';return;}
    const me=exMeta(exKey),lying=!!(me&&me.lying);
    const rem=parseFloat(getComputedStyle(document.documentElement).fontSize)||16;
    const colW=lying?w*0.46:Math.min(w*0.28,14*rem);
    if(!layout||layout.key!==exKey+view+modelKey+w+'x'+h){
      const items=labelItems();
      lab.innerHTML='';
      items.forEach(it=>{const d=document.createElement('div');d.className='figLab';d.style.maxWidth=(colW-0.6*rem)+'px';d.innerHTML=`<b>${it.tag} ${esc(it.name)}</b><span>${esc(it.fn)}</span>`;lab.appendChild(d);it.el=d;});
      layout={key:exKey+view+modelKey+w+'x'+h,items,cols:null};
    }
    const items=layout.items;
    items.forEach(it=>{const p=anchorWorld(it,new THREE.Vector3());it.p=p?toScreen(p,w,h):null;});
    if(!layout.cols){
      // Spalte einmal je Übung/Ansicht festlegen (verhindert Springen)
      const vis=items.filter(i=>i.p);const cx=vis.length?vis.reduce((a,i)=>a+i.p.x,0)/vis.length:w/2;
      items.forEach(it=>{it.col=it.p?(it.p.x<cx?'l':'r'):'r';});
      const cnt=c=>items.filter(i=>i.col===c).length;
      while(Math.abs(cnt('l')-cnt('r'))>1){const from=cnt('l')>cnt('r')?'l':'r';const cand=items.filter(i=>i.col===from&&i.p).sort((a,b)=>from==='l'?b.p.x-a.p.x:a.p.x-b.p.x)[0];if(!cand)break;cand.col=from==='l'?'r':'l';}
      items.forEach(it=>{it.el.className='figLab'+(it.col==='l'&&!lying?' l':'');});
      layout.cols=true;
    }
    const pad=0.5*rem,gap=0.45*rem;
    ['l','r'].forEach(c=>{
      const L=items.filter(i=>i.col===c&&i.p);
      L.forEach(it=>{it.hh=it.el.offsetHeight||2.4*rem;});
      if(lying){
        // oben gestapelt; die oberste Beschriftung führt zum innersten Anker, so kreuzen sich die Linien nicht
        L.sort((a,b)=>c==='l'?b.p.x-a.p.x:a.p.x-b.p.x);
        let y=pad;L.forEach(it=>{it.ly=y;y+=it.hh+gap;});
      }else{
        L.sort((a,b)=>a.p.y-b.p.y);
        let y=pad;
        L.forEach(it=>{it.ly=Math.max(it.p.y-it.hh*0.3,y);y=it.ly+it.hh+gap;});
        let over=y-gap-(h-pad);
        for(let i=L.length-1;i>=0&&over>0;i--){const it=L[i];const lim=i?L[i-1].ly+L[i-1].hh+gap:pad;const ny=Math.max(lim,it.ly-over);over-=it.ly-ny;it.ly=ny;}
        if(over>0){let y2=pad;L.forEach(it=>{it.ly=y2;y2+=it.hh+gap;});}
      }
    });
    const ink=css('--ink')||'#3A2619';
    let s='';
    items.forEach(it=>{
      if(!it.p){it.el.style.display='none';return;}
      it.el.style.display='';
      const ly=it.ly+0.62*rem,tw=it.el.offsetWidth;
      let x0,x1;
      if(it.col==='l'){
        if(lying){it.el.style.right='auto';it.el.style.left=pad+'px';x0=pad+tw+0.4*rem;}
        else{it.el.style.left='auto';it.el.style.right=(w-colW)+'px';x0=colW+0.4*rem;}
        x1=x0+Math.max(0.8*rem,Math.min(2*rem,(it.p.x-x0)*0.35));
      }else{
        if(lying){it.el.style.left='auto';it.el.style.right=pad+'px';x0=w-pad-tw-0.4*rem;}
        else{it.el.style.right='auto';it.el.style.left=(w-colW)+'px';x0=w-colW-0.4*rem;}
        x1=x0-Math.max(0.8*rem,Math.min(2*rem,(x0-it.p.x)*0.35));
      }
      it.el.style.top=it.ly+'px';
      s+=`<polyline points="${x0.toFixed(1)},${ly.toFixed(1)} ${x1.toFixed(1)},${ly.toFixed(1)} ${it.p.x.toFixed(1)},${it.p.y.toFixed(1)}"/>`;
      s+=`<circle fill="${ink}" stroke="none" cx="${it.p.x.toFixed(1)}" cy="${it.p.y.toFixed(1)}" r="${(0.2*rem).toFixed(1)}"/>`;
    });
    svg.innerHTML=`<g fill="none" stroke="${ink}" stroke-width="1">${s}</g>`;
  }
  const esc=t=>String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

  // ---------- Schleife ----------
  function loop(){
    raf=requestAnimationFrame(loop);
    const now=performance.now(),dt=Math.min(0.1,(now-(lastT||now))/1000);lastT=now;
    if(!root||!host||!root.isConnected||document.hidden||!renderer||!M||!M.action)return;
    if(!host.clientWidth||!host.clientHeight)return;
    const prevT=M.action.time;
    M.mixer.update(dt);
    // Hüftbrücke + Katze-Kuh: Clips abwechseln
    if(M.exClips&&M.exClips.length>1&&M.action.time<prevT){M.loops++;const lim=M.exIdx===0?3:2;if(M.loops>=lim){M.loops=0;M.exIdx=(M.exIdx+1)%M.exClips.length;startClip(M.exClips[M.exIdx],0.6);}}
    if(camAnim&&camAnim.d){const u=Math.min(1,(now-camAnim.t0)/camAnim.d),e=u<.5?2*u*u:1-Math.pow(-2*u+2,2)/2;
      applyCam({pos:camAnim.from.pos.clone().lerp(camAnim.to.pos,e),target:camAnim.from.target.clone().lerp(camAnim.to.target,e)});if(u>=1)camAnim.d=0;}
    renderer.render(scene,camera);
    renderLabels();
  }

  // ---------- Rückfall ----------
  function startFallback(msg){
    setStatus('fallback',msg);
    if(!root)return;
    if(svg)svg.innerHTML='';if(lab)lab.innerHTML='';
    if(typeof Rig==='undefined'||typeof THREE==='undefined')return;
    if(!fb){fb=document.createElement('div');fb.className='figFallback';const inner=document.createElement('div');fb.appendChild(inner);root.appendChild(fb);
      try{Rig.init(inner);}catch(e){}}
    if(renderer&&renderer.domElement)renderer.domElement.style.display='none';
    if(exKey)try{Rig.show(ALIAS[exKey]||exKey);rigView();}catch(e){}
    if(cycle)Rig.setCycle(cycle);
  }
  function rigView(){if(fb&&Rig._setAz)Rig._setAz({side:90,front:0,back:180}[view]);}

  function useModel(key){
    modelKey=MODELS[key]?key:'man';
    if(!renderer){return;}
    setStatus('loading');
    load(modelKey).then(m=>{
      if(m!==M){if(M)scene.remove(M.scene);M=m;scene.add(M.scene);}
      if(fb){fb.remove();fb=null;renderer.domElement.style.display='';}
      setStatus('model');
      resize();
      if(exKey)play(exKey);
    }).catch(e=>{delete cache[modelKey];startFallback(e.message||String(e));});
  }

  // ---------- API ----------
  return {
    mount(el){
      ensureRoot();
      host=el;
      if(getComputedStyle(el).position==='static')el.style.position='relative';
      if(root.parentNode!==el)el.appendChild(root);
      if(ro){ro.disconnect();ro.observe(el);}
      if(renderer&&!M&&status.mode!=='fallback')useModel(modelKey);
      resize();
      if(fb&&typeof Rig!=='undefined')Rig.resize();
    },
    show(k){
      const changed=k!==exKey;exKey=k;
      if(fb){try{Rig.show(ALIAS[k]||k);if(changed)rigView();}catch(e){}return;}
      if(M&&changed)play(k);
    },
    setView(v){if(!['side','front','back'].includes(v))return;view=v;if(fb)rigView();else frameCamera(false);},
    setSlow(b){slow=!!b;applySpeed();},
    setCycle(sec){cycle=sec||null;if(fb&&typeof Rig!=='undefined')Rig.setCycle(cycle);applySpeed();},
    setModel(k){const nk=MODELS[k]?k:'man';if(nk===modelKey&&(M||status.mode==='loading'&&cache[nk]))return;modelKey=nk;if(renderer&&host)useModel(nk);},
    labels(b){labelsOn=!!b;layout=null;},
    onStatus(f){onSt.push(f);try{f(status);}catch(e){}},
    status:()=>status,
    // für Tests
    _debug:()=>({M,camera,exKey,view,slow,cycle}),
    _seek(t){if(M&&M.action){M.action.time=t;M.mixer.update(0);}}
  };
})();
