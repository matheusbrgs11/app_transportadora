package br.com.coleta.motorista

import android.Manifest
import android.app.*
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.*
import org.json.JSONObject
import java.time.Instant
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

object TrackingPolicy {
    fun acceptable(location: Location, nowMillis: Long, nowNanos: Long): Boolean = location.hasAccuracy() &&
        location.accuracy.isFinite() && location.accuracy in 0f..1000f &&
        location.latitude.isFinite() && location.latitude in -90.0..90.0 &&
        location.longitude.isFinite() && location.longitude in -180.0..180.0 &&
        nowMillis-location.time in 0..120_000 && nowNanos-location.elapsedRealtimeNanos in 0..120_000_000_000
}

class TrackingService: Service(),LocationListener {
    private val executor=Executors.newSingleThreadExecutor()
    private val sending=AtomicBoolean(false)
    private val handler=Handler(Looper.getMainLooper())
    private lateinit var manager:LocationManager
    private lateinit var store:Store
    private var owner=""
    private var lastAttempt=0L
    private var interval=60_000L
    @Volatile private var stopped=false
    companion object { @Volatile var runningOwner:String?=null; private set }
    private val guard=object:Runnable {
        override fun run() {
            val s=SessionVault(this@TrackingService).valid()
            val t=store.tracking(owner)
            if(stopped)return
            if(s==null||s.optString("owner")!=owner||t?.optString("state")!="active"||
                Instant.parse(t.getString("expira_em"))<=Instant.now()||
                checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)!=PackageManager.PERMISSION_GRANTED) {
                stopTracking();return
            }
            handler.postDelayed(this,15_000)
        }
    }
    override fun onCreate(){super.onCreate();store=Store(this);manager=getSystemService(LocationManager::class.java)}
    override fun onBind(intent:Intent?)=null
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
        if(intent?.action=="STOP") { stopTracking();return START_NOT_STICKY }
        if(owner.isNotEmpty())return START_NOT_STICKY
        val session=SessionVault(this).valid() ?: run { stopSelf();return START_NOT_STICKY }
        owner=session.getString("owner")
        val turn=store.tracking(owner)
        if(turn?.optString("state")!="active") { stopSelf();return START_NOT_STICKY }
        interval=turn.optLong("interval_seconds",60).coerceIn(30,300)*1000
        val nm=getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel("tracking","Localização durante o turno",NotificationManager.IMPORTANCE_LOW))
        val stop=PendingIntent.getService(this,51,Intent(this,TrackingService::class.java).setAction("STOP"),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val open=PendingIntent.getActivity(this,52,Intent(this,MainActivity::class.java),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification=Notification.Builder(this,"tracking").setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentTitle("Coleta • turno com localização ativa").setContentText("Posição enviada durante o turno. Toque em Encerrar para parar.")
            .setOngoing(true).setContentIntent(open).addAction(Notification.Action.Builder(null,"Encerrar turno",stop).build()).build()
        try {
            startForeground(51,notification)
            val fine=checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED
            val coarse=checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED
            if(!coarse && !fine) { stopTracking();return START_NOT_STICKY }
            var providers=0
            if(fine && manager.isProviderEnabled(LocationManager.GPS_PROVIDER)) { manager.requestLocationUpdates(LocationManager.GPS_PROVIDER,interval,0f,this);providers++ }
            if(manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) { manager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER,interval,0f,this);providers++ }
            if(providers==0) { stopTracking();return START_NOT_STICKY }
            runningOwner=owner
            handler.post(guard)
        } catch(_:SecurityException) { stopTracking() }
        return START_NOT_STICKY
    }
    override fun onLocationChanged(location:Location) {
        if(stopped||!TrackingPolicy.acceptable(location,System.currentTimeMillis(),SystemClock.elapsedRealtimeNanos()))return
        val now=SystemClock.elapsedRealtime()
        if(now-lastAttempt<interval||!sending.compareAndSet(false,true))return
        lastAttempt=now
        executor.execute {
            try {
                val session=SessionVault(this).valid() ?: return@execute
                val turn=store.tracking(owner) ?: return@execute
                if(stopped||session.getString("owner")!=owner||turn.optString("state")!="active")return@execute
                val api=Api(session.getString("base"),session.getString("token"))
                api.request("/motorista/turnos/${turn.getString("id")}/posicao",JSONObject()
                    .put("latitude",location.latitude).put("longitude",location.longitude)
                    .put("precisao_metros",location.accuracy.toDouble()).put("capturada_em",Instant.ofEpochMilli(location.time).toString()))
            } catch(e:ApiError) {
                if(e.status in listOf(401,403,404,409))handler.post { stopTracking() }
            } catch(_:Exception) { /* No GPS backlog: the next fresh fix replaces a failed send. */ }
            finally { sending.set(false) }
        }
    }
    private fun stopTracking() {
        if(stopped)return
        stopped=true
        if(owner.isNotEmpty())store.endTracking(owner)
        runCatching { manager.removeUpdates(this) };handler.removeCallbacks(guard)
        val session=SessionVault(this).valid()
        if(session?.optString("owner")==owner) {
            runCatching { SyncScheduler.schedule(this) }
            executor.execute { runCatching { store.flushTrackingEnd(owner,Api(session.getString("base"),session.getString("token"))) } }
        }
        stopForeground(STOP_FOREGROUND_REMOVE);stopSelf()
    }
    override fun onProviderDisabled(provider:String) { /* Status ages in the panel; no fabricated location. */ }
    override fun onProviderEnabled(provider:String) {}
    @Deprecated("Legacy location callback") override fun onStatusChanged(provider:String?,status:Int,extras:Bundle?) {}
    override fun onDestroy() {
        runningOwner=null
        stopped=true;handler.removeCallbacksAndMessages(null);runCatching { manager.removeUpdates(this) }
        if(owner.isNotEmpty())store.endTracking(owner)
        if(SessionVault(this).valid()?.optString("owner")==owner) runCatching { SyncScheduler.schedule(this) }
        executor.execute { store.close() };executor.shutdown();super.onDestroy()
    }
}
