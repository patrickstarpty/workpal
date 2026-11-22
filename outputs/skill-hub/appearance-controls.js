let selectedTheme='fwd',selectedMode='system';
const systemAppearance=matchMedia('(prefers-color-scheme: dark)');
function applyAppearance(){
 const theme=appearanceThemes.find(t=>t.id===selectedTheme);
 const html=document.documentElement;
 const dark=selectedMode==='dark'||(selectedMode==='system'&&systemAppearance.matches);
 html.classList.toggle('dark',dark);html.classList.toggle('light',!dark);
 html.classList.toggle('theme-dark',dark);html.classList.toggle('theme-light',!dark);
 html.style.colorScheme=dark?'dark':'light';
 for(const attr of Array.from(html.attributes))if(attr.name==='data-theme'||attr.name.startsWith('data-theme-option-'))html.removeAttribute(attr.name);
 if(theme.id!=='default')html.dataset.theme=theme.id;
 for(const [name,value] of Object.entries(theme.attributes))if(value!==null)html.setAttribute(name,value);
 const declarations=mode=>Object.entries(theme.variables[mode]).map(([name,value])=>name+':'+value+';').join('');
 document.getElementById('workpal-theme').textContent=theme.css+'\n:root.theme-light{'+declarations('light')+'}\n:root.theme-dark{'+declarations('dark')+'}';
}
function decorateComponents(){
 root.querySelectorAll('button').forEach(b=>{
  b.dataset.slot='button';
  b.dataset.variant=b.classList.contains('primary')?'default':b.classList.contains('plain')?'outline':'ghost';
  b.dataset.size='sm';
 });
 root.querySelectorAll('.nav button').forEach(b=>{b.dataset.mc='nav-item';b.dataset.active=String(b.getAttribute('aria-current')==='page');});
 root.querySelectorAll('.panel,.squad-card,.skill-card').forEach(n=>n.dataset.slot='card');
 root.querySelectorAll('input').forEach(n=>n.dataset.slot='input');
 root.querySelectorAll('select').forEach(n=>n.dataset.slot='select-trigger');
}
root.addEventListener('change',event=>{
 if(event.target.id==='appearance-theme'){selectedTheme=event.target.value;applyAppearance();}
 if(event.target.id==='appearance-mode'){selectedMode=event.target.value;applyAppearance();}
});
root.addEventListener('keydown',event=>{
 if(event.key==='Escape'&&event.target.closest('.appearance-menu')){
  const menu=root.querySelector('.appearance-menu');menu.open=false;menu.querySelector('summary').focus();
 }
});
root.addEventListener('pointerdown',event=>{
 const menu=root.querySelector('.appearance-menu');
 if(menu.open&&!menu.contains(event.target))menu.open=false;
});
systemAppearance.addEventListener('change',()=>{if(selectedMode==='system')applyAppearance();});
applyAppearance();
