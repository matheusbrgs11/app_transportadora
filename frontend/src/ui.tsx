import { useEffect, useRef, type ReactNode } from 'react';
import { X, AlertCircle, LoaderCircle, ArrowRight } from 'lucide-react';
export function ErrorBox({message}:{message:string}){return message?<div className="error" role="alert"><AlertCircle size={19}/><span>{message}</span></div>:null;}
export function Loading(){return <div className="loading" role="status"><LoaderCircle className="spin" size={20}/>Carregando…</div>;}
export function Empty({title,text,action,onAction}:{title:string;text:string;action?:string;onAction?:()=>void}){return <div className="empty"><div className="empty-symbol"><ArrowRight size={24}/></div><h3>{title}</h3><p>{text}</p>{action&&<button className="primary" onClick={onAction}>{action}</button>}</div>;}
export function Badge({active}:{active:boolean}){return <span className={'badge '+(active?'green':'gray')}><i/>{active?'Ativo':'Inativo'}</span>;}
export function Modal({title,subtitle,children,onClose,wide=false}:{title:string;subtitle?:string;children:ReactNode;onClose:()=>void;wide?:boolean}){
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{ref.current?.showModal();},[]);
 return <dialog ref={ref} className={wide?'wide':''} onCancel={e=>{e.preventDefault();onClose();}} aria-label={title}>
  <header className="modal-head"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div><button className="icon-button" aria-label="Fechar" onClick={onClose}><X size={22}/></button></header>{children}
 </dialog>;
}
export function Field({label,children,wide=false}:{label:string;children:ReactNode;wide?:boolean}){return <label className={'field '+(wide?'full':'')}><span>{label}</span>{children}</label>;}
export function SaveBar({busy,onClose,label='Salvar cadastro'}:{busy:boolean;onClose:()=>void;label?:string}){return <footer className="modal-footer"><button type="button" className="secondary" onClick={onClose} disabled={busy}>Cancelar</button><button className="primary" type="submit" disabled={busy}>{busy?<><LoaderCircle className="spin" size={17}/>Salvando…</>:label}</button></footer>;}
