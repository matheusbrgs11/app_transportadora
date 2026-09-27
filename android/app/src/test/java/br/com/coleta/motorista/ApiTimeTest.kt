package br.com.coleta.motorista

import java.time.ZoneId
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
class ApiTimeTest {
    @Test fun historyAndShiftDatesAcceptOffsetsAndUtc() {
        val expected=ApiTime.parse("2026-09-27T11:00:00Z")
        assertEquals(expected,ApiTime.parse("2026-09-27T08:00:00-03:00"))
        assertEquals(expected,ApiTime.parse("2026-09-27T13:00:00+02:00"))
        assertEquals("2026-09-27",ApiTime.parse("2026-09-28T01:00:00+00:00")
            .atZone(ZoneId.of("America/Sao_Paulo")).toLocalDate().toString())
        assertEquals(123456000,ApiTime.parse("2026-09-27T08:00:00.123456-03:00").nano)
    }
}
