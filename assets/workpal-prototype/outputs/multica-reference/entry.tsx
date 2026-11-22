import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Button} from '@multica/ui/components/ui/button';
import {TooltipProvider} from '@multica/ui/components/ui/tooltip';
import {Dialog,DialogContent,DialogTitle} from '@multica/ui/components/ui/dialog';
import {PropertyPicker,PickerItem,PickerEmpty} from '../../../multica/packages/views/issues/components/pickers/property-picker';
import './style.css';
const names=['Backlog','To do','In progress','In review','Done','Blocked'];
function App(){const [open,setOpen]=useState(false),[status,setStatus]=useState('To do'),[query,setQuery]=useState(''),[dialog,setDialog]=useState(false);const matches=names.filter(n=>n.toLowerCase().includes(query.toLowerCase()));return <TooltipProvider><main style={{padding:32}}><h1>Issue properties</h1><div style={{display:'flex',gap:12,marginTop:20}}><PropertyPicker open={open} onOpenChange={setOpen} searchable onSearchChange={setQuery} searchPlaceholder="Search…" align="start" width="w-64" trigger={<span>{status}</span>}>{matches.map(n=><PickerItem key={n} selected={n===status} onClick={()=>{setStatus(n);setOpen(false)}}>{n}</PickerItem>)}{!matches.length&&<PickerEmpty/>}</PropertyPicker><Button variant="outline" size="sm">Assignee</Button><Button variant="outline" size="sm" disabled>Disabled</Button><Button onClick={()=>setDialog(true)}>Open dialog</Button></div><Dialog open={dialog} onOpenChange={setDialog}><DialogContent><DialogTitle>Confirm workflow change</DialogTitle><p>Changing status can hand work to the next owner.</p><Button onClick={()=>setDialog(false)}>Cancel</Button></DialogContent></Dialog></main></TooltipProvider>}
createRoot(document.getElementById('root')!).render(<App/>);
