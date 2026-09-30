package br.com.coleta.motorista

import android.location.Location
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import java.time.Instant

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[28])
class TrackingTest {
    @Test fun rejectsOldImpreciseAndFutureFixes() {
        val p=Location("gps").apply { latitude=-16.0;longitude=-49.0;accuracy=12f;time=200_000;elapsedRealtimeNanos=200_000_000_000 }
        assertTrue(TrackingPolicy.acceptable(p,201_000,201_000_000_000))
        assertFalse(TrackingPolicy.acceptable(p,400_000,201_000_000_000))
        assertFalse(TrackingPolicy.acceptable(p,201_000,400_000_000_000))
        assertFalse(TrackingPolicy.acceptable(p,199_000,201_000_000_000))
        p.accuracy=1001f
        assertFalse(TrackingPolicy.acceptable(p,201_000,201_000_000_000))
        assertFalse(TrackingPolicy.afterTurnStart(p,Instant.ofEpochMilli(201_000)))
        assertTrue(TrackingPolicy.afterTurnStart(p,Instant.ofEpochMilli(200_000)))
    }
    @Test fun closingPersistsWithoutChangingAnotherAccount() {
        val context=RuntimeEnvironment.getApplication()
        Store(context).use { db ->
            db.tracking("tracking-a",JSONObject().put("id","first").put("state","active"))
            db.tracking("tracking-b",JSONObject().put("id","second").put("state","active"))
            db.endTracking("tracking-a")
        }
        Store(context).use { db ->
            assertEquals("ending",db.tracking("tracking-a")!!.getString("state"))
            assertEquals("active",db.tracking("tracking-b")!!.getString("state"))
            assertEquals("first",db.tracking("tracking-a")!!.getString("id"))
        }
    }
}
