package br.com.coleta.motorista

import org.json.JSONObject

/** A single account's immutable outbox. A conflict must not block unrelated visits. */
class VisitSync(private val store: Store, private val owner: String,
                private val send: (JSONObject) -> JSONObject) {
    fun run(): Int {
        var sent = 0
        for (record in store.visits(owner).filter { it.getString("state") != "sent" }) {
            val id = record.getString("id")
            try {
                val receipt = send(record.getJSONObject("body"))
                // Never acknowledge a redirect, empty response or malformed success as delivery.
                java.util.UUID.fromString(receipt.getString("id"))
                check(receipt.getString("status") == "concluida") { "Resposta de confirmação inválida. Registro preservado." }
                store.state(owner, id, "sent")
                sent++
            } catch (e: ApiError) {
                val conflict = e.status in listOf(403, 409, 422)
                store.state(owner, id, if (conflict) "conflict" else "pending", e.message ?: "Falha no envio")
                if (!conflict) throw e
            } catch (e: Exception) {
                store.state(owner, id, "pending", e.message ?: "Falha no envio")
                throw e
            }
        }
        return sent
    }
}
