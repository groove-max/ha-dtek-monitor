/* Fictional compact-card example contributed in PR #12. */
const prefix='demo';
window.card=document.createElement('dtek-outage-card');
card.setConfig({entity:'binary_sensor.'+prefix+'_power',status_entity:'sensor.'+prefix+'_schedule_status',updated_entity:'sensor.'+prefix+'_dtek_last_update',title:'Мій дім'});
const makeDay=(date,tomorrow=false)=>({date,slots:Array.from({length:48},(_,i)=>({label:String(Math.floor(i/2)).padStart(2,'0')+':'+(i%2?'30':'00'),offset:'+0300'})),rows:[{id:'GPV1.1',label:'Черга 1.1',home:false,cells:Array(48).fill('clear')},{id:'GPV2.2',label:'Черга 2.2',home:true,cells:Array.from({length:48},(_,i)=>tomorrow?'unknown':((i>=15&&i<23)||(i>=26&&i<29)||(i>=36&&i<44))?'outage':'clear')}]});
window.demoData={status:'ready',days:[makeDay('2026-10-23'),makeDay('2026-10-24',true)]};
window.demoHass={language:'uk',states:{['binary_sensor.'+prefix+'_power']:{state:'on',attributes:{}},['sensor.'+prefix+'_schedule_status']:{state:'current',attributes:{}},['sensor.'+prefix+'_dtek_last_update']:{state:'2026-10-23T22:06:00+03:00'}},callWS:async()=>window.demoData};
card.hass=window.demoHass;document.querySelector("main").append(card);
