// ---------- HR: Live-Puls per Web Bluetooth (Heart Rate Service 0x180D, Messwert 0x2A37) ----------
// Quelle: Brustgurt oder Apple Watch mit einer App, die den Puls als BLE-Pulsmesser sendet (z. B. HeartBLE).
// requestDevice() geht nur direkt nach einem Klick (Nutzergeste), daher connect() nur aus einem Klick-Handler aufrufen.
const HR=(function(){
  const MAX_TRIES=3,STALE_MS=5000;
  let dev=null,ch=null,name='',manual=false,tries=0,last=null,lastAt=0,h={};

  function supported(){return !!(navigator.bluetooth&&navigator.bluetooth.requestDevice);}
  function status(s){h.onStatus&&h.onStatus(s);}
  // 0x2A37: Byte 0 = Flags; Bit 0 gesetzt = Wert als UInt16 (little endian), sonst UInt8
  function parse(dv){const f=dv.getUint8(0);return (f&1)?dv.getUint16(1,true):dv.getUint8(1);}
  function onValue(e){
    const v=parse(e.target.value);
    if(v>0&&v<300){last=v;lastAt=Date.now();h.onBpm&&h.onBpm(v);}
  }

  async function attach(){
    status('verbindet mit '+name+' …');
    const srv=await dev.gatt.connect();
    const svc=await srv.getPrimaryService('heart_rate');
    const c=await svc.getCharacteristic('heart_rate_measurement');
    if(ch)ch.removeEventListener('characteristicvaluechanged',onValue);
    ch=c;ch.addEventListener('characteristicvaluechanged',onValue);
    await ch.startNotifications();
    tries=0;status('verbunden: '+name);
  }
  async function onDisconnected(){
    last=null;
    if(manual)return;
    if(tries>=MAX_TRIES){status('getrennt: '+name+' (3 Versuche fehlgeschlagen, neu verbinden)');return;}
    tries++;
    status(`Verbindung zu ${name} verloren, Versuch ${tries} von ${MAX_TRIES} …`);
    await new Promise(r=>setTimeout(r,1000*tries));
    if(manual)return;
    try{await attach();}
    catch(e){if(!dev.gatt.connected)onDisconnected();}
  }

  async function connect(){
    if(!supported())throw new Error('Web Bluetooth fehlt (Chrome oder Edge am PC oder Android nötig)');
    const d=await navigator.bluetooth.requestDevice({filters:[{services:['heart_rate']}]});
    if(dev&&dev!==d){manual=true;try{dev.gatt.disconnect();}catch(e){}dev.removeEventListener('gattserverdisconnected',onDisconnected);}
    dev=d;name=d.name||'Pulsmesser';manual=false;tries=0;
    dev.addEventListener('gattserverdisconnected',onDisconnected);
    await attach();
    return name;
  }
  function disconnect(){
    manual=true;last=null;
    try{if(ch)ch.stopNotifications().catch(()=>{});}catch(e){}
    try{if(dev&&dev.gatt.connected)dev.gatt.disconnect();}catch(e){}
    status('getrennt');
  }
  function connected(){return !!(dev&&dev.gatt&&dev.gatt.connected);}
  // aktueller Puls, null wenn älter als 5 s
  function current(){return last!=null&&Date.now()-lastAt<STALE_MS?last:null;}
  function on(x){h=Object.assign(h,x||{});}

  return {supported,connect,disconnect,connected,current,on,deviceName:()=>name,_parse:parse};
})();
