// ---------- Muskeln und Formhinweise je Übung ----------
// Muskelgruppen: id = Wert im Vertex-Color-Kanal R der Modelle (models/*.glb), siehe tools/blender/build_models.py
const MUSCLES={
  chest:      {id:1, name:'Brustmuskel',            short:'Brust'},
  delt_front: {id:2, name:'Vorderer Deltamuskel',   short:'vordere Schulter'},
  delt_side:  {id:3, name:'Seitlicher Deltamuskel', short:'seitliche Schulter'},
  triceps:    {id:4, name:'Trizeps',                short:'Trizeps'},
  biceps:     {id:5, name:'Bizeps',                 short:'Bizeps'},
  upper_back: {id:6, name:'Oberer Rücken',          short:'oberer Rücken'},
  lats:       {id:7, name:'Breiter Rückenmuskel',   short:'breiter Rücken'},
  lower_back: {id:8, name:'Rückenstrecker',         short:'unterer Rücken'},
  abs:        {id:9, name:'Gerader Bauchmuskel',    short:'Bauch'},
  obliques:   {id:10,name:'Schräge Bauchmuskeln',   short:'schräge Bauchmuskeln'},
  glutes:     {id:11,name:'Gesäßmuskel',            short:'Gesäß'},
  quads:      {id:12,name:'Quadrizeps',             short:'Quadrizeps'},
  hamstrings: {id:13,name:'Hintere Oberschenkel',   short:'hintere Oberschenkel'},
  adductors:  {id:14,name:'Adduktoren',             short:'Adduktoren'},
  calves:     {id:15,name:'Wadenmuskel',            short:'Waden'}
};

// Je Übung:
//  active/support: [Gruppe, Funktion, Name (optional, sonst MUSCLES.name), Seite (optional 'l'|'r', sonst beide)]
//  hints: [Ankerpunkt, Titel, Text]; Ankerpunkte sind Gelenke des Rigs (figure.js LANDMARKS),
//         mit _l/_r für eine Seite oder ohne Endung für die Seite, die näher an der Kamera liegt.
// Seiten aus Sicht der Figur: links = _l.
const ANATOMY={
  kniehebe:{
    active:[['quads','hebt das Knie, gerader Schenkelmuskel'],['calves','federt vom Vorfuß ab']],
    support:[['abs','hält den Oberkörper aufrecht','Rumpf']],
    hints:[['knee','Knie hüfthoch','Oberschenkel waagerecht'],['neck','Aufrecht','nicht nach hinten lehnen']]},
  sqa:{
    active:[['quads','streckt das Knie'],['glutes','streckt die Hüfte']],
    support:[['delt_side','kreist die Arme'],['abs','hält den Rücken lang','Rumpf']],
    hints:[['ankle','Fersen am Boden','Gewicht auf dem ganzen Fuß'],['knee','Knie Richtung Fußspitzen','nicht nach innen']]},
  bridge2:{
    active:[['glutes','hebt das Becken'],['hamstrings','helfen beim Heben']],
    support:[['abs','verhindert das Hohlkreuz','Rumpf']],
    hints:[['hip','Schulter–Hüfte–Knie','oben eine Linie'],['spine_lower','Kein Hohlkreuz','Po anspannen, nicht den Rücken']]},
  probe:null, // wird zur Laufzeit durch die erste Übung des Paars ersetzt
  splitsquat:{
    active:[['quads','Hauptarbeit'],['glutes','Hauptarbeit']],
    support:[['abs','stabilisiert, aufrecht','Rumpf'],['adductors','halten das Knie in der Spur']],
    hints:[['knee_l','Knie über Fuß','nicht nach innen'],['knee_r','Hinteres Knie','knapp über dem Boden']]},
  pushup:{
    active:[['chest','Hauptarbeit'],['triceps','streckt den Arm']],
    support:[['delt_front','hebt den Arm nach vorn'],['abs','Linie Kopf bis Ferse','Rumpf']],
    hints:[['hip','Hüfte in Linie','nicht durchhängen'],['elbow','Ellbogen','etwa 45 Grad zum Körper']]},
  slrdl:{
    active:[['hamstrings','bremsen und heben, Standbein',null,'l'],['glutes','strecken die Hüfte, Standbein',null,'l']],
    support:[['lower_back','hält den Rücken gerade'],['adductors','stabilisieren das Becken']],
    hints:[['spine_upper','Rücken gerade','vom Kopf bis zum Becken'],['hip_r','Becken parallel','Hüfte nicht aufdrehen']]},
  floorpress:{
    active:[['chest','Hauptarbeit'],['triceps','streckt den Arm']],
    support:[['delt_front','hebt den Arm nach vorn']],
    hints:[['elbow','Ellbogen','etwa 45 Grad, Oberarm berührt den Boden'],['wrist','Handgelenk','gerade über dem Ellbogen']]},
  row1:{
    active:[['lats','zieht den Arm nach hinten',null,'r'],['upper_back','zieht das Schulterblatt zurück',null,'r']],
    support:[['biceps','beugt den Ellbogen',null,'r'],['lower_back','hält den Rücken gerade']],
    hints:[['spine_upper','Rücken gerade','nicht verdrehen'],['shoulder_r','Schulter tief','nicht zum Ohr ziehen']]},
  deadbug:{
    active:[['abs','hält den unteren Rücken am Boden'],['obliques','verhindern das Verdrehen']],
    support:[['quads','halten das Bein in der Luft']],
    hints:[['spine_lower','Unterer Rücken','bleibt fest am Boden'],['ankle','Bein lang','knapp über dem Boden']]},
  goblet:{
    active:[['quads','Hauptarbeit'],['glutes','streckt die Hüfte']],
    support:[['adductors','arbeiten in der Tiefe mit'],['upper_back','hält die Brust oben']],
    hints:[['ankle','Fersen am Boden','Brust raus'],['knee','Knie Richtung Fußspitzen','Ellbogen innen vorbei']]},
  press:{
    active:[['delt_front','Hauptarbeit'],['delt_side','hebt den Arm'],['triceps','streckt den Arm']],
    support:[['upper_back','dreht das Schulterblatt mit'],['abs','verhindert das Hohlkreuz','Rumpf']],
    hints:[['spine_lower','Kein Hohlkreuz','Bauch und Po fest'],['wrist','Oben','Arme gestreckt über den Schultern']]},
  bridge1:{
    active:[['glutes','hebt das Becken, Standbein',null,'l'],['hamstrings','helfen beim Heben',null,'l']],
    support:[['obliques','halten das Becken waagerecht']],
    hints:[['hip','Becken waagerecht','nicht zur Seite kippen'],['ankle_l','Ferse drückt','in den Boden']]},
  row:{
    active:[['lats','zieht die Ellbogen nach hinten'],['upper_back','zieht die Schulterblätter zusammen']],
    support:[['biceps','beugt den Ellbogen'],['lower_back','hält den Rücken gerade'],['hamstrings','halten die Vorbeuge']],
    hints:[['spine_upper','Rücken gerade','kein Rundrücken'],['elbow','Ellbogen nach hinten','eng am Körper']]},
  lunge:{
    active:[['quads','Hauptarbeit, vorderes Bein'],['glutes','bringt dich zurück in den Stand']],
    support:[['hamstrings','bremsen die Bewegung'],['adductors','halten das Knie in der Spur']],
    hints:[['knee','Knie über Fuß','nicht nach innen'],['neck','Oberkörper aufrecht','nicht nach vorn fallen']]},
  sideplank:{
    active:[['obliques','halten die Hüfte oben']],
    support:[['glutes','seitliches Gesäß, hält das Becken'],['delt_side','stützt die Schulter'],['abs','hält die Linie','Rumpf']],
    hints:[['hip','Körper in Linie','Hüfte nicht absinken lassen'],['elbow_r','Ellbogen','unter der Schulter']]},
  kneepushup:{
    active:[['chest','Hauptarbeit'],['triceps','streckt den Arm']],
    support:[['delt_front','hebt den Arm nach vorn'],['abs','Linie Kopf bis Knie','Rumpf']],
    hints:[['hip','Hüfte in Linie','nicht abknicken'],['elbow','Ellbogen','etwa 45 Grad zum Körper']]},
  rdl:{
    active:[['hamstrings','Hauptarbeit, Dehnung hinten'],['glutes','strecken die Hüfte']],
    support:[['lower_back','hält den Rücken gerade'],['upper_back','hält die Schultern zurück']],
    hints:[['spine_upper','Rücken gerade','Bewegung aus der Hüfte'],['wrist','Hanteln nah','gleiten an den Beinen']]},
  squatbw:{
    active:[['quads','Hauptarbeit'],['glutes','streckt die Hüfte']],
    support:[['adductors','arbeiten in der Tiefe mit'],['abs','hält den Rücken lang','Rumpf']],
    hints:[['ankle','Fersen am Boden','Gewicht auf dem ganzen Fuß'],['knee','Knie Richtung Fußspitzen','nicht nach innen']]},
  bridge2w:{
    active:[['glutes','hebt das Becken mit Gewicht'],['hamstrings','helfen beim Heben']],
    support:[['abs','verhindert das Hohlkreuz','Rumpf']],
    hints:[['hip','Schulter–Hüfte–Knie','oben eine Linie'],['ankle','Über die Fersen','drücken']]},
  lungebw:{
    active:[['quads','Hauptarbeit, vorderes Bein'],['glutes','bringt dich zurück in den Stand']],
    support:[['hamstrings','bremsen die Bewegung'],['adductors','halten das Knie in der Spur']],
    hints:[['knee','Knie über Fuß','nicht nach innen'],['neck','Oberkörper aufrecht','nicht nach vorn fallen']]},
  sideplankknee:{
    active:[['obliques','halten die Hüfte oben']],
    support:[['glutes','seitliches Gesäß, hält das Becken'],['delt_side','stützt die Schulter']],
    hints:[['hip','Kopf–Hüfte–Knie','eine Linie'],['elbow_r','Ellbogen','unter der Schulter']]},
  deadbuglegs:{
    active:[['abs','hält den unteren Rücken am Boden']],
    support:[['obliques','verhindern das Verdrehen'],['quads','halten das Bein in der Luft']],
    hints:[['spine_lower','Unterer Rücken','bleibt fest am Boden'],['ankle','Bein lang','knapp über dem Boden']]},
  thruster:{
    active:[['quads','Kniebeuge'],['glutes','streckt die Hüfte'],['delt_front','drückt nach oben']],
    support:[['triceps','streckt den Arm'],['abs','hält den Rumpf fest','Rumpf']],
    hints:[['ankle','Fersen am Boden','Schwung aus den Beinen'],['wrist','In einem Zug','über den Kopf drücken']]},
  burpee:{
    active:[['quads','Hocke und Aufstehen'],['chest','Liegestütz']],
    support:[['triceps','streckt den Arm'],['abs','hält den Stütz','Rumpf'],['glutes','richtet auf']],
    hints:[['hip','Stütz gerade','Hüfte in Linie'],['knee','Ohne Sprung','sauber statt schnell']]},
  walk:{
    active:[],
    support:[['quads','locker'],['hamstrings','locker'],['calves','locker']],
    hints:[['neck','Aufrecht','ruhig durch die Nase atmen']]},
  hipflex:{
    active:[['quads','wird vorn gedehnt, gerader Schenkelmuskel',null,'r']],
    support:[['glutes','angespannt, schiebt das Becken vor',null,'r']],
    hints:[['hip_r','Becken vor','bis es vorn in der Hüfte zieht'],['neck','Oberkörper aufrecht','nicht ins Hohlkreuz']]},
  chest:{
    active:[['chest','wird gedehnt'],['delt_front','wird gedehnt']],
    support:[['upper_back','zieht die Schultern zurück']],
    hints:[['shoulder','Schultern','nach hinten-unten'],['spine_lower','Kein Hohlkreuz','Bauch fest']]}
};

// Kurzliste für Tabellen: aktive Muskeln, sonst unterstützende
function anatomyShort(k){
  const a=ANATOMY[k];if(!a)return '';
  const l=(a.active.length?a.active:a.support).map(m=>m[2]||MUSCLES[m[0]].short);
  return [...new Set(l)].join(', ');
}
