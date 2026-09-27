package br.com.coleta.motorista

import android.net.Uri
import org.json.JSONObject

object Navigation {
    fun confirmed(stop: JSONObject): Boolean = stop.optBoolean("localizacao_confirmada") &&
        !stop.isNull("latitude") && !stop.isNull("longitude") &&
        stop.optDouble("latitude").isFinite() && stop.optDouble("longitude").isFinite() &&
        stop.optDouble("latitude") in -90.0..90.0 && stop.optDouble("longitude") in -180.0..180.0
    fun destination(stop: JSONObject): String = if(confirmed(stop)) "${stop.getDouble("latitude")},${stop.getDouble("longitude")}" else
        listOf("endereco","numero","bairro","cidade","estado","cep").filter { !stop.isNull(it) && stop.optString(it).isNotBlank() }.joinToString(", ") { stop.getString(it) }+", Brasil"
    fun uri(stop: JSONObject): Uri = Uri.parse("https://www.google.com/maps/dir/").buildUpon()
        .appendQueryParameter("api","1").appendQueryParameter("destination",destination(stop))
        .appendQueryParameter("travelmode","driving").appendQueryParameter("dir_action","navigate").build()
}
