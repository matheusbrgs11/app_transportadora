package br.com.coleta.motorista

import java.net.ServerSocket
import java.net.InetSocketAddress
import java.io.IOException
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
class ApiTest {
    @Test fun rejectsRedirectWithoutForwardingCredentialsAndExplainsNonApiResponse() {
        val server=ServerSocket(0,4,java.net.InetAddress.getByName("127.0.0.1"))
        var destinationHit=false
        val worker=Thread {
            try {
                while(!server.isClosed) server.accept().use { socket ->
                    socket.soTimeout=5000
                    val input=socket.getInputStream().bufferedReader()
                    val path=input.readLine().split(" ")[1]
                    while(!input.readLine().isNullOrEmpty()) {}
                    val response=when(path) {
                        "/redirect" -> "HTTP/1.1 302 Found\r\nLocation: /destination\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                        "/destination" -> { destinationHit=true;"HTTP/1.1 204 No Content\r\nConnection: close\r\n\r\n" }
                        else -> "HTTP/1.1 200 OK\r\nContent-Length: 18\r\nConnection: close\r\n\r\n<html>proxy</html>"
                    }
                    socket.getOutputStream().write(response.toByteArray())
                }
            } catch(_:java.net.SocketException) { }
        }.apply { isDaemon=true;start() }
        try {
            val api=Api("http://127.0.0.1:${server.localPort}","private-token")
            try { api.request("/redirect");fail("Redirect accepted") } catch(e:ApiError) {
                assertEquals(302,e.status);assertTrue(e.message!!.contains("redireciona"))
            }
            assertFalse(destinationHit)
            try { api.request("/html");fail("HTML accepted") } catch(e:IOException) {
                assertTrue(e.message!!.contains("endereço"))
            }
        } finally { server.close();worker.join(2000) }
    }
    @Test fun serverErrorsDoNotExposeHtmlAndValidationRemainsUseful() {
        assertFalse(ApiMessages.refusal(502,"<html>private upstream details</html>").contains("private upstream"))
        assertTrue(ApiMessages.refusal(422,"""{"detail":[{"msg":"Informe o motivo"}]}""").contains("Informe o motivo"))
        assertTrue(ApiMessages.refusal(401,"anything").contains("registros continuam salvos"))
    }
}
