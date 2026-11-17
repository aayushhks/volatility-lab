'use strict';
let fixtures,side='call',tab='accepted',limit=8,current=[],visible=[];
const $=id=>document.getElementById(id);
const common={paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{family:'DM Sans, sans-serif',color:'#8d9587',size:10},margin:{l:48,r:22,t:18,b:42},xaxis:{gridcolor:'#f0f2eb',zeroline:false},yaxis:{gridcolor:'#f0f2eb',zeroline:false,ticksuffix:'%'},showlegend:false};
const config={responsive:true,displayModeBar:false};
function draw(){
 const source=fixtures[$('scenario').value],spread=+$('spread').value/100,horizon=+$('horizon').value;
 $('spread-value').textContent=Math.round(spread*100)+'%';$('horizon-value').textContent=horizon+' days';
 $('scenario-note').textContent={'Balanced':'A gentle smile with a modest downside skew.','Steep skew':'Higher implied volatility on the downside.','Short-term stress':'Elevated near-term volatility that fades with time.'}[$('scenario').value];
 current=source.filter(x=>x.kind===side && x.days<=horizon).map(x=>({...x}));
 for(const x of current){if(x.status==='accepted'&&x.relative_spread>spread){x.status='rejected';x.reason='Spread exceeds threshold';}}
 visible=current.filter(x=>x.status==='accepted');
 const days=[...new Set(visible.map(x=>x.days))].sort((a,b)=>a-b),strikes=[...new Set(visible.map(x=>x.strike))].sort((a,b)=>a-b);
 const atm=visible.filter(x=>x.days===days[0]).sort((a,b)=>Math.abs(a.strike-100)-Math.abs(b.strike-100))[0];
 $('accepted').textContent=visible.length;$('atm').textContent=atm?(atm.iv*100).toFixed(1)+'%':'—';$('expiries').textContent=days.length;
 $('error').textContent=visible.length?Math.max(...visible.map(x=>x.repricing_error)).toExponential(1):'—';
 $('atm-note').textContent=atm?`strike $${atm.strike} · ${atm.days}-day expiry`:'No accepted quotes';
 const grid=days.map(d=>strikes.map(k=>{const x=visible.find(x=>x.days===d&&x.strike===k);return x?x.iv*100:null;}));
 renderSurface(strikes.map(x=>x/100),days,grid);
 const previous=+$('slice').value;$('slice').replaceChildren(...days.map(d=>new Option(d+' days',d)));if(days.includes(previous))$('slice').value=previous;
 drawSmile();
 const term=days.map(d=>visible.filter(x=>x.days===d).sort((a,b)=>Math.abs(a.strike-100)-Math.abs(b.strike-100))[0]);
 Plotly.react('term',[{x:term.map(x=>x.days),y:term.map(x=>x.iv*100),type:'scatter',mode:'lines+markers',line:{color:'#82936a',width:2},marker:{size:5},fill:'tozeroy',fillcolor:'rgba(168,187,137,.08)',hovertemplate:'%{x} days<br>IV %{y:.2f}%<extra></extra>'}],{...common,xaxis:{...common.xaxis,title:{text:'Days to expiry',font:{size:10}}},yaxis:{...common.yaxis,rangemode:'normal',range:term.length?[Math.min(...term.map(x=>x.iv*100))-1,Math.max(...term.map(x=>x.iv*100))+1]:undefined}},config);
 table();
}
function drawSmile(){const sl=visible.filter(x=>x.days===+$('slice').value).sort((a,b)=>a.strike-b.strike);Plotly.react('smile',[{x:sl.map(x=>x.strike/100),y:sl.map(x=>x.iv*100),type:'scatter',mode:'lines+markers',line:{color:'#9285b7',width:2},marker:{size:5},hovertemplate:'Strike / spot %{x:.2f}<br>IV %{y:.2f}%<extra></extra>'}],{...common,xaxis:{...common.xaxis,title:{text:'Strike / spot',font:{size:10}}}},config);}
function table(){const rows=current.filter(x=>x.status===(tab==='accepted'?'accepted':'rejected'));$('row-count').textContent=rows.length+' quotes';$('rows').replaceChildren(...rows.slice(0,limit).map(x=>{const tr=document.createElement('tr');for(const val of ['$'+x.strike,x.days,x.kind,Number(x.bid).toFixed(3),Number(x.ask).toFixed(3),x.status==='accepted'?(x.iv*100).toFixed(2)+'%':x.reason]){const td=document.createElement('td');td.textContent=val;tr.append(td);}return tr;}));$('table-note').textContent=`Showing ${Math.min(limit,rows.length)} of ${rows.length} · synthetic quotes`;$('more').hidden=limit>=rows.length;}
function save(){const fields=['strike','days','kind','bid','ask','iv','relative_spread','repricing_error','status','reason'];const quote=x=>'"'+String(x??'').replaceAll('"','""')+'"';const csv=[fields.join(','),...current.map(x=>fields.map(f=>quote(x[f])).join(','))].join('\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download='synthetic-volatility-audit.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),500);}
for(const id of ['scenario','spread','horizon'])$(id).addEventListener('input',()=>{limit=8;draw();});
for(const id of ['call','put'])$(id).onclick=()=>{side=id;for(const x of ['call','put'])$(x).setAttribute('aria-pressed',String(x===id));draw();};
for(const [id,value] of [['valid-tab','accepted'],['invalid-tab','rejected']])$(id).onclick=()=>{tab=value;limit=8;$('valid-tab').setAttribute('aria-pressed',String(value==='accepted'));$('invalid-tab').setAttribute('aria-pressed',String(value==='rejected'));table();};
$('slice').onchange=drawSmile;$('export').onclick=save;$('more').onclick=()=>{limit+=20;table();};
$('reset').onclick=()=>{angle=-.65;elevation=.65;zoom=1;paintSurface();};
$('method').onclick=$('method2').onclick=()=>$('dialog').showModal();$('close').onclick=()=>$('dialog').close();
fetch('data.json').then(r=>{if(!r.ok)throw Error('Cannot load fixtures');return r.json();}).then(x=>{fixtures=x;draw();}).catch(e=>{$('surface').textContent='Unable to load demo: '+e.message;});

// Software-rendered 3D surface: no WebGL/GPU requirement.
let surfaceData,angle=-.65,elevation=.65,zoom=1;
const canvas=document.createElement('canvas');canvas.style.cssText='width:100%;height:100%;display:block;touch-action:none;cursor:grab';$('surface').append(canvas);
let dragging=false,oldX=0,oldY=0;
canvas.addEventListener('pointerdown',e=>{dragging=true;oldX=e.clientX;oldY=e.clientY;canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointermove',e=>{if(!dragging)return;angle+=(e.clientX-oldX)*.008;elevation=Math.max(.2,Math.min(1.3,elevation+(e.clientY-oldY)*.005));oldX=e.clientX;oldY=e.clientY;paintSurface();});
canvas.addEventListener('pointerup',()=>dragging=false);canvas.addEventListener('pointercancel',()=>dragging=false);
canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.6,Math.min(1.5,zoom-e.deltaY*.001));paintSurface();},{passive:false});
new ResizeObserver(()=>paintSurface()).observe($('surface'));
function renderSurface(xs,ys,zs){surfaceData={xs,ys,zs};paintSurface();}
function paintSurface(){
 if(!surfaceData)return;
 const {xs,ys,zs}=surfaceData,values=zs.flat().filter(x=>x!==null);if(!values.length)return;
 const w=canvas.clientWidth,h=canvas.clientHeight,dpr=window.devicePixelRatio||1;canvas.width=w*dpr;canvas.height=h*dpr;
 const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);
 const zmin=Math.floor(Math.min(...values)/5)*5-2,zmax=Math.ceil(Math.max(...values)/5)*5+2;
 const scale=Math.min(w/3.5,h/2.4)*zoom;
 const project=(x,y,z)=>{let rx=x*Math.cos(angle)-y*Math.sin(angle),ry=x*Math.sin(angle)+y*Math.cos(angle);return [w*.47+rx*scale,h*.63+(ry*Math.sin(elevation)-z*Math.cos(elevation))*scale];};
 const pos=(i,j,z)=>project(-1+2*i/Math.max(1,xs.length-1),-.7+1.4*(ys[j]-ys[0])/Math.max(1,ys.at(-1)-ys[0]),(z-zmin)/(zmax-zmin));
 function line(a,b,col='#e0e5d8'){ctx.strokeStyle=col;ctx.lineWidth=.7;ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();}
 ctx.font='10px DM Sans, sans-serif';ctx.fillStyle='#8b9582';
 for(let i=0;i<xs.length;i+=2){line(pos(i,0,zmin),pos(i,ys.length-1,zmin));const p=pos(i,0,zmin);ctx.fillText(xs[i].toFixed(2),p[0]-10,p[1]+18);}
 for(let j=0;j<ys.length;j++){line(pos(0,j,zmin),pos(xs.length-1,j,zmin));const p=pos(xs.length-1,j,zmin);ctx.fillText(ys[j]+'d',p[0]+8,p[1]+4);}
 for(let z=Math.ceil(zmin/5)*5;z<=zmax;z+=5){const p=pos(0,ys.length-1,z);line(p,pos(xs.length-1,ys.length-1,z),'#edf0e8');ctx.fillText(z+'%',p[0]-31,p[1]+3);}
 line(pos(0,ys.length-1,zmin),pos(0,ys.length-1,zmax));
 const cells=[];
 for(let j=0;j<ys.length-1;j++)for(let i=0;i<xs.length-1;i++){
  const zz=[zs[j][i],zs[j][i+1],zs[j+1][i+1],zs[j+1][i]];if(zz.some(x=>x===null))continue;
  cells.push({p:[pos(i,j,zz[0]),pos(i+1,j,zz[1]),pos(i+1,j+1,zz[2]),pos(i,j+1,zz[3])],v:zz.reduce((a,b)=>a+b)/4,depth:(-1+2*(i+.5)/(xs.length-1))*Math.sin(angle)+(-.7+1.4*((ys[j]+ys[j+1])/2-ys[0])/Math.max(1,ys.at(-1)-ys[0]))*Math.cos(angle)});
 }
 cells.sort((a,b)=>a.depth-b.depth);
 for(const c of cells){const t=(c.v-zmin)/(zmax-zmin),lo=[215,227,190],hi=[115,98,157];ctx.fillStyle=`rgb(${lo.map((a,i)=>Math.round(a+(hi[i]-a)*t)).join(',')})`;ctx.strokeStyle='rgba(89,95,91,.25)';ctx.lineWidth=.7;ctx.beginPath();ctx.moveTo(...c.p[0]);c.p.slice(1).forEach(p=>ctx.lineTo(...p));ctx.closePath();ctx.fill();ctx.stroke();}
 ctx.fillStyle='#86917c';ctx.font='11px DM Sans, sans-serif';ctx.fillText('Strike / spot',w*.29,h-17);ctx.fillText('Days to expiry',w*.68,h-17);
 const gradient=ctx.createLinearGradient(0,h*.24,0,h*.76);gradient.addColorStop(0,'#73629d');gradient.addColorStop(1,'#d7e3be');ctx.fillStyle=gradient;ctx.fillRect(w-50,h*.24,9,h*.52);ctx.fillStyle='#8b9582';ctx.font='10px DM Sans, sans-serif';ctx.fillText(zmax.toFixed(0)+'%',w-34,h*.25);ctx.fillText(zmin.toFixed(0)+'%',w-34,h*.76);ctx.fillText('IV',w-49,h*.20);
}
