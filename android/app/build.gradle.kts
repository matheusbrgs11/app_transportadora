plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
val productionStore = System.getenv("COLETA_KEYSTORE_FILE")
val productionStorePassword = System.getenv("COLETA_KEYSTORE_PASSWORD")
val productionAlias = System.getenv("COLETA_KEY_ALIAS")
val productionKeyPassword = System.getenv("COLETA_KEY_PASSWORD")
val productionSigningReady = listOf(productionStore,productionStorePassword,productionAlias,productionKeyPassword).all { !it.isNullOrBlank() }
android {
    testOptions {
        unitTests.isIncludeAndroidResources = true
        unitTests.all {
            it.maxHeapSize = "1g"
            it.maxParallelForks = 1
            it.jvmArgs("--add-opens=java.base/java.lang=ALL-UNNAMED", "--add-opens=java.base/java.util=ALL-UNNAMED", "--add-opens=java.base/java.io=ALL-UNNAMED", "--add-opens=java.base/java.net=ALL-UNNAMED", "--add-opens=java.base/java.security=ALL-UNNAMED", "--add-opens=java.base/java.text=ALL-UNNAMED", "--add-opens=java.base/jdk.internal.access=ALL-UNNAMED", "--add-opens=java.desktop/java.awt.font=ALL-UNNAMED", "--add-opens=jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED")
        }
    }
    namespace = "br.com.coleta.motorista"
    compileSdk = 35
    defaultConfig {
        applicationId = "br.com.coleta.motorista"
        minSdk = 26
        targetSdk = 35
        versionCode = (System.getenv("COLETA_VERSION_CODE") ?: "1").toInt()
        versionName = System.getenv("COLETA_VERSION_NAME") ?: "0.1.0"
    }
    signingConfigs {
        if(productionSigningReady) create("production") {
            storeFile = file(productionStore!!)
            storePassword = productionStorePassword
            keyAlias = productionAlias
            keyPassword = productionKeyPassword
        }
    }
    buildTypes {
        getByName("release") {
            if(productionSigningReady) signingConfig = signingConfigs.getByName("production")
        }
        create("usb") {
            initWith(getByName("release"))
            applicationIdSuffix = ".homologacao.usb"
            versionNameSuffix = "-usb"
            signingConfig = signingConfigs.getByName("debug")
            isDebuggable = false
            matchingFallbacks += listOf("release")
        }
        create("staging") {
            initWith(getByName("release"))
            applicationIdSuffix = ".homologacao"
            versionNameSuffix = "-homologacao"
            signingConfig = signingConfigs.getByName("debug")
            isDebuggable = false
            matchingFallbacks += listOf("release")
        }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.17")
}
