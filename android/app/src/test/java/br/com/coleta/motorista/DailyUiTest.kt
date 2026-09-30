package br.com.coleta.motorista

import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import org.junit.Test
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.json.JSONObject
import org.json.JSONArray
import java.time.LocalDate
import java.util.UUID

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class DailyUiTest {
    private fun views(v: View): List<View> = listOf(v) + if(v is ViewGroup) (0 until v.childCount).flatMap { views(v.getChildAt(it)) } else emptyList()
    private fun set(a: MainActivity, name: String, value: Any) { MainActivity::class.java.getDeclaredField(name).apply { isAccessible=true }.set(a,value) }
    @Test fun revisitsStayAvailableAndNonattendanceIsSavedOfflineFromScreen() {
        val context=RuntimeEnvironment.getApplication()
        context.deleteDatabase("coleta.db")
        val controller=Robolectric.buildActivity(MainActivity::class.java).setup()
        val a=controller.get()
        val first=UUID.randomUUID().toString(); val second=UUID.randomUUID().toString()
        val route=UUID.randomUUID().toString(); val client=UUID.randomUUID().toString()
        val store=Store(context)
        store.tracking("a",JSONObject().put("state","active"))
        store.save("a",JSONObject().put("id_local_dispositivo",UUID.randomUUID().toString())
            .put("coleta_id",first).put("rota_id",route).put("cliente_id",client).put("concluida_em","2026-05-07T12:00:00Z"))
        fun stop(id:String,attempt:Int,status:String)=JSONObject().put("coleta_id",id).put("cliente_id",client)
            .put("nome","Cliente teste").put("ordem",1).put("tentativa",attempt).put("status",status)
        val plan=JSONObject().put("data",LocalDate.now(java.time.ZoneId.of("UTC")).toString()).put("fuso_horario","UTC")
            .put("rotas",JSONArray().put(JSONObject().put("id",route).put("nome","Rota teste").put("versao",1)
                .put("paradas",JSONArray().put(stop(first,1,"concluida")).put(stop(second,2,"agendada")))))
        set(a,"owner","a");set(a,"day",plan)
        MainActivity::class.java.getDeclaredMethod("home").apply { isAccessible=true }.invoke(a)
        fun buttons()=views(a.findViewById(android.R.id.content)).filterIsInstance<Button>()
        assertTrue(views(a.findViewById(android.R.id.content)).filterIsInstance<TextView>()
            .any { it.text.toString()=="Turno em andamento" })
        assertTrue(buttons().any { it.text.toString()=="Finalizar turno" })
        assertEquals(1,buttons().count { it.text.toString()=="Realizar coleta" })
        buttons().single { it.text.toString()=="Não foi possível atender" }.performClick()
        views(a.findViewById(android.R.id.content)).filterIsInstance<EditText>().single().setText("Portaria fechada")
        buttons().single { it.text.toString().startsWith("Salvar não atendimento") }.performClick()
        val saved=store.visits("a").single { it.getJSONObject("body").optString("coleta_id")==second }
        assertEquals("pending",saved.getString("state"))
        assertEquals("nao_atendida",saved.getJSONObject("body").getString("status"))
        assertEquals("Portaria fechada",saved.getJSONObject("body").getString("motivo"))
        assertFalse(buttons().any { it.text.toString()=="Realizar coleta" })
        controller.pause().stop().destroy(); store.close(); context.deleteDatabase("coleta.db")
    }
    @Test fun dayRolloverBlocksSavingButKeepsTheDraft() {
        val context=RuntimeEnvironment.getApplication();context.deleteDatabase("coleta.db")
        val controller=Robolectric.buildActivity(MainActivity::class.java).setup();val a=controller.get()
        val id=UUID.randomUUID().toString()
        val plan=JSONObject().put("data",LocalDate.now(java.time.ZoneId.of("UTC")).minusDays(1).toString()).put("fuso_horario","UTC")
        val route=JSONObject().put("id",UUID.randomUUID().toString()).put("versao",1)
        val stop=JSONObject().put("coleta_id",id).put("cliente_id",UUID.randomUUID().toString()).put("nome","Cliente").put("tentativa",1)
        set(a,"owner","a")
        MainActivity::class.java.getDeclaredMethod("notAttended",JSONObject::class.java,JSONObject::class.java,JSONObject::class.java)
            .apply { isAccessible=true }.invoke(a,plan,route,stop)
        views(a.findViewById(android.R.id.content)).filterIsInstance<EditText>().single().setText("Preservar motivo")
        views(a.findViewById(android.R.id.content)).filterIsInstance<Button>().single { it.text.toString().startsWith("Salvar não atendimento") }.performClick()
        Store(context).use { store ->
            assertTrue(store.visits("a").isEmpty())
            assertEquals("Preservar motivo",store.draft("a",id+"|nao_atendida")!!.getString("motivo"))
        }
        controller.pause().stop().destroy();context.deleteDatabase("coleta.db")
    }

}
