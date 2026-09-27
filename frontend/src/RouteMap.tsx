import {useEffect,useState} from 'react';
import {type Api,type Route,type Stop} from './api';
import {Modal,Loading,ErrorBox} from './ui';
import {mapsLink,embedLink,confirmed} from './maps';
export default function RouteMap({api,id,onClose}:{api:Api;id:string;onClose:()=>void}){
 const [route,setRoute]=useState<Route|null>(null),[error,setError]=useState(''),[selected,setSelected]=useState(0),[showMap,setShowMap]=useState(false);
 useEffect(()=>{const c=new AbortController();api<Route>('/rotas/'+id,{signal:c.signal}).then(setRoute).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>c.abort();},[api,id]);
 const stops:Stop[]=route?.paradas||[],stop=stops[selected],previous=selected?stops[selected-1]:undefined;
 const embed=stop?embedLink(stop,previous):null;
 return <Modal title="Destinos e sequência da rota" subtitle={route?.nome} wide onClose={onClose}><div className="modal-body"><ErrorBox message={error}/>{!route?!error&&<Loading/>:<>
  <p>Planejamento recorrente atual. {stops.filter(confirmed).length} de {stops.length} pontos confirmados. O trajeto é consultado por trecho, mantendo todas as paradas da sequência.</p>
  <p className="helper">Pontos não confirmados serão pesquisados pelo endereço: confira o resultado no Google Maps. Os trajetos não consideram restrições específicas de caminhões ou motos.</p>
  <ol>{stops.map((s,i)=><li key={s.cliente_id}><button className="text-button" onClick={()=>setSelected(i)} aria-current={selected===i?'step':undefined}>{s.nome} · {confirmed(s)?'Ponto confirmado':'Conferir endereço'}{s.cliente_ativo===false?' · Inativo':''}</button></li>)}</ol>
  {stop&&<><h3>{selected?`Trecho ${selected} → ${selected+1}`:'Primeiro destino'} · {stop.nome}</h3><a href={mapsLink(stop,previous)} className="secondary" target="_blank" rel="noreferrer">Abrir {selected?'trecho':'destino'} no Google Maps</a>
   {embed?<><button className="secondary" onClick={()=>setShowMap(x=>!x)}>Mostrar mapa no painel</button>{showMap&&<iframe title="Trecho selecionado no Google Maps" src={embed} loading="lazy" style={{width:'100%',height:420,border:0}} referrerPolicy="strict-origin-when-cross-origin"/>}</>:<p>Mapa incorporado ainda não configurado. Os links externos já estão disponíveis.</p>}</>}
 </>}</div></Modal>;
}
