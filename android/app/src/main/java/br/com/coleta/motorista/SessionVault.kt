package br.com.coleta.motorista

import android.content.Context
import android.os.SystemClock
import android.provider.Settings
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Credentials are never written in plaintext; no password is stored. */
class SessionVault(private val context: Context, private val keyProvider: (() -> SecretKey)? = null) {
    private val preferences = context.getSharedPreferences("session", Context.MODE_PRIVATE)
    private fun key(): SecretKey {
        keyProvider?.let { return it() }
        val keys=KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keys.getKey("coleta.session.v1",null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder("coleta.session.v1",KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    fun save(session: JSONObject) = synchronized(lock) {
        val cipher=Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE,key()) }
        val blob=Base64.encodeToString(cipher.iv,Base64.NO_WRAP)+":"+Base64.encodeToString(cipher.doFinal(session.toString().toByteArray(Charsets.UTF_8)),Base64.NO_WRAP)
        check(preferences.edit().putString("encrypted",blob).commit()) { "Não foi possível guardar a sessão." }
    }
    fun load(): JSONObject? = synchronized(lock) {
        val blob=preferences.getString("encrypted",null) ?: return@synchronized null
        try {
            val parts=blob.split(':')
            val cipher=Cipher.getInstance("AES/GCM/NoPadding").apply {
                init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,Base64.decode(parts[0],Base64.NO_WRAP)))
            }
            JSONObject(String(cipher.doFinal(Base64.decode(parts[1],Base64.NO_WRAP)),Charsets.UTF_8))
        } catch (_:Exception) { null } // Fail closed; never remove the outbox on key loss.
    }
    fun clear(owner: String? = null, token: String? = null) = synchronized(lock) {
        if ((owner==null || load()?.optString("owner")==owner) && (token==null || load()?.optString("token")==token)) {
            check(preferences.edit().clear().commit()) { "Não foi possível encerrar a sessão local." }
        }
    }
    fun valid(): JSONObject? = load()?.takeIf { SessionPolicy.valid(it,System.currentTimeMillis(),SystemClock.elapsedRealtime(),boot()) }
    fun boot(): Int = Settings.Global.getInt(context.contentResolver,Settings.Global.BOOT_COUNT,-1)
    companion object { private val lock=Any() }
}

object SessionPolicy {
    fun create(base: String, owner: String, token: String, seconds: Long, boot: Int,
               now: Long = System.currentTimeMillis(), elapsed: Long = SystemClock.elapsedRealtime()): JSONObject =
        JSONObject().put("base",base).put("owner",owner).put("token",token).put("issued",now)
            .put("duration",minOf(seconds,12*60*60)*1000).put("elapsed",elapsed).put("boot",boot)
    fun valid(s: JSONObject, now: Long, elapsed: Long, boot: Int): Boolean {
        val age=elapsed-s.getLong("elapsed")
        val wallAge=now-s.getLong("issued")
        return boot>=0 && boot==s.getInt("boot") && age>=0 && age<s.getLong("duration") &&
            wallAge>=0 && wallAge<s.getLong("duration") && kotlin.math.abs(wallAge-age)<5*60*1000
    }
}
