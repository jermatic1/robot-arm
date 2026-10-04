plugins {
    id("com.android.application")
}

// Release signing comes from the environment so the keystore never lives in the repo.
val keystoreFile: String? = System.getenv("TV_KEYSTORE_FILE")

android {
    namespace = "robot.tv"
    compileSdk = 36

    defaultConfig {
        applicationId = "robot.tv"
        minSdk = 28
        targetSdk = 36
        versionCode = System.getenv("TV_VERSION_CODE")?.toInt() ?: 1
        versionName = System.getenv("TV_VERSION_NAME") ?: "dev"
    }

    signingConfigs {
        if (keystoreFile != null) {
            create("release") {
                storeFile = file(keystoreFile)
                storePassword = System.getenv("TV_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("TV_KEY_ALIAS")
                keyPassword = System.getenv("TV_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (keystoreFile != null) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
