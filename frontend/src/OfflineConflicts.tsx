import {useEffect,useState} from 'react';
import {type Api} from './api';
import {ErrorBox,Field,Modal} from './ui';
type RecordConflict={id:string;motorista_nome:string;cliente_nome:string;status:string;criado_em:string;resolucao:string|null;resolvido_nome:string|null;payload:Record<string,unknown>};
type Collection={id:string;status:string;cliente_nome:string;motorista_nome:string;data_referencia:string};
export default function OfflineConflicts({api,onClose}:{api:Api;onClose:()=>void}){
 const [mods,setMods]=useState<Record<string,string>>({});
 useEffect(()=>{const c=new AbortController();api<{items:{id:string;nome:string}[]}>('/modalidades',{signal:c.signal}).then(r=>setMods(Object.fromEntries(r.items.map(m=>[m.id,m.nome])))).catch(()=>{});return()=>c.abort();},[api]);
 const [items,setItems]=useState<RecordConflict[]>([]),[total,setTotal]=useState(0),[page,setPage]=useState(0),[status,setStatus]=useState('aberto');
 const [revision,setRevision]=useState(0),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [selected,setSelected]=useState<RecordConflict|null>(null),[reason,setReason]=useState(''),[collection,setCollection]=useState('');
 const [candidates,setCandidates]=useState<Collection[]>([]),[lookupError,setLookupError]=useState(''),[more,setMore]=useState(false);
 useEffect(()=>{const ctrl=new AbortController();setLoading(true);setSelected(null);setError('');api<{items:RecordConflict[];total:number}>(`/conflitos?status=${status}&limit=20&offset=${page*20}`,{signal:ctrl.signal})
  .then(r=>{setItems(r.items);setTotal(r.total);}).catch(e=>{if(e.name!=='AbortError')setError(e.message);}).finally(()=>{if(!ctrl.signal.aborted)setLoading(false);});return()=>ctrl.abort();},[api,status,page,revision]);
 useEffect(()=>{setCandidates([]);setLookupError('');setMore(false);const ctrl=new AbortController();if(selected&&typeof selected.payload.cliente_id==='string')api<{items:Collection[];total:number}>('/coletas?limit=200&cliente_id='+encodeURIComponent(selected.payload.cliente_id),{signal:ctrl.signal})
  .then(r=>{setCandidates(r.items);setMore(r.total>r.items.length);}).catch(e=>{if(e.name!=='AbortError')setLookupError(e.message);});return()=>ctrl.abort();},[api,selected]);
 async function resolve(){if(!selected)return;setBusy(true);setError('');try{await api(`/conflitos/${selected.id}/resolver`,{method:'POST',body:JSON.stringify({motivo:reason,coleta_id:collection||null})});setRevision(x=>x+1);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <Modal title="Conferências de registros offline" subtitle="Compare o registro do aparelho com as coletas antes de encerrar a conferência. O conteúdo original é preservado." wide onClose={()=>{if(!busy)onClose();}}><div className="modal-body">
  <Field label="Situação"><select disabled={busy} value={status} onChange={e=>{setStatus(e.target.value);setPage(0);}}><option value="aberto">Aguardando conferência</option><option value="resolvido">Conferidos</option></select></Field>
  <button className="secondary" disabled={busy||loading} onClick={()=>setRevision(x=>x+1)}>Atualizar</button><ErrorBox message={error}/>
  {loading?<p>Carregando…</p>:<><p>{total} registros</p>{items.map(r=><button className="secondary" key={r.id} disabled={busy} onClick={()=>{setSelected(r);setReason('');setCollection('');}}>{r.cliente_nome} · {r.motorista_nome} · {new Date(r.criado_em).toLocaleString('pt-BR')}</button>)}
  <p><button className="secondary" disabled={busy||page===0} onClick={()=>setPage(x=>x-1)}>Anterior</button> Página {page+1} <button className="secondary" disabled={busy||(page+1)*20>=total} onClick={()=>setPage(x=>x+1)}>Próxima</button></p></>}
  {selected&&<section><h3>{selected.cliente_nome} · {selected.motorista_nome}</h3>
   <p>Registro no aparelho: {String(selected.payload.concluida_em||'Data não informada')}</p>
   <p>{selected.payload.status==='nao_atendida'?'Não atendimento':'Coleta'} · {String(selected.payload.motivo||selected.payload.observacoes||'Sem observações')}</p>
   {Array.isArray(selected.payload.itens)&&<p>Volumes registrados: {selected.payload.itens.map((item:unknown,i:number)=>{const x=item&&typeof item==='object'?item as Record<string,unknown>:{};return <span key={i}>{mods[String(x.modalidade_id)]||'Modalidade não localizada'}: {x.quantidade==null?'a conferir':String(x.quantidade)}{i< (selected.payload.itens as unknown[]).length-1?' · ':''}</span>;})}</p>}
   {selected.status==='resolvido'?<p>Conferido por {selected.resolvido_nome}: {selected.resolucao}</p>:<form onSubmit={e=>{e.preventDefault();void resolve();}}>
    <p className="helper">Este encerramento registra a decisão. Se for necessário corrigir volumes ou cadastrar uma coleta, faça isso em Coletas antes de vincular o resultado aqui.</p>
    <ErrorBox message={lookupError}/>{more&&<p>Exibindo as 200 coletas mais recentes. Consulte o histórico para registros anteriores.</p>}
    <Field label="Coleta correspondente (quando houver)"><select disabled={busy} value={collection} onChange={e=>setCollection(e.target.value)}><option value="">Encerrar sem vincular coleta — explicar no motivo</option>{candidates.map(c=><option key={c.id} value={c.id}>{new Date(c.data_referencia).toLocaleString('pt-BR')} · {c.motorista_nome} · {c.status}</option>)}</select></Field>
    <Field label="Decisão e motivo obrigatórios"><textarea disabled={busy} value={reason} onChange={e=>setReason(e.target.value)} required maxLength={2000}/></Field>
    <button className="primary" disabled={busy||!reason.trim()}>Encerrar conferência e preservar original</button>
   </form>}
  </section>}
 </div></Modal>;
}
