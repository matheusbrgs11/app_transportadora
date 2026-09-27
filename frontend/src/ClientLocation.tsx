import {useEffect,useState} from 'react';
import {type Api,type Client} from './api';
import {Modal,ErrorBox,Field,Loading} from './ui';
import {searchLink,embedLink} from './maps';
export default function ClientLocation({api,id,onClose,onSave}:{api:Api;id:string;onClose:()=>void;onSave:()=>void}){
 const [client,setClient]=useState<Client|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [latitude,setLatitude]=useState(''),[longitude,setLongitude]=useState(''),[source,setSource]=useState('cliente'),[reason,setReason]=useState(''),[showMap,setShowMap]=useState(false);
 useEffect(()=>{const c=new AbortController();api<Client>('/clientes/'+id,{signal:c.signal}).then(r=>{setClient(r);setLatitude(r.latitude==null?'':String(r.latitude));setLongitude(r.longitude==null?'':String(r.longitude));setSource(r.localizacao_fonte||'cliente');}).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>c.abort();},[api,id]);
 async function save(clear=false){if(!client)return;setBusy(true);setError('');try{await api(`/clientes/${id}/localizacao`,{method:'PUT',body:JSON.stringify({versao:client.localizacao_versao,latitude:clear?null:Number(latitude),longitude:clear?null:Number(longitude),fonte:clear?null:source,motivo:reason})});onSave();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 const candidate=client&&latitude!==''&&longitude!==''&&Number.isFinite(Number(latitude))&&Number.isFinite(Number(longitude))&&Math.abs(Number(latitude))<=90&&Math.abs(Number(longitude))<=180?{...client,latitude:Number(latitude),longitude:Number(longitude),localizacao_confirmada:true}:null;
 const embed=client?embedLink(candidate||client):null;
 return <Modal title="Conferir localização" subtitle={client?.nome} onClose={()=>{if(!busy)onClose();}}><div className="modal-body"><ErrorBox message={error}/>{!client?!error&&<Loading/>:<>
  <p>{[client.endereco,client.numero,client.bairro,client.cidade,client.estado].filter(Boolean).join(', ')}</p><p>{client.localizacao_confirmada?'Ponto confirmado':'Endereço ainda sem ponto confirmado'}</p>
  <a className="text-button" href={searchLink({...client,localizacao_confirmada:false})} target="_blank" rel="noreferrer">Pesquisar endereço no Google Maps</a>{candidate&&<p><a className="text-button" href={searchLink(candidate)} target="_blank" rel="noreferrer">Conferir coordenadas digitadas no mapa</a></p>}
  {embed&&<><button className="secondary" onClick={()=>setShowMap(x=>!x)}>Mostrar mapa</button>{showMap&&<iframe title="Localização cadastrada" src={embed} style={{width:'100%',height:300,border:0}} loading="lazy" referrerPolicy="strict-origin-when-cross-origin"/>}</>}
  <p className="helper">Use coordenadas fornecidas pelo cliente ou obtidas por GPS em campo e confira se apontam para a entrada de coleta. Não há geocodificação automática nesta etapa. Alterações valem para novas execuções; as já emitidas preservam o ponto anterior.</p>
  <form onSubmit={e=>{e.preventDefault();void save();}}><div className="form-grid">
   <Field label="Latitude"><input type="number" step="any" min="-90" max="90" required disabled={busy} value={latitude} onChange={e=>setLatitude(e.target.value)}/></Field>
   <Field label="Longitude"><input type="number" step="any" min="-180" max="180" required disabled={busy} value={longitude} onChange={e=>setLongitude(e.target.value)}/></Field>
   <Field label="Origem das coordenadas"><select disabled={busy} value={source} onChange={e=>setSource(e.target.value)}><option value="cliente">Fornecidas pelo cliente</option><option value="gps_campo">GPS em campo</option></select></Field>
   <Field label="Como o ponto foi conferido / motivo da alteração"><textarea required maxLength={1000} value={reason} disabled={busy} onChange={e=>setReason(e.target.value)}/></Field>
  </div><button className="primary" disabled={busy||!reason.trim()}>Confirmar ponto</button><button type="button" className="secondary" disabled={busy||!client.localizacao_confirmada||!reason.trim()} onClick={()=>save(true)}>Remover ponto confirmado</button></form>
 </>}</div></Modal>;
}
