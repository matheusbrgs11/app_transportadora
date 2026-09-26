import {useEffect,useState} from 'react';
import {type Api,type Route,type Driver} from './api';
import {ErrorBox,Field,Modal} from './ui';

type Visit={coleta_id:string;nome:string;status:string;versao_coleta:number;motorista_id:string;tentativa:number};
type Run={paradas:Visit[];progresso:Record<string,number>};
const labels:Record<string,string>={agendada:'Pendentes',concluida:'Concluídas',nao_atendida:'Não atendidas',cancelada:'Canceladas'};
export default function DailyOperations({api,route,onClose}:{api:Api;route:Route;onClose:()=>void}){
 const [date,setDate]=useState(()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;});
 const [run,setRun]=useState<Run|null>(null),[drivers,setDrivers]=useState<Driver[]>([]);
 const [error,setError]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[revision,setRevision]=useState(0);
 const [exception,setException]=useState<{operar:boolean;motivo:string}|null>(null);
 const [loaded,setLoaded]=useState(false);
 const [reason,setReason]=useState(''),[operate,setOperate]=useState(false);
 const [action,setAction]=useState<{visit:Visit;kind:'transferir'|'revisitas';id:string}|null>(null);
 const [target,setTarget]=useState('');
 useEffect(()=>{const ctrl=new AbortController();setLoading(true);setLoaded(false);setRun(null);setException(null);setAction(null);setError('');
  Promise.all([api<{execucao:Run|null;excecao:typeof exception}>(`/rotas/${route.id}/execucoes?data=${date}`,{signal:ctrl.signal}),api<{items:Driver[]}>('/motoristas',{signal:ctrl.signal})])
   .then(([result,d])=>{setLoaded(true);setRun(result.execucao);setException(result.excecao);setDrivers(d.items);})
   .catch(e=>{if(e.name!=='AbortError')setError(e.message);}).finally(()=>{if(!ctrl.signal.aborted)setLoading(false);});return()=>ctrl.abort();
 },[api,route.id,date,revision]);
 async function mutate(path:string,method:string,body?:object){setBusy(true);setError('');try{await api(path,{method,body:body?JSON.stringify(body):undefined});setReason('');setAction(null);setRevision(x=>x+1);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <Modal title={'Operação · '+route.nome} subtitle="Acompanhe o dia e registre alterações com motivo." wide onClose={()=>{if(!busy)onClose();}}><div className="modal-body">
  <Field label="Data da operação"><input type="date" required value={date} disabled={busy} onChange={e=>{if(e.target.value)setDate(e.target.value);}}/></Field>
  <button className="secondary" disabled={busy||loading} onClick={()=>setRevision(x=>x+1)}>Atualizar andamento</button>
  <ErrorBox message={error}/>{loading?<p>Carregando operação…</p>:!loaded?<button className="secondary" onClick={()=>setRevision(x=>x+1)}>Tentar novamente</button>:<>
  {!run?<><p>{exception?`${exception.operar?'Operação extra autorizada':'Operação suspensa'}: ${exception.motivo}`:'Segue os dias do planejamento recorrente.'}</p>
   <button className="primary" disabled={busy} onClick={()=>mutate(`/rotas/${route.id}/execucoes?data=${date}`,'POST')}>Preparar atendimentos desta data</button>
   <form onSubmit={e=>{e.preventDefault();void mutate(`/rotas/${route.id}/excecoes/${date}`,'PUT',{operar:operate,motivo:reason});}}><h3>Exceção por data</h3>
    <Field label="Funcionamento"><select value={String(operate)} disabled={busy} onChange={e=>setOperate(e.target.value==='true')}><option value="false">Suspender (feriado ou pausa)</option><option value="true">Autorizar operação nesta data</option></select></Field>
    <Field label="Motivo obrigatório"><input required maxLength={1000} value={reason} disabled={busy} onChange={e=>setReason(e.target.value)}/></Field><button className="secondary" disabled={busy||!reason.trim()}>Salvar exceção</button>
   </form></>:<><p>{Object.entries(run.progresso).map(([k,v])=>`${labels[k]}: ${v}`).join(' · ')}</p><p className="helper">Transferências valem para atendimentos pendentes. Revisitas criam uma nova tentativa nesta mesma data; o registro anterior é preservado. Cancelamentos ficam em Coletas.</p>
   {run.paradas.map(v=><article className="route-card" key={v.coleta_id}><h3>{v.nome} · tentativa {v.tentativa}</h3><p>{labels[v.status]} · {drivers.find(d=>d.id===v.motorista_id)?.nome||'Motorista'}</p>
    <button className="secondary" disabled={busy} onClick={()=>{setAction({visit:v,kind:v.status==='agendada'?'transferir':'revisitas',id:crypto.randomUUID()});setReason('');setTarget('');}}>{v.status==='agendada'?'Transferir atendimento':'Criar revisita'}</button></article>)}
   {action&&<form onSubmit={e=>{e.preventDefault();void mutate(`/coletas/${action.visit.coleta_id}/${action.kind}`,'POST',{versao:action.visit.versao_coleta,motivo:reason,...(action.kind==='transferir'?{motorista_id:target}:{id_local_dispositivo:action.id})});}}>
    <h3>{action.kind==='transferir'?'Transferir':'Revisitar'} · {action.visit.nome}</h3>
    {action.kind==='transferir'&&<Field label="Novo motorista"><select required value={target} disabled={busy} onChange={e=>setTarget(e.target.value)}><option value="">Selecione</option>{drivers.filter(d=>d.ativo&&d.id!==action.visit.motorista_id).map(d=><option key={d.id} value={d.id}>{d.nome}</option>)}</select></Field>}
    <Field label="Motivo obrigatório"><input required maxLength={1000} disabled={busy} value={reason} onChange={e=>setReason(e.target.value)}/></Field>
    <button className="primary" disabled={busy||!reason.trim()}>Confirmar {action.kind==='transferir'?'transferência':'revisita'}</button><button type="button" className="secondary" disabled={busy} onClick={()=>setAction(null)}>Voltar</button>
   </form>}</>}
  </>}
 </div></Modal>;
}
