package br.com.coleta.motorista

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build

/** Aviso local de melhor esforço: consulta em turno ativo ou JobScheduler, sem prometer entrega instantânea. */
object CallAlerts {
    fun check(context:Context,api:Api,owner:String) {
        val rows=api.request("/motorista/chamados").getJSONArray("items")
        val prefs=context.getSharedPreferences("call-alerts",Context.MODE_PRIVATE)
        val seen=prefs.getStringSet(owner,emptySet())?.toMutableSet() ?: mutableSetOf()
        val received=mutableListOf<String>()
        for(i in 0 until rows.length()) {
            val row=rows.getJSONObject(i)
            if(row.optString("estado")!="enviado")continue
            val id=row.getString("id")
            if(!seen.add(id))continue
            received.add(id)
        }
        if(received.isEmpty())return
        if(Build.VERSION.SDK_INT>=33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return
        // Persiste antes de notificar para não repetir avisos após falha ou reinício.
        prefs.edit().putStringSet(owner,seen).apply()
        val manager=context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("calls","Novos chamados de coleta",NotificationManager.IMPORTANCE_HIGH))
        val open=PendingIntent.getActivity(context,53,Intent(context,MainActivity::class.java)
            .setAction("OPEN_CALLS").addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification=Notification.Builder(context,"calls").setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(if(received.size==1) "Novo chamado de coleta" else "${received.size} novos chamados de coleta")
            .setContentText("Abra o aplicativo e atualize sua rota para responder.")
            .setVisibility(Notification.VISIBILITY_PRIVATE).setAutoCancel(true).setContentIntent(open).build()
        manager.notify(5201,notification)
    }
}
