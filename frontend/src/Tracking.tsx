import {useEffect,useMemo,useState} from 'react';
import type {Api} from './api';
import {ErrorBox} from './ui';
import TrackingMap from './TrackingMap';
type Driver={id:string;nome:string;tipo:string;placa:string;turno_id:string|null;capturada_em:string|null;precisao_metros:number|null;latitude:number|null;longitude:number|null;situacao:string};
export default function Tracking({api}:{api:Api}){
 const [rows,setRows]=useState<Driver[]>([]),[error,setError]=useState(''),[now,setNow]=useState(Date.now()),[loaded,setLoaded]=useState(false);
 useEffect(()=>{
  let stopped=false,offset=0;let controller:AbortController|null=null;
  async function refresh(){
   if(document.hidden||controller)return;
   controller=new AbortController();
   try{const result=await api<{items:Driver[];agora:string}>('/rastreamento',{signal:controller.signal,cache:'no-store'});
    if(!stopped){offset=Date.parse(result.agora)-Date.now();setNow(Date.now()+offset);setRows(result.items);setError('');setLoaded(true);}
   }catch(e){if(!stopped&&(e as Error).name!=='AbortError')setError((e as Error).message);}finally{controller=null;}
  }
  void refresh();const poll=setInterval(()=>void refresh(),15000),tick=setInterval(()=>setNow(Date.now()+offset),1000);
  document.addEventListener('visibilitychange',refresh);
  return()=>{stopped=true;controller?.abort();clearInterval(poll);clearInterval(tick);document.removeEventListener('visibilitychange',refresh);};
 },[api]);
 const mapDrivers=useMemo(()=>error?[]:rows.filter(r=>r.situacao==='recente'&&r.latitude!==null&&r.longitude!==null)
  .map(r=>({id:r.id,nome:r.nome,latitude:r.latitude!,longitude:r.longitude!})),[rows,error]);
 return <section className="panel"><p>Última posição durante o turno. Atualização do painel a cada 15 segundos; envio do aparelho aproximadamente a cada minuto, sujeito à conexão e ao Android.</p>
 <TrackingMap drivers={mapDrivers}/>
 <ErrorBox message={error}/>{error&&<p role="status">Sem confirmação atual do servidor. As posições abaixo podem estar desatualizadas.</p>}
 {!loaded&&!error&&<p>Consultando motoristas…</p>}{loaded&&!rows.length&&<p>Nenhum motorista ativo.</p>}
 {rows.map(r=>{const age=r.capturada_em?Math.max(0,Math.floor((now-Date.parse(r.capturada_em))/1000)):null;
 const status=!r.turno_id?'Fora de turno':age===null?'Aguardando posição':error?'Conexão indisponível':age>120?'Posição antiga':'Posição recente';
 return <article className="stat" key={r.id}><div><h2>{r.nome}</h2><p>{r.tipo} · {r.placa}</p><strong>{status}</strong>
 {age!==null&&<p>Capturada há {age<60?age+' segundos':Math.floor(age/60)+' minutos'} · precisão estimada: {Math.round(Number(r.precisao_metros))} m<br/>{new Date(r.capturada_em!).toLocaleString('pt-BR')}</p>}
 {r.latitude!==null&&r.longitude!==null&&<a href={'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(r.latitude+','+r.longitude)} target="_blank" rel="noreferrer">Ver última posição no Google Maps</a>}
 </div></article>;})}</section>;
}
