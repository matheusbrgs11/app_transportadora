package br.com.coleta.motorista

import org.junit.Assert.*
import org.junit.Test
import org.junit.Before
import org.junit.After
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.json.JSONObject
import java.util.UUID

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class OfflineTest {
    private lateinit var store: Store
    private val context get() = RuntimeEnvironment.getApplication()
    private fun body() = JSONObject().put("id_local_dispositivo", UUID.randomUUID().toString()).put("quantidade", 7)
    private fun receipt() = JSONObject().put("id", UUID.randomUUID().toString()).put("status", "concluida")
    @Before fun setup() { context.deleteDatabase("coleta.db"); store = Store(context) }
    @After fun teardown() { store.close(); context.deleteDatabase("coleta.db") }

    @Test fun savedVisitSurvivesDatabaseReopenAndAccountsStayIsolated() {
        val visit = body()
        store.save("companyA|driverA",visit)
        store.cache("companyA|driverA",JSONObject().put("data","2026-09-26"))
        store.close(); store = Store(context)
        assertEquals(visit.toString(),store.visits("companyA|driverA").single().getJSONObject("body").toString())
        assertTrue(store.visits("companyA|driverB").isEmpty())
        assertTrue(store.visits("companyB|driverA").isEmpty())
        assertNull(store.cached("companyB|driverA"))
        store.state("companyB|driverA",visit.getString("id_local_dispositivo"),"sent")
        assertEquals("pending",store.visits("companyA|driverA").single().getString("state"))
        assertEquals("2026-09-26",store.cached("companyA|driverA")!!.getString("data"))
    }
    @Test fun conflictDoesNotBlockNextVisit() {
        val first=body(); store.save("a",first); store.save("a",body())
        val count=VisitSync(store,"a") {
            if(it.getString("id_local_dispositivo")==first.getString("id_local_dispositivo")) throw ApiError(409,"Rota alterada")
            receipt()
        }.run()
        assertEquals(1,count)
        assertEquals(listOf("conflict","sent"),store.visits("a").map { it.getString("state") })
    }
    @Test fun responseLostPreservesSamePayloadForRetry() {
        val visit=body(); store.save("a",visit)
        try { VisitSync(store,"a") { throw java.io.IOException("Resposta perdida") }.run(); fail() } catch (_: java.io.IOException) { }
        val retried=mutableListOf<String>()
        VisitSync(store,"a") { retried.add(it.toString()); receipt() }.run()
        assertEquals(listOf(visit.toString()),retried)
        assertEquals("sent",store.visits("a").single().getString("state"))
        assertEquals(0,VisitSync(store,"a") { fail("Não reenviar confirmado"); receipt() }.run())
    }
    @Test fun expiredSessionStopsQueueWithoutDiscardingAnything() {
        store.save("a",body()); store.save("a",body()); var calls=0
        try { VisitSync(store,"a") { calls++; throw ApiError(401,"Sessão expirada") }.run(); fail() } catch (_: ApiError) { }
        assertEquals(1,calls)
        assertEquals(listOf("pending","pending"),store.visits("a").map { it.getString("state") })
    }
    @Test fun malformedSuccessDoesNotAcknowledgeVisit() {
        store.save("a",body())
        try { VisitSync(store,"a") { JSONObject() }.run(); fail() } catch (_: org.json.JSONException) { }
        assertEquals("pending",store.visits("a").single().getString("state"))
    }

    @Test fun draftSurvivesReopenAndIsRemovedOnlyWithSavedVisit() {
        val draft=JSONObject().put("notes","Portaria dos fundos")
        store.draft("a","route|client|date",draft)
        store.close(); store=Store(context)
        assertEquals(draft.toString(),store.draft("a","route|client|date")!!.toString())
        assertNull(store.draft("b","route|client|date"))
        assertNull(store.draft("a","route|client|otherDate"))
        store.saveDraftVisit("a","route|client|date",body())
        assertNull(store.draft("a","route|client|date"))
        assertEquals(1,store.visits("a").size)
    }
    @Test fun failedSaveKeepsDraftAndOriginalVisit() {
        val visit=body(); store.save("a",visit)
        store.draft("a","stop",JSONObject().put("notes","Preservar"))
        try { store.saveDraftVisit("a","stop",visit); fail() } catch (_: android.database.sqlite.SQLiteConstraintException) { }
        assertEquals("Preservar",store.draft("a","stop")!!.getString("notes"))
        assertEquals(1,store.visits("a").size)
    }
    @Test fun migrationPreservesVersionOneOutbox() {
        store.close(); context.deleteDatabase("coleta.db")
        val db=context.openOrCreateDatabase("coleta.db",0,null)
        db.execSQL("CREATE TABLE cache(owner TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        db.execSQL("CREATE TABLE visits(id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL, error TEXT NOT NULL)")
        val visit=body()
        db.execSQL("INSERT INTO visits VALUES(?,?,?,?,?)",arrayOf(visit.getString("id_local_dispositivo"),"a",visit.toString(),"pending",""))
        db.version=1; db.close()
        store=Store(context)
        assertEquals(visit.toString(),store.visits("a").single().getJSONObject("body").toString())
        store.draft("a","stop",JSONObject().put("notes","Migrado"))
        assertEquals("Migrado",store.draft("a","stop")!!.getString("notes"))
    }
    @Test fun nonattendanceRequiresMatchingReceiptAndSurvivesRetry() {
        val visit=body().put("status","nao_atendida").put("motivo","Cliente fechado")
        store.save("a",visit)
        try { VisitSync(store,"a") { receipt() }.run(); fail() } catch (_:IllegalStateException) {}
        assertEquals("pending",store.visits("a").single().getString("state"))
        store.close(); store=Store(context)
        assertEquals(1,VisitSync(store,"a") {
            assertEquals(visit.toString(),it.toString())
            receipt().put("status","nao_atendida")
        }.run())
        assertEquals("sent",store.visits("a").single().getString("state"))
    }
    @Test fun transferredVisitDoesNotBlockUnrelatedVisit() {
        val visit=body(); store.save("a",visit); store.save("a",body())
        assertEquals(1,VisitSync(store,"a") {
            if(it.getString("id_local_dispositivo")==visit.getString("id_local_dispositivo")) throw ApiError(404,"Atendimento transferido")
            receipt()
        }.run())
        assertEquals(listOf("conflict","sent"),store.visits("a").map { it.getString("state") })
    }

    @Test fun receiptForAnotherAttendanceCannotAcknowledgeVisit() {
        val visit=body().put("coleta_id",UUID.randomUUID().toString()); store.save("a",visit)
        try { VisitSync(store,"a") { receipt() }.run(); fail() } catch (_:IllegalStateException) {}
        assertEquals("pending",store.visits("a").single().getString("state"))
        assertEquals(1,VisitSync(store,"a") { receipt().put("id",visit.getString("coleta_id")) }.run())
    }

}
