import {useCallback,useEffect,useMemo,useState,type FormEvent} from 'react';
import {ArrowUpRight,Users,Route as RouteIcon,Truck,LogOut,ArrowRight,ShieldCheck,Package,Menu,X,ClipboardList,Settings2,LayoutDashboard} from 'lucide-react';
import {createApi,type User,type Summary,type Client} from './api';
import {ErrorBox} from './ui';
import Clients from './Clients';
import Drivers from './Drivers';
import Routes from './Routes';
import Collections from './Collections';
import Tracking from './Tracking';
import UserManagement from './Users';
import MyPassword from './MyPassword';
import RecoveryCodes from './RecoveryCodes';
import CompanySettings from './CompanySettings';
import Overview from './Overview';

const pages=[{id:'visao',name:'Visão do dia',icon:LayoutDashboard,caption:'Acompanhe o andamento das coletas.'},{id:'rastreamento',name:'Rastreamento',icon:Truck,caption:'Última posição dos motoristas durante o turno.'},{id:'clientes',name:'Clientes',icon:Users,caption:'Sua base de clientes, em um só lugar.'},{id:'motoristas',name:'Motoristas',icon:Truck,caption:'Quem faz a operação acontecer.'},{id:'rotas',name:'Rotas fixas',icon:RouteIcon,caption:'Organize os caminhos de cada motorista.'},{id:'coletas',name:'Coletas',icon:ClipboardList,caption:'Registre as visitas e consulte o histórico por cliente.'},{id:'usuarios',name:'Acessos',icon:ShieldCheck,caption:'Controle quem pode acessar a operação.'},{id:'empresa',name:'Empresa',icon:Settings2,caption:'Dados da transportadora e modalidades de coleta.'}] as const;
type Page=typeof pages[number]['id'];
export default function App(){
 const [session,setSession]=useState<{token:string;user:User}|null>(null);
 const [page,setPage]=useState<Page>('visao');
 const [historyClient,setHistoryClient]=useState<Client|null>(null);
 const [summary,setSummary]=useState<Summary|null>(null);
 const [error,setError]=useState('');
 const [notice,setNotice]=useState('');
 const [refresh,setRefresh]=useState(0);
 const [menu,setMenu]=useState(false);
 const [passwordOpen,setPasswordOpen]=useState(false);
 const [recoveryOpen,setRecoveryOpen]=useState(false);
 const expired=useCallback(()=>{setSession(null);setSummary(null);setHistoryClient(null);setPage('visao');setError('Sua sessão expirou. Entre novamente.');},[]);
 const api=useMemo(()=>createApi(session?.token||'',expired),[session?.token,expired]);
 useEffect(()=>{if(!session||session.user.perfil==='motorista')return;const controller=new AbortController();api<Summary>('/operacao/resumo',{signal:controller.signal}).then(setSummary).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>controller.abort();},[api,session,refresh]);
 const changed=(message:string)=>{setRefresh(n=>n+1);setNotice(message);};
 useEffect(()=>{if(!notice)return;const timer=setTimeout(()=>setNotice(''),6000);return()=>clearTimeout(timer);},[notice]);
 async function logout(){try{await api('/auth/logout',{method:'POST'});}catch(e){setError((e as Error).message);return;}setSession(null);setSummary(null);setHistoryClient(null);setPage('visao');setNotice('');setError('');}
 if(!session)return <Login error={error} onLogin={(token,user)=>{setError('');setHistoryClient(null);setPage('visao');setPasswordOpen(false);setRecoveryOpen(false);setSession({token,user});}}/>;
 if(session.user.perfil==='motorista')return <div className="login-page"><div className="login-card"><Brand/><h1>Acesso do motorista</h1><p>Este painel é destinado à equipe administrativa. O aplicativo do motorista será disponibilizado em uma próxima etapa.</p><button className="primary" onClick={logout}>Sair</button><ErrorBox message={error}/></div></div>;
 const visiblePages=pages.filter(p=>!['clientes','usuarios','empresa'].includes(p.id)||session.user.perfil==='admin');
 const current=pages.find(p=>p.id===page)!;
 return <div className="app-shell"><a className="skip-link" href="#conteudo">Pular para o conteúdo</a>
  <aside className={'sidebar '+(menu?'open':'')}><Brand/><button className="mobile-close icon-button" aria-label="Fechar menu" onClick={()=>setMenu(false)}><X/></button>
   <div className="workspace"><span className="workspace-avatar">{summary?.empresa?.[0]||'T'}</span><div><strong>{summary?.empresa||'Sua transportadora'}</strong><small>Gestão de coletas</small></div></div>
   <span className="nav-label">OPERAÇÃO</span><nav aria-label="Navegação principal">{visiblePages.map(({id,name,icon:Icon})=><button key={id} className={id===page?'selected':''} aria-current={id===page?'page':undefined} onClick={()=>{setPage(id);setHistoryClient(null);setMenu(false);setError('');}}><Icon size={20}/>{name}{id===page&&<ArrowRight size={16} className="nav-arrow"/>}</button>)}</nav>
   <div className="sidebar-foot"><div className="account"><span>{session.user.nome[0]}</span><div><strong>{session.user.nome}</strong><small>{session.user.perfil==='admin'?'Administrador':session.user.perfil==='agendamento'?'Agendamento de coletas':'Operador'}</small></div></div><button onClick={()=>{setPasswordOpen(true);setMenu(false);}}>Minha senha</button><button onClick={()=>{setRecoveryOpen(true);setMenu(false);}}>Códigos de recuperação</button><button onClick={logout}><LogOut size={17}/>Sair da conta</button></div>
  </aside>
  <div className="main-shell"><header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-toggle" onClick={()=>setMenu(true)} aria-label="Abrir menu"><Menu/></button><span>Operação</span><span>/</span><strong>{current.name}</strong></div><span className="private-note"><ShieldCheck size={16}/>Área da transportadora</span></header>
   <main id="conteudo" tabIndex={-1}><div className="page-heading"><div><span className="eyebrow">GESTÃO OPERACIONAL</span><h1>{current.name}</h1><p>{current.caption}</p></div><span className="date">{new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'long',year:'numeric'}).format(new Date())}</span></div>
    <div className="stats">{[{label:'Clientes ativos',value:summary?.clientes_ativos,icon:Users},{label:'Motoristas ativos',value:summary?.motoristas_ativos,icon:Truck},{label:'Rotas ativas',value:summary?.rotas_ativas,icon:RouteIcon}].map(({label,value,icon:Icon})=><div className="stat" key={label}><span className="stat-icon"><Icon size={21}/></span><div><span>{label}</span><strong>{value??'—'}</strong></div></div>)}</div>
    <ErrorBox message={error}/>
    {page==='visao'&&<Overview api={api} onCollections={()=>setPage('coletas')}/>}
    {page==='rastreamento'&&<Tracking api={api}/>}
    {page==='clientes'&&session.user.perfil==='admin'&&<Clients api={api} admin={session.user.perfil==='admin'} changed={changed} onHistory={client=>{setHistoryClient(client);setPage('coletas');}}/>}
    {page==='motoristas'&&<Drivers api={api} admin={session.user.perfil==='admin'} changed={changed}/>}
    {page==='rotas'&&<Routes api={api} changed={changed}/>}
    {page==='coletas'&&<Collections api={api} admin={session.user.perfil==='admin'} initialClient={historyClient} changed={changed}/>}
    {page==='usuarios'&&session.user.perfil==='admin'&&<UserManagement api={api} currentId={session.user.id} changed={changed}/>}
    {page==='empresa'&&session.user.perfil==='admin'&&<CompanySettings api={api} changed={changed}/>}
   </main><footer className="page-footer"><span>Coleta · Gestão de transportadoras</span><span>Planejamento da operação</span></footer>
  </div>{passwordOpen&&<MyPassword api={api} onClose={()=>setPasswordOpen(false)} onChanged={()=>{setPasswordOpen(false);setSession(null);setError('Senha alterada. Entre novamente.');}}/>}{recoveryOpen&&<RecoveryCodes api={api} onClose={()=>setRecoveryOpen(false)}/>} {notice&&<div className="toast" role="status"><ShieldCheck size={19}/>{notice}<button aria-label="Fechar aviso" onClick={()=>setNotice('')}><X size={16}/></button></div>}
 </div>;
}
function Brand(){return <div className="brand"><span><Package size={25}/></span><strong>coleta<span className="brand-dot">.</span></strong></div>;}
function Login({onLogin,error:outerError}:{onLogin:(token:string,user:User)=>void;error:string}){
 const [error,setError]=useState('');const [busy,setBusy]=useState(false);const [recovering,setRecovering]=useState(false);const [notice,setNotice]=useState('');
 async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();setBusy(true);setError('');const form=new FormData(e.currentTarget);try{const data=await createApi('',()=>{})<{access_token:string;usuario:User}>('/auth/login',{method:'POST',body:JSON.stringify(Object.fromEntries(form))});onLogin(data.access_token,data.usuario);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function recover(e:FormEvent<HTMLFormElement>){e.preventDefault();const data=new FormData(e.currentTarget);if(data.get('nova_senha')!==data.get('confirmacao')){setError('As senhas precisam ser iguais.');return;}setBusy(true);setError('');try{await createApi('',()=>{})('/auth/recuperacao',{method:'POST',body:JSON.stringify({empresa_id:data.get('empresa_id'),usuario_login:data.get('usuario_login'),codigo:data.get('codigo'),nova_senha:data.get('nova_senha')})});setRecovering(false);setNotice('Senha redefinida. Entre com a nova senha.');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <div className="login-page"><section className="login-story"><Brand/><div><span className="eyebrow">DA BASE À ROTA</span><h1>Uma operação<br/>mais organizada.</h1><p>Clientes, motoristas e rotas conectados à rotina da sua transportadora.</p><div className="login-path"><span><Users/>Clientes</span><ArrowRight/><span><Truck/>Motoristas</span><ArrowRight/><span><RouteIcon/>Rotas</span></div></div><small>Gestão de coletas</small></section>
 <section className="login-side">{recovering?<form className="login-card" onSubmit={recover}><span className="eyebrow">RECUPERAÇÃO</span><h2>Redefinir senha</h2><p>Use um dos códigos de recuperação que você guardou anteriormente.</p><ErrorBox message={error}/><label className="field"><span>Código da empresa</span><input name="empresa_id" required autoComplete="organization"/></label><label className="field"><span>Usuário</span><input name="usuario_login" required autoComplete="username"/></label><label className="field"><span>Código de recuperação</span><input name="codigo" required minLength={24} autoComplete="off"/></label><label className="field"><span>Nova senha</span><input name="nova_senha" required type="password" minLength={12} autoComplete="new-password"/></label><label className="field"><span>Confirmar nova senha</span><input name="confirmacao" required type="password" minLength={12} autoComplete="new-password"/></label><button className="primary" disabled={busy}>{busy?'Salvando…':'Redefinir senha'}</button><button className="text-button login-switch" type="button" onClick={()=>{setRecovering(false);setError('');}}>Voltar ao login</button></form>:<form className="login-card" onSubmit={submit}><span className="eyebrow">BEM-VINDO</span><h2>Acesse sua operação</h2><p>Entre com o acesso fornecido pela sua transportadora.</p><ErrorBox message={error||outerError}/>{notice&&<p className="success-note" role="status">{notice}</p>}<label className="field"><span>Código da empresa</span><input name="empresa_id" required autoComplete="organization" placeholder="Código de acesso da transportadora"/></label><label className="field"><span>Usuário</span><input name="usuario_login" required autoComplete="username"/></label><label className="field"><span>Senha</span><input name="senha" required type="password" autoComplete="current-password"/></label><button className="primary" disabled={busy}>{busy?'Entrando…':'Entrar no painel'}<ArrowUpRight size={19}/></button><button className="text-button login-switch" type="button" onClick={()=>{setRecovering(true);setError('');}}>Esqueci minha senha</button><small className="login-help">Precisa de acesso? Fale com o administrador da sua empresa.</small></form>}</section></div>;
}
