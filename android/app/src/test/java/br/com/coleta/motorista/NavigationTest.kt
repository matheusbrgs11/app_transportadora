package br.com.coleta.motorista

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
class NavigationTest {
    @Test fun confirmedPointIsUsedIncludingZeroWithoutExposingClientIdentity() {
        val stop=JSONObject().put("localizacao_confirmada",true).put("latitude",0.0).put("longitude",-49.25)
            .put("nome","Private client").put("cnpj","private").put("telefone","private")
        val uri=Navigation.uri(stop)
        assertEquals("https",uri.scheme);assertEquals("www.google.com",uri.host)
        assertEquals("0.0,-49.25",uri.getQueryParameter("destination"))
        assertEquals("1",uri.getQueryParameter("api"))
        assertEquals("navigate",uri.getQueryParameter("dir_action"))
        assertFalse(uri.toString().contains("private",ignoreCase=true))
    }
    @Test fun oldOrUnconfirmedPlansUseEncodedAddressAndCannotInjectParameters() {
        val stop=JSONObject().put("endereco","Rua São José & origin=outro").put("numero","20")
            .put("cidade","Goiânia").put("estado","GO").put("latitude",50).put("longitude",80)
        assertFalse(Navigation.confirmed(stop))
        val uri=Navigation.uri(stop)
        assertNull(uri.getQueryParameter("origin"))
        assertEquals("Rua São José & origin=outro, 20, Goiânia, GO, Brasil",uri.getQueryParameter("destination"))
        stop.put("localizacao_confirmada",true).put("latitude",91)
        assertFalse(Navigation.confirmed(stop))
    }
}
