package br.com.coleta.motorista

import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

class ApiError(val status: Int, message: String) : Exception(message)
object ApiMessages {
    fun refusal(code:Int,raw:String):String {
        if(code==401) return "Sessão expirada. Entre novamente; os registros continuam salvos."
        if(code>=500) return "Servidor indisponível ($code). Tente novamente; registros salvos permanecem no aparelho."
        if(code in 300..399) return "O endereço redireciona para outro servidor. Confira a URL fornecida pela transportadora."
        val detail=runCatching { JSONObject(raw).opt("detail") }.getOrNull()
        val message=when(detail) {
            is String -> detail.take(600)
            is org.json.JSONArray -> (0 until detail.length()).take(5).joinToString("\n") {
                val item=detail.optJSONObject(it)
                item?.optString("msg")?.take(120) ?: "Confira os campos informados."
            }
            else -> "Confira o endereço do servidor e os dados informados."
        }
        return "Envio recusado ($code). $message"
    }
}
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
            if (code !in 200..299) throw ApiError(code, ApiMessages.refusal(code,raw))
            return if (raw.isBlank()) JSONObject() else JSONObject(raw)
        } catch(e:javax.net.ssl.SSLException) {
            throw java.io.IOException("Não foi possível validar a conexão HTTPS. Confira o endereço e a data/hora do aparelho.",e)
        } catch(e:java.net.SocketTimeoutException) {
            throw java.io.IOException("O servidor demorou para responder. Tente novamente; os registros salvos foram preservados.",e)
        } catch(e:java.net.ConnectException) {
            throw java.io.IOException("Servidor inacessível. Confira a internet e o endereço. No teste USB, mantenha cabo, encaminhamento e servidor ativos.",e)
        } catch(e:java.net.UnknownHostException) {
            throw java.io.IOException("Endereço do servidor não encontrado. Confira a URL e a conexão.",e)
        } catch(e:org.json.JSONException) {
            throw java.io.IOException("Resposta inesperada. Confira se o endereço informado é o da API da transportadora.",e)
        } finally { connection.disconnect() }
    }
}
