// ---------- 3D-Figur (Three.js r128, global THREE) ----------
const Rig=(function(){
  const D=Math.PI/180;
  const DEF={root:{rx:0,ry:0,rz:0},torso:{fwd:0,side:0,twist:0},head:{fwd:0},
    armL:{fwd:0,abd:8,rot:0,elbow:0},armR:{fwd:0,abd:8,rot:0,elbow:0},
    legL:{fwd:0,abd:3,knee:0,ankle:0},legR:{fwd:0,abd:3,knee:0,ankle:0}};
  const KEYS=[];Object.keys(DEF).forEach(j=>Object.keys(DEF[j]).forEach(p=>KEYS.push([j,p])));
  function flat(pose){return KEYS.map(([j,p])=>(pose[j]&&pose[j][p]!=null)?pose[j][p]:DEF[j][p]);}
  function arms(o){return {armL:o,armR:o};} function legs(o){return {legL:o,legR:o};}
  const LIE={root:{rx:-90}};
  const PLANK=Object.assign({root:{rx:68}},{armL:{fwd:68,abd:10},armR:{fwd:68,abd:10}},{legL:{ankle:25},legR:{ankle:25}});
  const PUSH_LOW=Object.assign({root:{rx:82}},{armL:{fwd:15,abd:35,elbow:95},armR:{fwd:15,abd:35,elbow:95}},{legL:{ankle:25},legR:{ankle:25}});
  const FEET_PLANTED=legs({fwd:55,knee:125});
  const SQ_DEEP=Object.assign({},legs({fwd:100,knee:125}),{torso:{fwd:30}});

  // Übungen: frames = [{t:Sekunden bis zu diesem Frame, pose}], az = Kamerawinkel
  const EXS={
    kniehebe:{az:35,frames:[
      {t:.4,pose:{legL:{fwd:90,knee:90},armR:{fwd:50,elbow:90},armL:{fwd:-25,elbow:70}}},
      {t:.4,pose:{legR:{fwd:90,knee:90},armL:{fwd:50,elbow:90},armR:{fwd:-25,elbow:70}}}]},
    sqa:{az:35,frames:[
      {t:1.2,pose:arms({fwd:170,abd:12})},
      {t:1.2,pose:Object.assign({},legs({fwd:95,knee:120}),{torso:{fwd:30}},arms({fwd:60,abd:10}))}]},
    bridge2:{el:32,az:60,frames:[
      {t:1,pose:Object.assign({},LIE,FEET_PLANTED,arms({abd:18}))},
      {t:1,pose:Object.assign({},{root:{rx:-110}},legs({fwd:0,knee:110}),arms({abd:18}))},
      {t:.5,pose:Object.assign({},{root:{rx:-110}},legs({fwd:0,knee:110}),arms({abd:18}))}]},
    splitsquat:{az:60,db:'both',frames:[
      {t:1.2,pose:{legL:{fwd:25,knee:25},legR:{fwd:-20,knee:20,ankle:30},torso:{fwd:5}}},
      {t:1.2,pose:{legL:{fwd:75,knee:75},legR:{fwd:-15,knee:95,ankle:50},torso:{fwd:12}}}]},
    pushup:{el:36,az:65,frames:[
      {t:1,pose:PLANK},
      {t:1,pose:PUSH_LOW}]},
    slrdl:{el:20,az:80,db:'both',frames:[
      {t:1.4,pose:{legR:{fwd:-10},legL:{knee:10}}},
      {t:1.4,pose:Object.assign({},{torso:{fwd:85},head:{fwd:-40},legL:{fwd:0,knee:20},legR:{fwd:-95}},arms({fwd:85,abd:10}))}]},
    floorpress:{el:32,az:55,db:'both',frames:[
      {t:1,pose:Object.assign({},LIE,FEET_PLANTED,arms({fwd:90,abd:5,rot:0}))},
      {t:1,pose:Object.assign({},LIE,FEET_PLANTED,arms({fwd:0,abd:50,rot:0,elbow:90}))}]},
    row1:{el:22,az:-70,db:'R',frames:[
      {t:.9,pose:{legL:{fwd:30,knee:30},legR:{fwd:-25,knee:15},torso:{fwd:45},head:{fwd:-30},armL:{fwd:60,abd:5,elbow:15},armR:{fwd:45,abd:8}}},
      {t:.9,pose:{legL:{fwd:30,knee:30},legR:{fwd:-25,knee:15},torso:{fwd:45},head:{fwd:-30},armL:{fwd:60,abd:5,elbow:15},armR:{fwd:-15,abd:8,elbow:95}}}]},
    deadbug:{el:40,az:45,frames:[
      {t:1.2,pose:Object.assign({},LIE,arms({fwd:90,abd:5}),legs({fwd:90,knee:90}))},
      {t:1.2,pose:Object.assign({},LIE,{armR:{fwd:165,abd:5},armL:{fwd:90,abd:5},legL:{fwd:15,knee:5},legR:{fwd:90,knee:90}})},
      {t:1.2,pose:Object.assign({},LIE,arms({fwd:90,abd:5}),legs({fwd:90,knee:90}))},
      {t:1.2,pose:Object.assign({},LIE,{armL:{fwd:165,abd:5},armR:{fwd:90,abd:5},legR:{fwd:15,knee:5},legL:{fwd:90,knee:90}})}]},
    goblet:{az:40,db:'one',frames:[
      {t:1,pose:arms({fwd:45,abd:12,elbow:125})},
      {t:3,pose:Object.assign({},SQ_DEEP,arms({fwd:45,abd:12,elbow:125}))},
      {t:.4,pose:Object.assign({},SQ_DEEP,arms({fwd:45,abd:12,elbow:125}))}]},
    press:{az:30,db:'both',frames:[
      {t:1,pose:arms({abd:75,rot:90,elbow:110})},
      {t:1,pose:arms({abd:170,rot:90,elbow:0})}]},
    bridge1:{el:32,az:60,db:'one',frames:[
      {t:1,pose:Object.assign({},LIE,{legL:{fwd:55,knee:125},legR:{fwd:25,knee:0}},arms({fwd:0,abd:12,elbow:60}))},
      {t:1,pose:Object.assign({},{root:{rx:-110}},{legL:{fwd:0,knee:110},legR:{fwd:0,knee:0}},arms({fwd:0,abd:12,elbow:60}))},
      {t:.5,pose:Object.assign({},{root:{rx:-110}},{legL:{fwd:0,knee:110},legR:{fwd:0,knee:0}},arms({fwd:0,abd:12,elbow:60}))}]},
    row:{el:22,az:80,db:'both',frames:[
      {t:1,pose:Object.assign({},legs({fwd:15,knee:15}),{torso:{fwd:70},head:{fwd:-30}},arms({fwd:70,abd:10}))},
      {t:1,pose:Object.assign({},legs({fwd:15,knee:15}),{torso:{fwd:70},head:{fwd:-30}},arms({fwd:-15,abd:10,elbow:95}))}]},
    lunge:{az:60,db:'both',frames:[
      {t:.8,pose:{}},
      {t:.9,pose:{legR:{fwd:-20,knee:95,ankle:50},legL:{fwd:70,knee:75},torso:{fwd:8}}},
      {t:.8,pose:{}},
      {t:.9,pose:{legL:{fwd:-20,knee:95,ankle:50},legR:{fwd:70,knee:75},torso:{fwd:8}}}]},
    sideplank:{el:26,az:10,frames:[
      {t:1.5,pose:{root:{rz:68},armR:{abd:68,elbow:90,rot:0},armL:{abd:0,fwd:0},legL:{abd:0},legR:{abd:0}}},
      {t:1.5,pose:{root:{rz:76},armR:{abd:68,elbow:90,rot:0},armL:{abd:0,fwd:0},legL:{abd:0},legR:{abd:0}}}]},
    thruster:{az:35,db:'both',frames:[
      {t:.7,pose:Object.assign({},legs({fwd:100,knee:125}),{torso:{fwd:25}},arms({abd:70,rot:90,elbow:115}))},
      {t:.7,pose:arms({abd:170,rot:90,elbow:0})}]},
    burpee:{el:30,az:60,frames:[
      {t:.6,pose:{}},
      {t:.6,pose:Object.assign({},legs({fwd:110,knee:130}),{torso:{fwd:70},head:{fwd:-30}},arms({fwd:110,abd:15}))},
      {t:.6,pose:PLANK},
      {t:.5,pose:PUSH_LOW},
      {t:.5,pose:PLANK},
      {t:.6,pose:Object.assign({},legs({fwd:110,knee:130}),{torso:{fwd:70},head:{fwd:-30}},arms({fwd:110,abd:15}))}]},
    walk:{az:35,frames:[
      {t:.5,pose:{legL:{fwd:30,knee:30},armR:{fwd:25,elbow:40},armL:{fwd:-20,elbow:30}}},
      {t:.5,pose:{legR:{fwd:30,knee:30},armL:{fwd:25,elbow:40},armR:{fwd:-20,elbow:30}}}]},
    hipflex:{az:70,frames:[
      {t:2,pose:Object.assign({},{legR:{fwd:-15,knee:95},legL:{fwd:95,knee:70}},arms({abd:18,elbow:80}))},
      {t:2,pose:Object.assign({},{legR:{fwd:-35,knee:100},legL:{fwd:100,knee:60}},arms({abd:18,elbow:80}))}]},
    chest:{az:-45,frames:[
      {t:2,pose:arms({fwd:-35,abd:8})},
      {t:2,pose:arms({fwd:-55,abd:4})}]}
  };
  EXS.probe=EXS.splitsquat;

  // ---- Aufbau ----
  let renderer,scene,camera,rig,J,dbL,dbR,dbOne,container,cur=null,t0=0,az=35,drag=null,raf=null;
  const skin=0xdfe3e8, skin2=0xb9c0c9, accent=0xe4572e;
  function capsule(len,r,color){
    const g=new THREE.Group();const m=new THREE.MeshStandardMaterial({color,roughness:.6});
    const cyl=new THREE.Mesh(new THREE.CylinderGeometry(r,r,len,14),m);cyl.position.y=-len/2;cyl.castShadow=true;g.add(cyl);
    const s1=new THREE.Mesh(new THREE.SphereGeometry(r,14,10),m);s1.castShadow=true;g.add(s1);
    const s2=new THREE.Mesh(new THREE.SphereGeometry(r,14,10),m);s2.position.y=-len;s2.castShadow=true;g.add(s2);
    return g;
  }
  function dumbbell(){
    const g=new THREE.Group();const m=new THREE.MeshStandardMaterial({color:accent,roughness:.4});const mb=new THREE.MeshStandardMaterial({color:0x777d86,roughness:.4});
    const bar=new THREE.Mesh(new THREE.CylinderGeometry(.015,.015,.3,10),mb);bar.rotation.x=Math.PI/2;g.add(bar);
    [-.12,.12].forEach(z=>{const p=new THREE.Mesh(new THREE.CylinderGeometry(.06,.06,.05,16),m);p.rotation.x=Math.PI/2;p.position.z=z;p.castShadow=true;g.add(p);});
    return g;
  }
  function build(){
    rig=new THREE.Group();J={};
    const pelvis=new THREE.Group();rig.add(pelvis);J.root=pelvis;
    const pm=new THREE.Mesh(new THREE.SphereGeometry(.13,16,12),new THREE.MeshStandardMaterial({color:skin2,roughness:.6}));pm.scale.set(1.3,.8,.9);pm.castShadow=true;pelvis.add(pm);
    const torso=new THREE.Group();pelvis.add(torso);J.torso=torso;
    const tm=new THREE.Mesh(new THREE.CylinderGeometry(.16,.12,.48,16),new THREE.MeshStandardMaterial({color:skin,roughness:.6}));tm.position.y=.26;tm.scale.set(1.25,1,.75);tm.castShadow=true;torso.add(tm);
    const neck=new THREE.Group();neck.position.y=.5;torso.add(neck);J.head=neck;
    const head=new THREE.Mesh(new THREE.SphereGeometry(.11,18,14),new THREE.MeshStandardMaterial({color:skin,roughness:.6}));head.position.y=.17;head.castShadow=true;neck.add(head);
    const nose=new THREE.Mesh(new THREE.SphereGeometry(.03,10,8),new THREE.MeshStandardMaterial({color:accent}));nose.position.set(0,.16,.11);neck.add(nose);
    [['L',1],['R',-1]].forEach(([s,sg])=>{
      const sh=new THREE.Group();sh.position.set(sg*.21,.47,0);sh.rotation.order='XZY';torso.add(sh);J['armU'+s]=sh;
      sh.add(capsule(.3,.05,skin));
      const el=new THREE.Group();el.position.y=-.3;sh.add(el);J['armF'+s]=el;
      el.add(capsule(.28,.045,skin));
      const hand=new THREE.Group();hand.position.y=-.3;el.add(hand);J['hand'+s]=hand;
      const db=dumbbell();hand.add(db);J['db'+s]=db;
      const hp=new THREE.Group();hp.position.set(sg*.1,-.02,0);hp.rotation.order='XZY';pelvis.add(hp);J['legU'+s]=hp;
      hp.add(capsule(.45,.065,skin));
      const kn=new THREE.Group();kn.position.y=-.45;hp.add(kn);J['legL'+s]=kn;
      kn.add(capsule(.43,.05,skin));
      const an=new THREE.Group();an.position.y=-.43;kn.add(an);J['foot'+s]=an;
      const fm=new THREE.Mesh(new THREE.BoxGeometry(.09,.07,.25),new THREE.MeshStandardMaterial({color:skin2,roughness:.7}));fm.position.set(0,-.035,.06);fm.castShadow=true;an.add(fm);
    });
    dbOne=dumbbell();dbOne.visible=false;scene.add(dbOne);
    scene.add(rig);
  }
  function applyPose(v){
    const g={};KEYS.forEach(([j,p],i)=>{(g[j]=g[j]||{})[p]=v[i];});
    J.root.rotation.set(g.root.rx*D,g.root.ry*D,g.root.rz*D);
    J.torso.rotation.set(g.torso.fwd*D,g.torso.twist*D,g.torso.side*D);
    J.head.rotation.set(g.head.fwd*D,0,0);
    [['L',1],['R',-1]].forEach(([s,sg])=>{
      const a=g['arm'+s],l=g['leg'+s];
      J['armU'+s].rotation.set(-a.fwd*D,sg*a.rot*D,sg*a.abd*D);
      J['armF'+s].rotation.set(-a.elbow*D,0,0);
      J['legU'+s].rotation.set(-l.fwd*D,0,sg*l.abd*D);
      J['legL'+s].rotation.set(l.knee*D,0,0);
      J['foot'+s].rotation.set(l.ankle*D,0,0);
    });
    // Boden und Zentrierung
    rig.position.set(0,0,0);rig.updateMatrixWorld(true);
    const pts=[];const tmp=new THREE.Vector3();
    const add=(obj,x,y,z,r)=>{tmp.set(x,y,z);obj.localToWorld(tmp);pts.push([tmp.x,tmp.y-r,tmp.z]);};
    add(J.head,0,.17,0,.11);add(J.torso,0,.47,0,.1);add(J.torso,0,.25,.13,.03);add(J.torso,0,.25,-.1,.03);add(J.root,0,0,0,.1);
    ['L','R'].forEach(s=>{add(J['armF'+s],0,0,0,.05);add(J['hand'+s],0,0,0,.05);add(J['legL'+s],0,0,0,.055);add(J['foot'+s],0,-.07,.19,0);add(J['foot'+s],0,-.07,-.05,0);add(J['foot'+s],0,0,0,.05);});
    let minY=1e9,sx=0,sz=0,maxY=-1e9;pts.forEach(p=>{if(p[1]<minY)minY=p[1];if(p[1]>maxY)maxY=p[1];sx+=p[0];sz+=p[2];});
    rig.position.set(-sx/pts.length,-minY,-sz/pts.length);
    rig.updateMatrixWorld(true);
    return (maxY-minY)/2;
  }
  function setDb(mode){
    J.dbL.visible=mode==='both'||mode==='L';J.dbR.visible=mode==='both'||mode==='R';dbOne.visible=mode==='one';
    if(mode==='one'){const a=new THREE.Vector3(),b=new THREE.Vector3();J.handL.getWorldPosition(a);J.handR.getWorldPosition(b);dbOne.position.copy(a).add(b).multiplyScalar(.5);dbOne.rotation.set(Math.PI/2,0,0);}
  }
  function lerpPose(ex,time){
    const fr=ex.frames,n=fr.length;const total=fr.reduce((a,f)=>a+f.t,0);let tt=time%total;
    let i=0;while(tt>fr[(i+1)%n].t&&i<n){tt-=fr[(i+1)%n].t;i++;}
    const A=flat(fr[i%n].pose),B=flat(fr[(i+1)%n].pose),u=tt/fr[(i+1)%n].t,e=u<.5?2*u*u:1-Math.pow(-2*u+2,2)/2;
    return A.map((a,k)=>a+(B[k]-a)*e);
  }
  function loop(){
    raf=requestAnimationFrame(loop);
    if(!cur||document.hidden)return;
    const v=lerpPose(cur,(performance.now()-t0)/1000);
    const halfH=applyPose(v);setDb(cur.db||'none');
    const r=2.9,el=(cur.el||18)*D,a=az*D;
    camera.position.set(r*Math.cos(el)*Math.sin(a),halfH+r*Math.sin(el)+.15,r*Math.cos(el)*Math.cos(a));
    camera.lookAt(0,halfH,0);
    renderer.render(scene,camera);
  }
  function init(el){
    container=el;
    renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});renderer.setPixelRatio(Math.min(2,window.devicePixelRatio||1));renderer.shadowMap.enabled=true;
    el.appendChild(renderer.domElement);
    scene=new THREE.Scene();
    camera=new THREE.PerspectiveCamera(38,1,.1,20);
    scene.add(new THREE.HemisphereLight(0xffffff,0x334455,.9));
    const sun=new THREE.DirectionalLight(0xffffff,.9);sun.position.set(2,4,3);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);sun.shadow.camera.left=-2;sun.shadow.camera.right=2;sun.shadow.camera.top=2;sun.shadow.camera.bottom=-2;scene.add(sun);
    const floor=new THREE.Mesh(new THREE.CircleGeometry(1.6,48),new THREE.MeshStandardMaterial({color:0x262b33,roughness:1}));floor.rotation.x=-Math.PI/2;floor.receiveShadow=true;scene.add(floor);
    const mat=new THREE.Mesh(new THREE.PlaneGeometry(.7,1.9),new THREE.MeshStandardMaterial({color:0x2f3640,roughness:1}));mat.rotation.x=-Math.PI/2;mat.position.y=.004;mat.receiveShadow=true;scene.add(mat);
    build();resize();window.addEventListener('resize',resize);
    const pos=e=>(e.touches?e.touches[0].clientX:e.clientX);
    el.addEventListener('pointerdown',e=>{drag={x:e.clientX,az};el.setPointerCapture&&el.setPointerCapture(e.pointerId);});
    el.addEventListener('pointermove',e=>{if(drag)az=drag.az-(e.clientX-drag.x)*.6;});
    el.addEventListener('pointerup',()=>{drag=null;});el.addEventListener('pointercancel',()=>{drag=null;});
    if(!raf)loop();
  }
  function resize(){const w=container.clientWidth||200;renderer.setSize(w,w,false);camera.aspect=1;camera.updateProjectionMatrix();}
  function show(key){const ex=EXS[key];if(!ex)return;if(cur!==ex){cur=ex;t0=performance.now();az=ex.az;}}
  function turn(d){az+=d;}
  return {init,show,resize,turn,has:k=>!!EXS[k],_setAz:a=>{az=a;},_J:()=>J};
})();
