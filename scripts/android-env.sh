#!/usr/bin/env bash
# Carregue com: source scripts/android-env.sh
coleta_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export JAVA_HOME="$coleta_root/.local/toolchains/jdk-17.0.20.1+1"
export ANDROID_HOME="$coleta_root/.local/toolchains/android-sdk"
export GRADLE_USER_HOME="$coleta_root/.local/gradle"
export PATH="$JAVA_HOME/bin:$coleta_root/.local/toolchains/gradle-8.11.1/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
unset coleta_root
