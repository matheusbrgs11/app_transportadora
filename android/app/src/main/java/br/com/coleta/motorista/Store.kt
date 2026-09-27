package br.com.coleta.motorista

import android.content.Context
import android.content.ContentValues
import android.database.sqlite.SQLiteOpenHelper
import android.database.sqlite.SQLiteDatabase
import org.json.JSONObject

class Store(context: Context) : SQLiteOpenHelper(context, "coleta.db", null, 3), java.io.Closeable {
    private fun drafts(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE drafts(owner TEXT NOT NULL, stop TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(owner,stop))")
    }
    override fun onCreate(db: SQLiteDatabase) {
        drafts(db)
        trackingTable(db)
        db.execSQL("CREATE TABLE cache(owner TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        db.execSQL("CREATE TABLE visits(id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL, error TEXT NOT NULL)")
    }
    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) drafts(db)
        if (oldVersion < 3) trackingTable(db)
    }
    private fun trackingTable(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE tracking(owner TEXT PRIMARY KEY,payload TEXT NOT NULL)")
    }
    fun tracking(owner: String): JSONObject? = readableDatabase.rawQuery("SELECT payload FROM tracking WHERE owner=?",arrayOf(owner)).use {
        if(it.moveToFirst()) JSONObject(it.getString(0)) else null
    }
    fun tracking(owner: String, payload: JSONObject) {
        check(writableDatabase.insertWithOnConflict("tracking",null,ContentValues().apply {
            put("owner",owner);put("payload",payload.toString())
        },SQLiteDatabase.CONFLICT_REPLACE)>=0)
    }
    fun endTracking(owner: String) {
        val db=writableDatabase;db.beginTransaction()
        try { tracking(owner)?.let { tracking(owner,it.put("state","ending")) };db.setTransactionSuccessful() }
        finally { db.endTransaction() }
    }
    fun flushTrackingEnd(owner: String, api: Api) {
        val record=tracking(owner) ?: return
        if(record.optString("state")!="ending") return
        try { api.request("/motorista/turnos/${record.getString("id")}/encerrar",JSONObject()) }
        catch(e:ApiError) { if(e.status!=404) throw e }
        // A new start is forbidden while this marker exists.
        writableDatabase.delete("tracking","owner=? AND payload=?",arrayOf(owner,record.toString()))
    }
    fun draft(owner: String, stop: String): JSONObject? = readableDatabase.rawQuery(
        "SELECT payload FROM drafts WHERE owner=? AND stop=?", arrayOf(owner,stop)
    ).use { if(it.moveToFirst()) JSONObject(it.getString(0)) else null }
    fun draft(owner: String, stop: String, payload: JSONObject) {
        check(writableDatabase.insertWithOnConflict("drafts",null,ContentValues().apply {
            put("owner",owner); put("stop",stop); put("payload",payload.toString())
        },SQLiteDatabase.CONFLICT_REPLACE)>=0) { "Falha ao salvar rascunho." }
    }
    fun saveDraftVisit(owner: String, stop: String, body: JSONObject) {
        val db=writableDatabase
        db.beginTransaction()
        try {
            save(owner,body)
            db.delete("drafts","owner=? AND stop=?",arrayOf(owner,stop))
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
    }
    fun cache(owner: String, payload: JSONObject) {
        check(writableDatabase.insertWithOnConflict("cache", null, ContentValues().apply {
            put("owner", owner); put("payload", payload.toString())
        }, SQLiteDatabase.CONFLICT_REPLACE)>=0) { "Falha ao salvar planejamento." }
    }
    fun cached(owner: String): JSONObject? = readableDatabase.rawQuery("SELECT payload FROM cache WHERE owner=?", arrayOf(owner)).use {
        if (it.moveToFirst()) JSONObject(it.getString(0)) else null
    }
    fun save(owner: String, body: JSONObject) {
        writableDatabase.insertOrThrow("visits", null, ContentValues().apply {
            put("id", body.getString("id_local_dispositivo")); put("owner", owner)
            put("payload", body.toString()); put("state", "pending"); put("error", "")
        })
    }
    fun visits(owner: String): List<JSONObject> = readableDatabase.rawQuery(
        "SELECT id,payload,state,error FROM visits WHERE owner=? ORDER BY rowid", arrayOf(owner)
    ).use { cursor -> buildList {
        while (cursor.moveToNext()) add(JSONObject().put("id",cursor.getString(0))
            .put("body",JSONObject(cursor.getString(1))).put("state",cursor.getString(2)).put("error",cursor.getString(3)))
    } }
    fun recoverSending(owner: String) {
        writableDatabase.execSQL("UPDATE visits SET state='pending' WHERE owner=? AND state='sending'",arrayOf(owner))
    }
    fun state(owner: String, id: String, state: String, error: String = "") {
        writableDatabase.update("visits", ContentValues().apply { put("state",state); put("error",error) },
            "owner=? AND id=?", arrayOf(owner,id))
    }
}
