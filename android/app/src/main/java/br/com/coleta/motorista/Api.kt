package br.com.coleta.motorista

import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

class ApiError(val status: Int, message: String) : Exception(message)
class Api(val base: String, var token: String = "") {
    fun request(path: String, body: JSONObject? = null): JSONObject {
        val connection = URL(base + path).openConnection() as HttpURLConnection
        try {
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 15000; connection.readTimeout = 20000
            if (token.isNotBlank()) connection.setRequestProperty("Authorization", "Bearer $token")
            if (body != null) {
                connection.requestMethod = "POST"; connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val code = connection.responseCode
            val raw = (if (code in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
            if (code !in 200..299) throw ApiError(code, if (code==401) "Sessão expirada. Entre novamente; os registros continuam salvos." else "Envio recusado ($code). Confira com a operação. $raw")
            return if (raw.isBlank()) JSONObject() else JSONObject(raw)
        } finally { connection.disconnect() }
    }
}
