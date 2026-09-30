import {useEffect,useState} from 'react';
import {ClipboardList,CheckCircle2,Clock,AlertCircle,Package,ArrowRight,type LucideIcon} from 'lucide-react';
import type {Api} from './api';
import {ErrorBox,Loading} from './ui';
type Indicators={data:string;fuso_horario:string;total:number;agendadas:number;concluidas:number;nao_atendidas:number;canceladas:number;chamados:number;itens_a_conferir:number};
type IndicatorCard=[string,number,LucideIcon];
export default function Overview({api,onCollections}:{api:Api;onCollections:()=>void}){
 const [data,setData]=useState<Indicators|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[revision,setRevision]=useState(0);
 useEffect(()=>{const ctrl=new AbortController();setLoading(true);api<Indicators>('/operacao/indicadores',{signal:ctrl.signal}).then(v=>{setData(v);setError('');}).catch(e=>{if(e.name!=='AbortError')setError(e.message);}).finally(()=>{if(!ctrl.signal.aborted)setLoading(false);});return()=>ctrl.abort();},[api,revision]);
 return <section className="panel"><div className="panel-toolbar"><div><h2>Operação de hoje</h2><p className="helper">{data?new Date(data.data+'T12:00:00').toLocaleDateString('pt-BR'):'Resumo da operação'} · Fuso da transportadora</p></div><button className="secondary push-right" onClick={()=>setRevision(n=>n+1)}>Atualizar</button></div><ErrorBox message={error}/>{loading?<Loading/>:data&&<><div className="overview-grid">{([
  ['Agendadas',data.agendadas,Clock],['Concluídas',data.concluidas,CheckCircle2],['Não atendidas',data.nao_atendidas,AlertCircle],['Canceladas',data.canceladas,ClipboardList],['Chamados registrados',data.chamados,Package],['Itens a conferir',data.itens_a_conferir,AlertCircle]
 ] as IndicatorCard[]).map(([label,value,Icon])=><div className="overview-card" key={label}><Icon size={22}/><span>{label}</span><strong>{value}</strong></div>)}</div><div className="overview-bottom"><span>{data.total} coletas com referência em hoje. “Itens a conferir” considera todo o histórico concluído.</span><button className="primary" onClick={onCollections}>Abrir coletas<ArrowRight size={17}/></button></div></>}</section>;
}
