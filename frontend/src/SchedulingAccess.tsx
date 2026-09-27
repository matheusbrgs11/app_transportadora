import {useState,type FormEvent} from 'react';
import type {Api} from './api';
import {ErrorBox,Field,Modal,SaveBar} from './ui';
export default function SchedulingAccess({api,onClose,onSave}:{api:Api;onClose:()=>void;onSave:()=>void}){
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 async function submit(e:FormEvent<HTMLFormElement>){
  e.preventDefault();const form=e.currentTarget;const data=new FormData(form);
  if(data.get('senha')!==data.get('confirmacao')){setError('As senhas precisam ser iguais.');return;}
  setBusy(true);setError('');
  try{await api('/usuarios',{method:'POST',body:JSON.stringify({nome:data.get('nome'),login:data.get('login'),senha:data.get('senha'),perfil:'agendamento'})});form.reset();onSave();}
  catch(e){setError((e as Error).message);}finally{setBusy(false);}
 }
 return <Modal title="Criar acesso de agendamento" subtitle="Acesso exclusivo à operação da sua empresa." onClose={()=>{if(!busy)onClose();}}>
 <form onSubmit={submit}><div className="modal-body"><p>Pode acompanhar motoristas, organizar rotas e agendar coletas para clientes existentes. Cadastro, alteração e desativação de clientes ficam com o administrador.</p>
 <ErrorBox message={error}/><Field label="Nome"><input name="nome" required maxLength={250}/></Field>
 <Field label="Usuário"><input name="login" required maxLength={150} autoComplete="off"/></Field>
 <Field label="Senha (mínimo 12 caracteres)"><input name="senha" type="password" required minLength={12} maxLength={256} autoComplete="new-password"/></Field>
 <Field label="Confirmar senha"><input name="confirmacao" type="password" required minLength={12} maxLength={256} autoComplete="new-password"/></Field>
 <p className="helper">A pessoa entra pelo mesmo painel, com o código da empresa e este usuário. Entregue as credenciais por um canal privado.</p>
 </div><SaveBar busy={busy} onClose={onClose} label="Criar acesso"/></form></Modal>;
}
