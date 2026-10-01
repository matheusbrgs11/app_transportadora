import {useEffect,useState,type FormEvent} from 'react';
import {AlertTriangle,ArrowRight,RefreshCw} from 'lucide-react';
import type {Api,Client,Driver} from './api';
import {ErrorBox} from './ui';

type Call={id:string;coleta_id:string;cliente_nome:string;motorista_nome:string;motorista_id:string;estado:string;prioridade:string;prazo:string;versao:number;observacoes:string|null};
type Modality={id:string;nome:string;ativa:boolean};
type Suggestion=Driver&{situacao:string;distancia_km:number|null};

const labels:Record<string,string>={enviado:'Aguardando resposta',aceito:'Aceito',recusado:'Recusado',expirado:'Expirado',concluido:'Concluído',nao_atendido:'Não atendido',cancelado:'Cancelado'};
export default function Calls({api,onCollection}:{api:Api;onCollection:(id:string)=>void}){
 const [items,setItems]=useState<Call[]>([]),[clients,setClients]=useState<Client[]>([]),[drivers,setDrivers]=useState<Driver[]>([]),[modalities,setModalities]=useState<Modality[]>([]);
 const [suggestions,setSuggestions]=useState<Suggestion[]>([]),[clientId,setClientId]=useState(''),[driverId,setDriverId]=useState(''),[modalityId,setModalityId]=useState('');
 const [error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false),[query,setQuery]=useState('');
 const [reassignId,setReassignId]=useState(''),[newDriver,setNewDriver]=useState(''),[reason,setReason]=useState('');
 async function reload(){const response=await api<{items:Call[]}>('/chamados');setItems(response.items);}
 useEffect(()=>{Promise.all([api<{items:Driver[]}>('/motoristas'),api<{items:Modality[]}>('/modalidades'),api<{items:Call[]}>('/chamados')])
  .then(([d,m,c])=>{setDrivers(d.items.filter(x=>x.ativo));setModalities(m.items.filter(x=>x.ativa));setItems(c.items);}).catch(e=>setError(e.message));},[api]);
 useEffect(()=>{if(!query.trim()){setClients([]);return;}const timer=setTimeout(()=>api<{items:Client[]}>('/clientes?q='+encodeURIComponent(query)+'&ativo=true&limit=30')
  .then(r=>setClients(r.items)).catch(e=>setError(e.message)),250);return()=>clearTimeout(timer);},[api,query]);
 useEffect(()=>{if(!clientId){setSuggestions([]);return;}api<{items:Suggestion[]}>('/chamados/sugestoes/'+clientId)
  .then(r=>setSuggestions(r.items)).catch(e=>setError(e.message));},[api,clientId]);
 async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();if(!clientId||!driverId||!modalityId){setError('Escolha cliente, motorista e modalidade.');return;}
  const form=new FormData(e.currentTarget);setBusy(true);setError('');try{await api('/chamados',{method:'POST',body:JSON.stringify({
    id_local_dispositivo:crypto.randomUUID(),cliente_id:clientId,motorista_id:driverId,prioridade:form.get('prioridade'),
    prazo:new Date(String(form.get('prazo'))).toISOString(),observacoes:form.get('observacoes')||null,
    itens:[{modalidade_id:modalityId,quantidade:form.get('quantidade')?Number(form.get('quantidade')):null,
      quantidade_status:form.get('quantidade')?'confirmada':'a_conferir'}]})});
    setNotice('Chamado enviado. Acompanhe o aceite do motorista nesta lista.');setClientId('');setDriverId('');setQuery('');(e.target as HTMLFormElement).reset();await reload();
  }catch(err){setError((err as Error).message);}finally{setBusy(false);}}
 async function reassign(call:Call){if(!newDriver||!reason.trim()){setError('Escolha outro motorista e informe o motivo.');return;}
  setBusy(true);setError('');try{await api('/chamados/'+call.id+'/reatribuir',{method:'POST',body:JSON.stringify({versao:call.versao,motorista_id:newDriver,motivo:reason.trim()})});setNotice('Chamado reatribuído.');setReassignId('');setNewDriver('');setReason('');await reload();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <div className="calls-page"><ErrorBox message={error}/>{notice&&<p className="success-note" role="status">{notice}</p>}
  <section className="panel"><h2>Novo pedido fora da rota</h2><p>Escolha o cliente e o motorista. O aplicativo mostrará o pedido quando o motorista atualizar a rota.</p>
   <form onSubmit={submit} className="call-form"><label className="field"><span>Buscar cliente</span><input value={query} onChange={e=>{setQuery(e.target.value);setClientId('');}} placeholder="Nome ou CNPJ" required/></label>
    {clients.length>0&&<div className="call-choices" role="listbox" aria-label="Clientes encontrados">{clients.map(c=><button type="button" key={c.id} aria-selected={clientId===c.id} onClick={()=>{setClientId(c.id);setQuery(c.nome);setClients([]);}}>{c.nome} · {c.cidade}</button>)}</div>}
    <label className="field"><span>Modalidade</span><select value={modalityId} onChange={e=>setModalityId(e.target.value)} required><option value="">Selecione</option>{modalities.map(m=><option key={m.id} value={m.id}>{m.nome}</option>)}</select></label>
    <label className="field"><span>Volumes previstos (opcional)</span><input name="quantidade" type="number" min="0" max="2147483647"/></label>
    <label className="field"><span>Prioridade</span><select name="prioridade" defaultValue="normal"><option value="normal">Normal</option><option value="urgente">Urgente</option></select></label>
    <label className="field"><span>Atender até</span><input name="prazo" type="datetime-local" required/></label>
    <label className="field"><span>Motorista</span><select value={driverId} onChange={e=>setDriverId(e.target.value)} required><option value="">Selecione</option>{drivers.map(d=><option key={d.id} value={d.id}>{d.nome} · {d.tipo}</option>)}</select></label>
    {clientId&&<p className="call-suggestion">{suggestions.length?suggestions.map(s=><span key={s.id}>{s.nome}: {s.situacao==='recente'?`${s.distancia_km} km em linha reta`:'sem posição recente'} · {s.tipo}　</span>):'Nenhum motorista ativo encontrado.'}</p>}
    <label className="field call-wide"><span>Observações</span><textarea name="observacoes" maxLength={2000} rows={2} placeholder="Ex.: ponto de entrada, contato no local"/></label>
    <button className="primary" disabled={busy}>{busy?'Enviando…':'Enviar chamado'}<ArrowRight size={18}/></button>
   </form></section>
  <section className="panel"><div className="call-heading"><div><h2>Chamados</h2><p>O envio não significa aceite. Confirme o estado abaixo.</p></div><button className="secondary" onClick={()=>reload().catch(e=>setError(e.message))}><RefreshCw size={16}/>Atualizar</button></div>
   {items.length===0?<p>Nenhum chamado registrado.</p>:<div className="call-list">{items.map(call=><article className="call-card" key={call.id}>
    <div><strong>{call.cliente_nome}</strong><span>{labels[call.estado]||call.estado}{call.prioridade==='urgente'&&<b> · Urgente</b>}</span></div>
    <p>Motorista: {call.motorista_nome} · Prazo: {new Date(call.prazo).toLocaleString('pt-BR')}</p>
    {call.observacoes&&<p>{call.observacoes}</p>}
    <div className="call-actions"><button className="secondary" onClick={()=>onCollection(call.coleta_id)}>Ver histórico</button>{['enviado','recusado','aceito'].includes(call.estado)&&<button className="secondary" onClick={()=>{setReassignId(reassignId===call.id?'':call.id);setNewDriver('');setReason('');}}>Reatribuir</button>}</div>
    {reassignId===call.id&&<div className="call-reassign"><label className="field"><span>Novo motorista</span><select value={newDriver} onChange={e=>setNewDriver(e.target.value)}><option value="">Selecione</option>{drivers.filter(d=>d.id!==call.motorista_id).map(d=><option key={d.id} value={d.id}>{d.nome} · {d.tipo}</option>)}</select></label><label className="field"><span>Motivo</span><input value={reason} onChange={e=>setReason(e.target.value)} maxLength={1000}/></label><button className="primary" disabled={busy} onClick={()=>reassign(call)}>Confirmar reatribuição</button></div>}
   </article>)}</div>}
  </section><p className="call-note"><AlertTriangle size={16}/>A distância é aproximada e depende de localização confirmada e posição recente. Confirme com o motorista antes de alterar a rota.</p>
 </div>;
}
