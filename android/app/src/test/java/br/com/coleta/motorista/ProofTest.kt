package br.com.coleta.motorista

import android.graphics.BitmapFactory
import android.graphics.Color
import android.view.MotionEvent
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.time.Instant
import java.util.UUID

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class ProofTest {
    private val context get()=RuntimeEnvironment.getApplication()
    @Test fun touchProducesRasterAndClearRemovesInk() {
        val pad=SignaturePad(context);pad.layout(0,0,640,240)
        for((action,x) in listOf(MotionEvent.ACTION_DOWN to 20f,MotionEvent.ACTION_MOVE to 120f,MotionEvent.ACTION_UP to 220f)) {
            val e=MotionEvent.obtain(0,1,action,x,60f,0);pad.onTouchEvent(e);e.recycle()
        }
        assertTrue(pad.hasInk())
        val raw=Base64.decode(pad.png(),Base64.NO_WRAP)
        java.io.File("build/test-fixtures/signature-native.png").apply { parentFile.mkdirs();writeBytes(raw) }
        val bitmap=BitmapFactory.decodeByteArray(raw,0,raw.size)
        assertEquals(640,bitmap.width);assertEquals(240,bitmap.height)
        assertEquals(Color.BLACK,bitmap.getPixel(80,60));bitmap.recycle()
        val restored=SignaturePad(context,pad.points());assertTrue(restored.hasInk())
        restored.clear();assertFalse(restored.hasInk())
        try { restored.png();fail("Blank signature must be rejected") } catch(_:IllegalStateException) {}
    }
    @Test fun proofAndImageSurviveOfflineReopenAndLostResponse() {
        context.deleteDatabase("coleta.db")
        var store=Store(context)
        val saved=JSONObject().put("tipo","assinatura").put("responsavel","Pessoa fictícia de teste")
            .put("capturado_em",Instant.now().toString()).put("tracos",JSONArray("[[[20,60],[120,60]]]"))
        val editor=ProofEditor(context,saved) {}
        store.draft("a","stop",JSONObject().put("comprovante",editor.draft()))
        store.close();store=Store(context)
        val restored=ProofEditor(context,store.draft("a","stop")!!.getJSONObject("comprovante")) {}
        val cid=UUID.randomUUID().toString()
        val body=JSONObject().put("id_local_dispositivo",UUID.randomUUID().toString()).put("coleta_id",cid).put("comprovante",restored.proof())
        store.saveDraftVisit("a","stop",body);assertNull(store.draft("a","stop"));assertTrue(store.visits("b").isEmpty())
        try { VisitSync(store,"a") { throw java.io.IOException("Response lost") }.run();fail() } catch(_:java.io.IOException) {}
        store.close();store=Store(context)
        assertEquals(1,VisitSync(store,"a") {
            assertEquals(body.toString(),it.toString());JSONObject().put("id",cid).put("status","concluida")
        }.run())
        assertEquals("sent",store.visits("a").single().getString("state"));store.close();context.deleteDatabase("coleta.db")
    }
    @Test fun exceptionsRequireReasonAndNeverIncludeImage() {
        val saved=JSONObject().put("tipo","recusa").put("motivo","Responsável não quis assinar")
        val proof=ProofEditor(context,saved) {}.proof()
        assertEquals("recusa",proof.getString("tipo"));assertFalse(proof.has("imagem_png"))
        try { ProofEditor(context,JSONObject().put("tipo","ausencia")) {}.proof();fail() } catch(_:IllegalStateException) {}
    }
}
