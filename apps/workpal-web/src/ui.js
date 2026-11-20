export const text = value => document.createTextNode(String(value));
export function el(tag, value, attrs={}) {
 const node=document.createElement(tag); if(value!==undefined)node.append(text(value));
 for(const [key,val] of Object.entries(attrs))node.setAttribute(key,val);
 return node;
}
export function openDialog(content,{returnFocus,label}={}) {
 const dialog=el('dialog');dialog.append(content);document.body.append(dialog);
 if(label)dialog.setAttribute('aria-label',label);
 dialog.addEventListener('close',()=>{dialog.remove();returnFocus?.focus();},{once:true});
 dialog.showModal();return dialog;
}
