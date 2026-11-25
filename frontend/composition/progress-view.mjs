/** Percentage of completed weighted stages, never a countdown or a success flag. */
export function createProgressView({container,ring,value,detail,elapsed}){
 let percent=0,running=false,started=0,timer;
 function paint(){value.textContent=percent+'%';ring.style.setProperty('--progress',percent+'%');ring.setAttribute('aria-valuenow',String(percent));}
 function clock(){const seconds=Math.floor((Date.now()-started)/1000);elapsed.textContent=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');}
 function stop(){running=false;clearInterval(timer);clock();}
 return {
  start(){clearInterval(timer);running=true;started=Date.now();percent=1;container.hidden=false;container.setAttribute('data-state','running');detail.textContent='بدء التوليد';paint();clock();timer=setInterval(clock,1000);},
  update(event){if(!running)return;const next=Number(event.percent);if(!Number.isFinite(next)||next<percent)return;percent=Math.max(percent,Math.min(99,Math.floor(next)));if(event.detail)detail.textContent=event.detail;paint();},
  complete(){stop();percent=100;container.setAttribute('data-state','complete');detail.textContent='اكتملت المحاولة — النتائج أدناه';paint();},
  fail(){stop();container.setAttribute('data-state','failed');detail.textContent='توقفت المحاولة — راجع الرسالة أدناه';paint();}
 };
}
