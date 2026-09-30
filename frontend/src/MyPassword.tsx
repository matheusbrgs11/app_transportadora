import {useState,type FormEvent} from 'react';
import type {Api} from './api';
import {ErrorBox,Field,Modal,SaveBar} from './ui';
export default function MyPassword({api,onClose,onChanged}:{api:Api;onClose:()=>void;onChanged:()=>void}){
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();const data=new FormData(e.currentTarget);if(data.get('nova_senha')!==data.get('confirmacao')){setError('As senhas precisam ser iguais.');return;}setBusy(true);setError('');try{await api('/auth/senha',{method:'POST',body:JSON.stringify({senha_atual:data.get('senha_atual'),nova_senha:data.get('nova_senha')})});onChanged();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <Modal title="Minha senha" subtitle="Após a troca, entre novamente em todos os aparelhos." onClose={()=>{if(!busy)onClose();}}><form onSubmit={submit}><div className="modal-body"><ErrorBox message={error}/><Field label="Senha atual"><input name="senha_atual" type="password" required autoComplete="current-password"/></Field><Field label="Nova senha (mínimo 12 caracteres)"><input name="nova_senha" type="password" required minLength={12} maxLength={256} autoComplete="new-password"/></Field><Field label="Confirmar nova senha"><input name="confirmacao" type="password" required minLength={12} maxLength={256} autoComplete="new-password"/></Field></div><SaveBar busy={busy} onClose={onClose} label="Trocar senha"/></form></Modal>;
}
