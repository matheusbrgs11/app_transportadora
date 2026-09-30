export type Api = {<T>(path:string,options?:RequestInit):Promise<T>;download:(path:string)=>Promise<Blob>};
async function responseError(response:Response){
 const body=await response.json().catch(()=>({detail:'O serviço não está disponível no momento.'}));
 const detail=Array.isArray(body.detail)?body.detail.map((e:{loc?:string[];msg?:string})=>`${(e.loc||[]).filter(x=>x!=='body').join(' · ')}: ${e.msg||'Valor inválido'}`).join('\n'):body.detail;
 return new Error(typeof detail==='string'&&detail?detail:'Não foi possível concluir esta ação.');
}
export function createApi(token:string,onExpired:()=>void):Api {
 const request=async <T>(path:string,options:RequestInit={})=>{
  let response:Response;
  try {
   response=await fetch('/api'+path,{...options,headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(token?{Authorization:`Bearer ${token}`} : {}),...options.headers}});
  } catch(error) {
   if(error instanceof DOMException && error.name==='AbortError') throw error;
   throw new Error('Não foi possível conectar. Confira sua conexão e tente novamente.');
  }
  if(response.status===401&&token) onExpired();
  if(!response.ok)throw await responseError(response);
  return response.status===204?undefined as T:response.json();
 };
 const api=request as Api;
 api.download=async (path:string)=>{
  let response:Response;
  try{response=await fetch('/api'+path,{headers:token?{Authorization:`Bearer ${token}`}:{}});}
  catch{throw new Error('Não foi possível conectar. Confira sua conexão e tente novamente.');}
  if(response.status===401&&token)onExpired();
  if(!response.ok)throw await responseError(response);
  return response.blob();
 };
 return api;
}
export type User={id:string;nome:string;perfil:'admin'|'operador'|'motorista'|'agendamento';empresa_id:string};
export type Client={id:string;latitude:number|null;longitude:number|null;localizacao_confirmada:boolean;localizacao_versao:number;localizacao_fonte:string|null;nome:string;cnpj:string;endereco:string;numero:string|null;complemento:string|null;bairro:string|null;cidade:string;estado:string;cep:string|null;telefone:string|null;email:string|null;contrato_status:'nao_informado'|'sem_contrato'|'com_contrato';numero_contrato:string|null;ativo:boolean};
export type Driver={id:string;nome:string;login:string;tipo:string;placa:string;ativo:boolean;rotas_ativas:number};
export type Stop={latitude?:number|null;longitude?:number|null;localizacao_confirmada?:boolean;cliente_id:string;nome:string;endereco:string;numero:string|null;cidade:string;estado:string;janela_inicio:string|null;janela_fim:string|null;cliente_ativo?:boolean};
export type Route={id:string;nome:string;motorista_id:string;motorista_nome:string;dias_semana:number[];ativa:boolean;versao:number;total_paradas:number;paradas:Stop[];tipo:string;placa:string};
export type Summary={empresa:string;clientes_ativos:number;motoristas_ativos:number;rotas_ativas:number;enderecos_a_localizar:number};
export function cnpj(value:string){return value.replace(/^(.{2})(.{3})(.{3})(.{4})(.{2})$/,'$1.$2.$3/$4-$5');}
export const days=['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'];
export const vehicleNames:Record<string,string>={carro:'Carro',moto:'Moto',van:'Van',caminhao:'Caminhão',outro:'Outro'};
