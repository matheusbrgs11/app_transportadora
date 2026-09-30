package br.com.coleta.motorista

import android.app.Activity
import android.app.AlertDialog
import android.app.KeyguardManager
import android.content.Intent
import android.os.SystemClock
import android.os.Bundle
import android.text.InputType
import android.text.TextWatcher
import android.text.Editable
import android.view.View
import android.view.Gravity
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.widget.*
import org.json.JSONArray
import org.json.JSONObject
import java.net.URI
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID
import java.util.Locale
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private enum class Tab { COLETAS, CLIENTES, HISTORICO, MAIS }
    private val navy=Color.rgb(21,45,59)
    private val orange=Color.rgb(237,103,44)
    private val muted=Color.rgb(104,124,137)
    private val line=Color.rgb(228,234,238)
    private val backgroundColor=Color.rgb(243,246,248)
    private val dateFormat=DateTimeFormatter.ofPattern("EEEE, dd 'de' MMMM 'de' yyyy",Locale("pt","BR"))
    private lateinit var layout: LinearLayout
    private lateinit var root: LinearLayout
    private lateinit var store: Store
    private val executor = Executors.newSingleThreadExecutor()
    private var api: Api? = null
    private var owner = ""
    private var day: JSONObject? = null
    private var busy = false
    private var trackingInterval = 60
    private var session: JSONObject? = null
    private lateinit var vault: SessionVault
    override fun onCreate(state: Bundle?) {
        super.onCreate(state); store = Store(this); vault=SessionVault(this)
        window.statusBarColor=navy
        window.navigationBarColor=navy
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
        if (vault.valid()!=null) unlockSaved() else login()
    }
    @Suppress("DEPRECATION")
    private fun unlockSaved() {
        page("Desbloquear acesso salvo")
        text("Confirme o bloqueio do aparelho para acessar a rota offline. A sessão dura até 12 horas; reiniciar o aparelho exige novo login.")
        button("Desbloquear") {
            val intent=getSystemService(KeyguardManager::class.java).createConfirmDeviceCredentialIntent("Coleta","Confirme para abrir sua rota")
            if(intent!=null) startActivityForResult(intent,41) else { vault.clear();login() }
        }
        button("Entrar com outra conta") { haltTracking();vault.clear();SyncScheduler.cancel(this);login() }
    }
    @Deprecated("Legacy activity result supports Android 8")
    override fun onActivityResult(requestCode:Int,resultCode:Int,data:Intent?) {
        super.onActivityResult(requestCode,resultCode,data)
        if(requestCode==41 && resultCode==RESULT_OK) {
            val saved=vault.valid()
            if(saved==null) { login();return }
            session=saved;owner=saved.getString("owner");api=Api(saved.getString("base"),saved.getString("token"))
            day=store.cached(owner);scheduleSync();home()
        }
    }
    private fun sessionAllowed(): Boolean {
        val current=session ?: return true
        if(SessionPolicy.valid(current,System.currentTimeMillis(),SystemClock.elapsedRealtime(),vault.boot()) && (!current.optBoolean("remember") || vault.valid()?.optString("token")==current.getString("token"))) return true
        haltTracking();session=null;login();message("Acesso local expirado ou relógio alterado. Entre novamente; seus registros estão preservados.")
        return false
    }
    private fun scheduleSync() {
        if(vault.valid()!=null) runCatching { SyncScheduler.schedule(this) }
            .onFailure { message("Envio automático indisponível. Use Enviar registros salvos.") }
    }
    private fun rounded(color: Int, radius: Float = 18f, stroke: Int? = null) = GradientDrawable().apply {
        setColor(color); cornerRadius=radius * resources.displayMetrics.density
        if(stroke!=null) setStroke((1*resources.displayMetrics.density).toInt(),stroke)
    }
    private fun page(title: String, tab: Tab? = null) {
        root=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL;setBackgroundColor(backgroundColor) }
        val top=LinearLayout(this).apply {
            orientation=LinearLayout.HORIZONTAL;gravity=Gravity.CENTER_VERTICAL
            setBackgroundColor(navy);setPadding(dp(20),dp(10),dp(20),dp(10))
        }
        val brandMark=TextView(this).apply {
            text="▣";textSize=24f;gravity=Gravity.CENTER;setTextColor(Color.WHITE)
            background=rounded(orange,10f)
        }
        top.addView(brandMark,LinearLayout.LayoutParams(dp(40),dp(40)))
        top.addView(TextView(this).apply {
            text="coleta.";textSize=24f;setTypeface(null,Typeface.BOLD);setTextColor(Color.WHITE)
            setPadding(dp(10),0,0,0)
        })
        top.addView(TextView(this).apply {
            text="MOTORISTA";textSize=11f;letterSpacing=.12f;setTextColor(Color.rgb(175,197,209));gravity=Gravity.END
        },LinearLayout.LayoutParams(0,-2,1f))
        root.addView(top,LinearLayout.LayoutParams(-1,dp(64)))
        layout=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL;setPadding(dp(20),dp(18),dp(20),dp(28)) }
        val scroll=ScrollView(this).apply { isFillViewport=true;addView(layout) }
        root.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
        if(tab!=null) bottomNavigation(tab)
        setContentView(root)
        text(title,27f).apply { setTextColor(navy);setTypeface(null,Typeface.BOLD);setPadding(0,dp(8),0,dp(8)) }
    }
    private fun dp(value: Int)=(value*resources.displayMetrics.density).toInt()
    private fun text(value: String, size: Float = 17f) = TextView(this).also {
        it.text=value;it.textSize=size;it.setTextColor(navy);it.setPadding(0,dp(7),0,dp(7));layout.addView(it)
    }
    private fun hint(value: String)=text(value,14f).apply { setTextColor(muted) }
    private fun section(value: String)=text(value,20f).apply { setTypeface(null,Typeface.BOLD);setPadding(0,dp(22),0,dp(7)) }
    private fun card(build: () -> Unit) {
        val outer=layout
        val content=LinearLayout(this).apply {
            orientation=LinearLayout.VERTICAL;setPadding(dp(16),dp(14),dp(16),dp(16))
            background=rounded(Color.WHITE,11f,line)
        }
        outer.addView(content,LinearLayout.LayoutParams(-1,-2).apply { bottomMargin=dp(12) })
        layout=content
        try { build() } finally { layout=outer }
    }
    private fun bottomNavigation(current: Tab) {
        val bar=LinearLayout(this).apply {
            orientation=LinearLayout.HORIZONTAL;setPadding(dp(6),dp(5),dp(6),dp(5));setBackgroundColor(navy)
        }
        val items=listOf(Triple(Tab.COLETAS,"Coletas",R.drawable.ic_tab_coletas),Triple(Tab.CLIENTES,"Clientes",R.drawable.ic_tab_clientes),
            Triple(Tab.HISTORICO,"Histórico",R.drawable.ic_tab_historico),Triple(Tab.MAIS,"Mais",R.drawable.ic_tab_mais))
        for((tab,label,icon) in items) {
            val selected=tab==current
            val item=LinearLayout(this).apply {
                orientation=LinearLayout.VERTICAL;gravity=Gravity.CENTER
                background=if(selected) rounded(Color.rgb(42,66,80),9f) else rounded(navy,9f)
                contentDescription=label
                setOnClickListener { if(!busy && sessionAllowed()) when(tab) {
                    Tab.COLETAS -> home();Tab.CLIENTES -> clients();Tab.HISTORICO -> historyHome();Tab.MAIS -> more()
                } }
            }
            item.addView(ImageView(this).apply {
                setImageResource(icon);setColorFilter(if(selected) orange else Color.rgb(183,200,211))
            },LinearLayout.LayoutParams(dp(21),dp(21)))
            item.addView(TextView(this).apply {
                text=label;textSize=12f;gravity=Gravity.CENTER
                setTypeface(null,if(selected) Typeface.BOLD else Typeface.NORMAL)
                setTextColor(if(selected) Color.WHITE else Color.rgb(183,200,211))
                setPadding(0,dp(4),0,0)
            })
            bar.addView(item,LinearLayout.LayoutParams(0,dp(62),1f).apply { leftMargin=dp(2);rightMargin=dp(2) })
        }
        root.addView(bar,LinearLayout.LayoutParams(-1,-2))
    }
    private fun field(label: String, secret: Boolean = false): EditText {
        text(label)
        return EditText(this).also {
            it.isSingleLine = true
            it.inputType = if (secret) InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_CLASS_TEXT
            it.importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO
            it.setPadding(dp(12),0,dp(12),0);it.background=rounded(Color.WHITE,7f,line)
            it.minHeight=dp(48)
            layout.addView(it)
        }
    }
    private fun button(label: String, action: () -> Unit) = Button(this).also {
        it.text=label;it.textSize=16f;it.isAllCaps=false;it.minHeight=dp(52)
        it.setTextColor(Color.WHITE);it.background=rounded(orange,8f)
        it.setOnClickListener { if (!busy && sessionAllowed()) action() }
        layout.addView(it,LinearLayout.LayoutParams(-1,-2).apply { topMargin=dp(8) })
    }
    private fun secondaryButton(label: String, action: () -> Unit)=button(label,action).apply {
        setTextColor(navy);background=rounded(Color.WHITE,8f,line)
    }
    private fun message(value: String) { AlertDialog.Builder(this).setMessage(value).setPositiveButton("OK",null).show() }
    private fun background(work: () -> Unit, done: () -> Unit) {
        busy = true
        executor.execute {
            val failure = runCatching(work).exceptionOrNull()
            runOnUiThread {
                busy = false
                if (!isDestroyed) {
                    if (failure is ApiError && failure.status==401 && api!=null) {
                        haltTracking();api?.let { vault.clear(owner,it.token) };SyncScheduler.cancel(this@MainActivity);session=null;login()
                        message(failure.message ?: "Entre novamente.");return@runOnUiThread
                    }
                    if (failure != null) message(failure.message ?: "Não foi possível conectar. Os registros salvos foram preservados.")
                    done()
                }
            }
        }
    }
    private fun login() {
        api = null; owner = ""; day = null; session=null
        page("Coleta • Motorista")
        text("Entre com o acesso fornecido pela transportadora.")
        val server = field("Servidor da transportadora")
        server.setText(getString(R.string.default_server))
        val company = field("Código da empresa")
        val username = field("Usuário")
        val password = field("Senha", true)
        val remember=CheckBox(this).apply {
            text="Manter acesso offline e envio automático por até 12 horas"
            isEnabled=getSystemService(KeyguardManager::class.java).isDeviceSecure
            isChecked=isEnabled
        };layout.addView(remember)
        if(!remember.isEnabled) text("Configure PIN ou senha de bloqueio do Android para manter acesso e envio automático após fechar o app.")
        button("Entrar") {
            val base = server.text.toString().trim().trimEnd('/')
            val uri = runCatching { URI(base) }.getOrNull()
            if (uri == null || uri.host == null || uri.userInfo != null || uri.query != null || uri.fragment != null || uri.scheme !in listOf("http","https")) {
                message("Informe uma URL válida do servidor."); return@button
            }
            val body = JSONObject().put("empresa_id",company.text.toString().trim()).put("usuario_login",username.text.toString().trim()).put("senha",password.text.toString())
            val persist=remember.isChecked
            password.text.clear()
            background({
                val service = Api(base)
                val result = service.request("/auth/login",body)
                service.token = result.getString("access_token")
                val user = result.getJSONObject("usuario")
                if (user.getString("perfil") != "motorista") {
                    service.request("/auth/logout",JSONObject()); error("Este aplicativo é exclusivo para motoristas.")
                }
                val key = base + "|" + user.getString("empresa_id") + "|" + user.getString("id")
                val saved=SessionPolicy.create(base,key,service.token,result.getLong("expires_in"),vault.boot()).put("remember",persist)
                if(persist) vault.save(saved) else { vault.clear();SyncScheduler.cancel(this@MainActivity) }
                session=saved;owner = key; api = service; day = store.cached(key)
            }, { if (api != null) { scheduleSync();home(); refresh() } })
        }
    }
    private fun refresh() {
        val service = api ?: return
        background({
            val updated = service.request("/motorista/rota-do-dia/preparar",JSONObject())
            updated.put("modalidades",service.request("/motorista/modalidades").getJSONArray("items"))
            store.cache(owner,updated); day = updated
        }, { home() })
    }
    private fun haltTracking() {
        val key=owner.ifEmpty { vault.valid()?.optString("owner") ?: "" }
        if(key.isNotEmpty()) store.endTracking(key)
        stopService(Intent(this,TrackingService::class.java))
    }
    private fun trackingScreen() {
        page("Localização durante o turno")
        text("Ao iniciar, sua última posição será enviada à transportadora aproximadamente a cada minuto, mesmo com a tela fechada. Encerre ao terminar. O turno expira em até 12 horas.")
        val state=store.tracking(owner)?.optString("state")
        text(if(state=="ending") "Encerramento aguardando conexão; captura parada." else if(TrackingService.runningOwner==owner) "Captura ativa. Confira também a notificação do Android." else "Captura parada neste aparelho.")
        if(TrackingService.runningOwner==owner) {
            text(TrackingService.transmissionStatus)
            TrackingService.lastSentAt?.let { text("Última confirmação: "+it.atZone(ZoneId.systemDefault()).toLocalTime().withNano(0)) }
        }
        button("Intervalo de envio: $trackingInterval segundos") {
            AlertDialog.Builder(this).setItems(arrayOf("30 segundos","60 segundos","120 segundos","300 segundos")) { _,which ->
                trackingInterval=listOf(30,60,120,300)[which];trackingScreen()
            }.show()
        }
        text("Alterações de intervalo valem no próximo início da captura.")
        button("Iniciar / retomar turno") { startTurn() }
        button("Encerrar turno") { endTurn() }
        secondaryButton("Atualizar situação") { trackingScreen() }
        secondaryButton("Voltar para minha rota") { home() }
    }
    private fun startTurn() {
            if(vault.valid()?.optString("owner")!=owner) { message("Entre com a opção de manter acesso habilitada e bloqueio de tela configurado.");return }
            val permissions=mutableListOf(android.Manifest.permission.ACCESS_COARSE_LOCATION,android.Manifest.permission.ACCESS_FINE_LOCATION)
            if(android.os.Build.VERSION.SDK_INT>=33) permissions.add(android.Manifest.permission.POST_NOTIFICATIONS)
            if(checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)!=android.content.pm.PackageManager.PERMISSION_GRANTED ||
                (android.os.Build.VERSION.SDK_INT>=33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED)) {
                requestPermissions(permissions.toTypedArray(),53);message("Após autorizar, toque novamente em Iniciar turno.");return
            }
            val service=api ?: return
            var ready=false
            background({
                store.flushTrackingEnd(owner,service)
                var local=store.tracking(owner)
                if(local==null) {
                    check(service.request("/motorista/turnos/atual").isNull("turno")) { "Existe turno em outro aparelho. Use Encerrar turno antes de iniciar aqui." }
                    local=JSONObject().put("id",UUID.randomUUID().toString()).put("state","starting")
                    store.tracking(owner,local)
                }
                val turn=service.request("/motorista/turnos",JSONObject().put("id",local.getString("id")))
                if(!turn.isNull("encerrado_em")) {
                    store.endTracking(owner);store.flushTrackingEnd(owner,service)
                    error("Turno anterior encerrado. Toque em Iniciar para abrir outro.")
                }
                store.tracking(owner,turn.put("state","active").put("interval_seconds",trackingInterval))
                ready=true
            },{
                if(ready && hasWindowFocus()) {
                    runCatching { startForegroundService(Intent(this,TrackingService::class.java)) }.onFailure {
                        haltTracking();scheduleSync();message("Não foi possível iniciar a localização. Confira as permissões e tente novamente.")
                    }
                }
                home()
            })
    }
    private fun endTurn() {
            val service=api ?: return
            haltTracking()
            background({
                store.flushTrackingEnd(owner,service)
                val current=service.request("/motorista/turnos/atual").optJSONObject("turno")
                if(current!=null) service.request("/motorista/turnos/${current.getString("id")}/encerrar",JSONObject())
            },{scheduleSync();home()})
    }
    private fun home() {
        page("Meu dia",Tab.COLETAS)
        val records = store.visits(owner)
        val pending=records.count { it.getString("state") in listOf("pending","sending") }
        val review=records.count { it.getString("state") in listOf("conflict","review") }
        val state=store.tracking(owner)?.optString("state")
        card {
            text(when {
                state=="ending" -> "Turno encerrado • aguardando conexão"
                state=="active" -> "Turno em andamento"
                else -> "Turno não iniciado"
            },20f).setTypeface(null,Typeface.BOLD)
            hint(when {
                state=="ending" -> "A localização foi interrompida. O encerramento será enviado quando houver conexão."
                state=="active" && TrackingService.runningOwner==owner -> "Localização ativa durante o turno."
                state=="active" -> "Turno aberto. Confira a localização em Mais opções."
                else -> "Inicie o turno para compartilhar sua localização com a transportadora."
            })
            button(if(state=="active") "Finalizar turno" else "Iniciar turno") {
                if(state=="active") endTurn() else startTurn()
            }
            if(state=="active" && TrackingService.runningOwner!=owner)
                secondaryButton("Retomar localização") { startTurn() }
        }
        if(pending>0 || review>0) card {
            text("$pending aguardando envio • $review em conferência",17f).setTypeface(null,Typeface.BOLD)
            secondaryButton("Ver registros") { outbox() }
        }
        val plan = day
        if (plan == null) {
            card { text("Sua rota ainda não foi carregada.");button("Carregar rota de hoje") { refresh() } }
            return
        }
        val routeDate=LocalDate.parse(plan.getString("data"))
        hint(routeDate.format(dateFormat).replaceFirstChar { it.titlecase(Locale("pt","BR")) })
        val today = LocalDate.now(ZoneId.of(plan.getString("fuso_horario"))).toString()
        val current = today == plan.getString("data")
        if (!current) card { text("Esta rota é de outro dia. Atualize antes de registrar novas visitas.") }
        secondaryButton("Atualizar rota do dia") { refresh() }
        val routes = plan.getJSONArray("rotas")
        if (routes.length()==0) card { text("Nenhuma rota programada para este dia.") }
        for (r in 0 until routes.length()) {
            val route = routes.getJSONObject(r)
            section(route.getString("nome"))
            val progress = route.optJSONObject("progresso")
            if (progress != null) hint("${progress.optInt("agendada")} para atender · ${progress.optInt("concluida")} concluídas")
            val stops = route.getJSONArray("paradas")
            for (s in 0 until stops.length()) {
                val stop = stops.getJSONObject(s)
                val existing = records.lastOrNull {
                    val b=it.getJSONObject("body")
                    if (!b.isNull("coleta_id") && !stop.isNull("coleta_id")) b.getString("coleta_id")==stop.getString("coleta_id")
                    else b.getString("rota_id")==route.getString("id") && b.getString("cliente_id")==stop.getString("cliente_id") &&
                        ApiTime.parse(b.getString("concluida_em")).atZone(ZoneId.of(plan.getString("fuso_horario"))).toLocalDate().toString()==today
                }
                val remoteStatus=stop.optString("status","agendada")
                card {
                    text("${stop.getInt("ordem")}. ${stop.getString("nome")}",20f).setTypeface(null,Typeface.BOLD)
                    val status=when {
                        remoteStatus=="concluida" -> "Concluída"
                        remoteStatus=="cancelada" -> "Cancelada"
                        remoteStatus!="agendada" -> "Não atendida"
                        existing?.optString("state")=="sent" -> "Enviada"
                        existing!=null -> "Salva no aparelho • aguardando envio"
                        else -> "Próxima coleta"
                    }
                    hint("$status · tentativa ${stop.optInt("tentativa",1)}")
                    if(remoteStatus=="agendada" && existing==null && current) {
                        button("Realizar coleta") { visit(plan,route,stop) }
                        secondaryButton("Não foi possível atender") { notAttended(plan,route,stop) }
                    }
                    secondaryButton("Abrir no Google Maps") { navigate(stop) }
                }
            }
        }
    }
    private fun clients() {
        page("Clientes da rota",Tab.CLIENTES)
        val plan=day
        if(plan==null) { card { text("Carregue sua rota para ver os clientes de hoje.");button("Carregar rota") { refresh() } };return }
        hint("Endereços e contatos das paradas de hoje.")
        val routes=plan.getJSONArray("rotas")
        var count=0
        for(r in 0 until routes.length()) {
            val stops=routes.getJSONObject(r).getJSONArray("paradas")
            for(s in 0 until stops.length()) {
                val stop=stops.getJSONObject(s);count++
                card {
                    text(stop.getString("nome"),20f).setTypeface(null,Typeface.BOLD)
                    hint(listOf("endereco","numero","complemento","bairro","cidade","estado")
                        .filter { !stop.isNull(it) && stop.optString(it).isNotBlank() }
                        .joinToString(", ") { stop.getString(it) })
                    if(!stop.isNull("telefone")) text("Telefone: ${stop.getString("telefone")}",16f)
                    if(!stop.isNull("janela_inicio")) hint("Horário: ${stop.getString("janela_inicio")}–${stop.getString("janela_fim")}")
                    secondaryButton("Abrir no Google Maps") { navigate(stop) }
                }
            }
        }
        if(count==0) card { text("Nenhum cliente programado para hoje.") }
    }
    private fun historyHome() {
        page("Histórico",Tab.HISTORICO)
        hint("Confira atendimentos anteriores e registros salvos neste aparelho.")
        card {
            text("Atendimentos",20f).setTypeface(null,Typeface.BOLD)
            button("Ver coletas de hoje") { history(days=1) }
            secondaryButton("Ver últimos 7 dias") { history() }
            secondaryButton("Ver últimos 6 meses") { history(days=183) }
        }
        val records=store.visits(owner)
        val pending=records.count { it.getString("state") in listOf("pending","sending") }
        card {
            text("Registros do aparelho",20f).setTypeface(null,Typeface.BOLD)
            hint("$pending aguardando envio")
            secondaryButton("Ver registros e conferências") { outbox() }
        }
    }
    private fun more() {
        page("Mais opções",Tab.MAIS)
        card {
            text("Turno e localização",20f).setTypeface(null,Typeface.BOLD)
            hint("Inicie ou finalize o turno e confira o último envio de localização.")
            button("Abrir turno") { trackingScreen() }
        }
        card {
            text("Conexão",20f).setTypeface(null,Typeface.BOLD)
            secondaryButton("Atualizar rota") { refresh() }
            secondaryButton("Enviar registros salvos") { sync() }
        }
        secondaryButton("Sair da conta") { logout() }
    }
    private fun logout() {
        val service=api
        val pending=store.visits(owner).count { it.getString("state") !in listOf("sent","resolved") }
        AlertDialog.Builder(this).setMessage("Sair? $pending registros permanecem no aparelho. O envio automático será pausado até novo login nesta conta.")
            .setNegativeButton("Continuar trabalhando",null).setPositiveButton("Sair") { _,_ ->
                haltTracking();vault.clear();SyncScheduler.cancel(this);session=null
                background({ runCatching { if(service!=null) store.flushTrackingEnd(owner,service) };runCatching { service?.request("/auth/logout",JSONObject()) } }, { login() })
            }.show()
    }
    private fun navigate(stop: JSONObject) {
        fun open() {
            val intent=Intent(Intent.ACTION_VIEW,Navigation.uri(stop))
            try { startActivity(Intent(intent).setPackage("com.google.android.apps.maps")) }
            catch(_:android.content.ActivityNotFoundException) {
                try { startActivity(intent) }
                catch(_:android.content.ActivityNotFoundException) { message("Instale Google Maps ou um navegador para abrir o destino.") }
            }
        }
        if(Navigation.confirmed(stop)) open()
        else AlertDialog.Builder(this).setMessage("Este cliente ainda não tem ponto confirmado. O Google Maps pesquisará pelo endereço; confira o destino antes de seguir.")
            .setNegativeButton("Voltar",null).setPositiveButton("Pesquisar destino") { _,_ -> open() }.show()
    }
    private fun visit(plan: JSONObject, route: JSONObject, stop: JSONObject) {
        val draftKey = draftKey(plan,route,stop)
        val draft = store.draft(owner,draftKey)
        page("Realizar coleta")
        section(stop.getString("nome"))
        hint("1. Selecione o tipo de mercadoria e informe a quantidade.")
        hint("Se não souber a quantidade, deixe o campo vazio para conferir depois.")
        val mods = plan.getJSONArray("modalidades")
        val entries = mutableListOf<Triple<String,CheckBox,EditText>>()
        for (i in 0 until mods.length()) {
            val m=mods.getJSONObject(i)
            val selected=CheckBox(this).apply { text=m.getString("nome") }; layout.addView(selected)
            val quantity=EditText(this).apply { hint="Quantidade a conferir"; inputType=InputType.TYPE_CLASS_NUMBER }; layout.addView(quantity)
            entries.add(Triple(m.getString("id"),selected,quantity))
        }
        section("2. Detalhes")
        val notes=field("Observações (opcional)")
        var proofEditor: ProofEditor? = null
        fun persistDraft() {
            val fields=JSONObject()
            for ((id,selected,quantity) in entries) fields.put(id,JSONObject()
                .put("selected",selected.isChecked).put("quantity",quantity.text.toString()))
            try { store.draft(owner,draftKey,JSONObject().put("fields",fields).put("notes",notes.text.toString()).put("comprovante",proofEditor?.draft() ?: draft?.optJSONObject("comprovante") ?: JSONObject.NULL)) }
            catch (_: Exception) { message("Falha ao preservar rascunho. Não feche esta tela antes de salvar.") }
        }
        val watcher=object:TextWatcher {
            override fun beforeTextChanged(s:CharSequence?,start:Int,count:Int,after:Int) {}
            override fun onTextChanged(s:CharSequence?,start:Int,before:Int,count:Int) {}
            override fun afterTextChanged(s:Editable?) { persistDraft() }
        }
        for ((id,selected,quantity) in entries) {
            val saved=draft?.optJSONObject("fields")?.optJSONObject(id)
            selected.isChecked=saved?.optBoolean("selected") ?: false
            quantity.setText(saved?.optString("quantity") ?: "")
        }
        notes.setText(draft?.optString("notes") ?: "")
        for ((_,selected,quantity) in entries) {
            selected.setOnCheckedChangeListener { _,_ -> persistDraft() }
            quantity.addTextChangedListener(watcher)
        }
        notes.addTextChangedListener(watcher)
        section("3. Assinatura ou justificativa")
        proofEditor=ProofEditor(this,draft?.optJSONObject("comprovante")) { persistDraft() }
        layout.addView(proofEditor)
        text("Rascunho preservado neste aparelho. Só será enviado após salvar a coleta.")
        button("Concluir coleta") {
            if(!saveDayAllowed(plan)) return@button
            if (stop.isNull("coleta_id")) {
                message("Atualize a rota antes de registrar esta coleta. O rascunho foi preservado."); return@button
            }
            val items=JSONArray()
            for ((id,selected,quantity) in entries) {
                if (!selected.isChecked) continue
                val raw=quantity.text.toString().trim()
                val count=raw.toIntOrNull()
                if (raw.isNotEmpty() && (count==null || count<0)) { message("Informe uma quantidade inteira válida."); return@button }
                items.put(JSONObject().put("modalidade_id",id).put("quantidade",count ?: JSONObject.NULL).put("quantidade_status",if(count==null) "a_conferir" else "confirmada"))
            }
            if (items.length()==0) { message("Selecione ao menos uma modalidade."); return@button }
            val proof=try { proofEditor!!.proof() } catch(e:Exception) { message(e.message ?: "Confira a rubrica.");return@button }
            val body=JSONObject().put("comprovante",proof).put("id_local_dispositivo",UUID.randomUUID().toString()).put("rota_id",route.getString("id"))
                .put("coleta_id",stop.getString("coleta_id")).put("versao_rota",route.getInt("versao")).put("cliente_id",stop.getString("cliente_id"))
                .put("concluida_em",Instant.now().toString()).put("itens",items).put("observacoes",notes.text.toString())
            try { store.saveDraftVisit(owner,draftKey,body); scheduleSync();home(); sync() } catch (e: Exception) { message("Não foi possível salvar no aparelho. Mantenha esta tela e tente novamente.") }
        }
        secondaryButton("Voltar e manter rascunho") { home() }
    }
    private fun saveDayAllowed(plan: JSONObject): Boolean {
        if(LocalDate.now(ZoneId.of(plan.getString("fuso_horario"))).toString()==plan.getString("data")) return true
        message("O dia da rota mudou. Rascunho preservado; atualize a rota antes de registrar outro atendimento.")
        return false
    }
    private fun draftKey(plan: JSONObject, route: JSONObject, stop: JSONObject): String {
        val legacy = plan.getString("data") + "|" + route.getString("id") + "|" + stop.getString("cliente_id")
        // Preserve drafts from the previous app while giving revisits their own identity.
        if (stop.isNull("coleta_id") || (stop.optInt("tentativa",1)==1 && store.draft(owner,legacy)!=null)) return legacy
        return stop.getString("coleta_id")
    }

    private fun notAttended(plan: JSONObject, route: JSONObject, stop: JSONObject) {
        page("Não atendida • ${stop.getString("nome")}")
        val key = draftKey(plan,route,stop) + "|nao_atendida"
        val reason = field("Motivo obrigatório (até 1.000 caracteres)")
        reason.setText(store.draft(owner,key)?.optString("motivo") ?: "")
        reason.addTextChangedListener(object: TextWatcher {
            override fun beforeTextChanged(s:CharSequence?,start:Int,count:Int,after:Int) {}
            override fun onTextChanged(s:CharSequence?,start:Int,before:Int,count:Int) {}
            override fun afterTextChanged(s:Editable?) {
                try { store.draft(owner,key,JSONObject().put("motivo",s.toString())) }
                catch (_:Exception) { message("Não foi possível preservar o rascunho.") }
            }
        })
        button("Salvar não atendimento no aparelho") {
            if(!saveDayAllowed(plan)) return@button
            val value = reason.text.toString().trim()
            if (value.isEmpty() || value.length>1000 || stop.isNull("coleta_id")) {
                message("Informe um motivo de até 1.000 caracteres e use uma rota atualizada."); return@button
            }
            val body=JSONObject().put("id_local_dispositivo",UUID.randomUUID().toString())
                .put("coleta_id",stop.getString("coleta_id")).put("rota_id",route.getString("id"))
                .put("versao_rota",route.getInt("versao")).put("cliente_id",stop.getString("cliente_id"))
                .put("concluida_em",Instant.now().toString()).put("status","nao_atendida")
                .put("motivo",value).put("itens",JSONArray())
            try { store.saveDraftVisit(owner,key,body); scheduleSync();home(); sync() }
            catch (_:Exception) { message("Falha ao salvar. Mantenha esta tela e tente novamente.") }
        }
        button("Voltar • manter rascunho") { home() }
    }

    private fun history(offset: Int = 0, days: Int = 7) {
        val service=api ?: return
        var result: JSONObject? = null
        val zone=ZoneId.of(day?.optString("fuso_horario") ?: "America/Sao_Paulo")
        val end=LocalDate.now(zone)
        val start=end.minusDays((days-1).toLong())
        background({ result=service.request("/motorista/historico?limit=50&offset=$offset&data_inicio=$start&data_fim=$end") }, {
            val data=result ?: return@background
            page(when(days) { 1 -> "Coletas de hoje"; 7 -> "Últimos 7 dias"; else -> "Últimos 6 meses" },Tab.HISTORICO)
            hint("${data.getInt("total")} atendimentos")
            val rows=data.getJSONArray("items")
            if (rows.length()==0) text("Nenhum atendimento neste período.")
            for (i in 0 until rows.length()) {
                val row=rows.getJSONObject(i)
                val status=when(row.getString("status")) {
                    "concluida" -> "Concluída"
                    "nao_atendida" -> "Não atendida"
                    "cancelada" -> "Cancelada"
                    else -> "Pendente"
                }
                val local=ApiTime.parse(row.getString("data_referencia")).atZone(ZoneId.of(data.getString("fuso_horario")))
                card {
                    text(row.getString("cliente_nome"),20f).setTypeface(null,Typeface.BOLD)
                    text(local.toLocalDate().format(dateFormat).replaceFirstChar { it.titlecase(Locale("pt","BR")) },16f)
                    hint("$status · tentativa ${row.getInt("tentativa")}")
                }
            }
            if (offset>0) button("Página anterior") { history(maxOf(0,offset-50),days) }
            if (offset+rows.length()<data.getInt("total")) button("Próxima página") { history(offset+50,days) }
        })
    }
    private fun clientName(body: JSONObject): String {
        val plan=day ?: return "Cliente da coleta"
        val routes=plan.optJSONArray("rotas") ?: return "Cliente da coleta"
        for(r in 0 until routes.length()) {
            val stops=routes.getJSONObject(r).optJSONArray("paradas") ?: continue
            for(s in 0 until stops.length()) {
                val stop=stops.getJSONObject(s)
                if(stop.optString("cliente_id")==body.optString("cliente_id")) return stop.optString("nome","Cliente da coleta")
            }
        }
        return "Cliente da coleta"
    }
    private fun outbox() {
        page("Registros salvos",Tab.HISTORICO)
        val records=store.visits(owner)
        if(records.isEmpty()) text("Nenhum registro salvo nesta conta.")
        for(record in records) {
            val id=record.getString("id");val state=record.getString("state");val body=record.getJSONObject("body")
            val label=when(state) { "pending"->"Pendente";"sending"->"Enviando";"sent"->"Enviado";"review"->"Em conferência";"resolved"->"Conferido pela operação";else->"Conflito" }
            val date=runCatching { ApiTime.parse(body.getString("concluida_em")).atZone(ZoneId.systemDefault()).toLocalDate().format(dateFormat) }.getOrDefault("Data indisponível")
            section(clientName(body))
            text(date.replaceFirstChar { it.titlecase(Locale("pt","BR")) },16f)
            hint(label)
            val detail=body.optString("motivo",body.optString("observacoes"))
            if(detail.isNotBlank()) hint(detail)
            if(record.optString("error").isNotBlank()) text(record.getString("error"))
            if(state=="conflict") {
                button("Retentar este registro") { store.state(owner,id,"pending");scheduleSync();sync() }
                button("Enviar este registro para conferência") {
                    val service=api ?: return@button
                    background({
                        val result=service.request("/motorista/conflitos",JSONObject().put("id_local_dispositivo",id).put("payload",body))
                        check(result.optString("status") in listOf("aberto","resolvido")) { "Confirmação inválida. Registro preservado." }
                        UUID.fromString(result.getString("id"))
                        store.state(owner,id,"review","Aguardando conferência da operação. Conteúdo original preservado.")
                    }, { outbox() })
                }
            }
            if(state=="review") button("Consultar resposta da operação") {
                val service=api ?: return@button
                background({
                    val result=service.request("/motorista/conflitos/$id")
                    if(result.getString("status")=="resolvido") store.state(owner,id,"resolved",result.getString("resolucao"))
                }, { outbox() })
            }
        }
    }
    private fun sync() {
        val service=api ?: return
        background({
            store.flushTrackingEnd(owner,service)
            VisitSync(store, owner) { body ->
                val current=session
                check(current==null || SessionPolicy.valid(current,System.currentTimeMillis(),SystemClock.elapsedRealtime(),vault.boot())) { "Sessão local expirada. Entre novamente." }
                service.request("/motorista/coletas", body)
            }.run()
        }, { home() })
    }
    override fun onDestroy() { super.onDestroy(); executor.shutdown() }
}
