package br.com.coleta.motorista

import android.app.job.JobInfo
import android.app.job.JobScheduler
import android.content.Context
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import javax.crypto.KeyGenerator

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
class SessionTest {
    @Test fun leaseExpiresAndRejectsRebootOrClockChanges() {
        val s=SessionPolicy.create("https://test.invalid","a","token",86400,3,1_000_000,1000)
        assertTrue(SessionPolicy.valid(s,1_001_000,2000,3))
        assertFalse(SessionPolicy.valid(s,1_001_000,2000,4))
        assertFalse(SessionPolicy.valid(s,999_999,2000,3))
        assertFalse(SessionPolicy.valid(s,1_000_001,400_000,3))
        assertFalse(SessionPolicy.valid(s,1_000_000+12*60*60*1000,1000+12*60*60*1000,3))
    }
    @Test fun encryptedSessionRoundTripAccountSafeRemovalAndKeyLoss() {
        val c=RuntimeEnvironment.getApplication()
        val prefs=c.getSharedPreferences("session",Context.MODE_PRIVATE);prefs.edit().clear().commit()
        val key=KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()
        val vault=SessionVault(c) { key }
        val s=SessionPolicy.create("https://test.invalid","owner-a","secret-token",3600,1)
        vault.save(s)
        assertFalse(prefs.getString("encrypted","")!!.contains("secret-token"))
        assertEquals(s.toString(),SessionVault(c) { key }.load()!!.toString())
        vault.clear("owner-b");assertNotNull(vault.load())
        vault.clear("owner-a","old-token");assertNotNull(vault.load())
        val wrong=KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()
        assertNull(SessionVault(c) { wrong }.load())
        vault.clear("owner-a","secret-token");assertNull(vault.load())
    }
    @Test fun schedulerRequiresNetworkPersistsAndDoesNotDuplicateJobs() {
        val c=RuntimeEnvironment.getApplication();SyncScheduler.cancel(c)
        SyncScheduler.schedule(c);SyncScheduler.schedule(c)
        val jobs=c.getSystemService(JobScheduler::class.java).allPendingJobs
        assertEquals(2,jobs.size)
        assertTrue(jobs.all { it.isPersisted && it.networkType==JobInfo.NETWORK_TYPE_ANY })
        assertEquals(JobInfo.BACKOFF_POLICY_EXPONENTIAL,jobs.single { !it.isPeriodic }.backoffPolicy)
        assertEquals(30_000L,jobs.single { !it.isPeriodic }.initialBackoffMillis)
        SyncScheduler.cancel(c);assertTrue(c.getSystemService(JobScheduler::class.java).allPendingJobs.isEmpty())
    }
}
