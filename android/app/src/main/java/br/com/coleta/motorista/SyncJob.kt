package br.com.coleta.motorista

import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.ComponentName
import android.content.Context
import android.util.Log
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

object SyncScheduler {
    private const val NOW=4101
    private const val PERIODIC=4102
    fun schedule(context: Context) {
        val scheduler=context.getSystemService(JobScheduler::class.java)
        val component=ComponentName(context,SyncJob::class.java)
        if (scheduler.getPendingJob(PERIODIC)==null) check(scheduler.schedule(JobInfo.Builder(PERIODIC,component)
            .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPersisted(true).setPeriodic(15*60*1000L).build())==JobScheduler.RESULT_SUCCESS)
        if (scheduler.getPendingJob(NOW)==null) check(scheduler.schedule(JobInfo.Builder(NOW,component)
            .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPersisted(true)
            .setBackoffCriteria(30_000,JobInfo.BACKOFF_POLICY_EXPONENTIAL).build())==JobScheduler.RESULT_SUCCESS)
    }
    fun cancel(context: Context) {
        context.getSystemService(JobScheduler::class.java).apply { cancel(NOW);cancel(PERIODIC) }
    }
}

class SyncJob: JobService() {
    private companion object { const val TAG="ColetaSync" }
    private val executor=Executors.newSingleThreadExecutor()
    private val running=ConcurrentHashMap<Int,AtomicBoolean>()
    override fun onStartJob(params: JobParameters): Boolean {
        val stopped=AtomicBoolean(false); running[params.jobId]=stopped
        executor.execute {
            var retry=false
            try {
                val vault=SessionVault(this)
                val session=vault.valid()
                if (session!=null && !stopped.get()) {
                    val owner=session.getString("owner")
                    val api=Api(session.getString("base"),session.getString("token"))
                    Store(this).use { store ->
                        try { store.flushTrackingEnd(owner,api) } catch(e:ApiError) {
                            if(e.status==401) vault.clear(owner,api.token)
                            throw e
                        }
                        val sent=VisitSync(store,owner) { body ->
                            check(!stopped.get() && vault.valid()?.optString("token")==api.token) { "Envio interrompido. Entre novamente se necessário." }
                            try { api.request("/motorista/coletas",body) }
                            catch(e:ApiError) {
                                if(e.status==401) vault.clear(owner,api.token)
                                throw e
                            }
                        }.run()
                        if(!stopped.get() && vault.valid()?.optString("token")==api.token)
                            runCatching { CallAlerts.check(this,api,owner) }
                        Log.i(TAG,"Sincronização em segundo plano concluída: $sent registro(s).")
                    }
                } else {
                    Log.w(TAG,"Sincronização em segundo plano ignorada: sessão indisponível ou execução interrompida.")
                }
            } catch (e:ApiError) {
                // Revocation/expiry stops automatic retries until a fresh login.
                retry=e.status!=401
                Log.w(TAG,"Sincronização em segundo plano falhou com HTTP ${e.status}; retentar=$retry.")
            } catch (e:Exception) {
                retry=!stopped.get()
                Log.w(TAG,"Sincronização em segundo plano falhou com ${e.javaClass.simpleName}; retentar=$retry.")
            }
            finally {
                if (!stopped.get()) jobFinished(params,retry)
                running.remove(params.jobId,stopped)
            }
        }
        return true
    }
    override fun onStopJob(params: JobParameters): Boolean { running.remove(params.jobId)?.set(true);return true }
    override fun onDestroy() { running.values.forEach { it.set(true) };executor.shutdownNow();super.onDestroy() }
}
