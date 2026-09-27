package br.com.coleta.motorista

import java.time.Instant
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter

object ApiTime {
    // Android's Instant parser can reject valid ISO offsets returned by the API.
    fun parse(value: String): Instant =
        OffsetDateTime.parse(value, DateTimeFormatter.ISO_OFFSET_DATE_TIME).toInstant()
}
