#!/bin/bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
sdk_root="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Library/Android/sdk}}"
build_tools="${IRONBOUND_BUILD_TOOLS:-$sdk_root/build-tools/34.0.0}"
android_jar="${IRONBOUND_ANDROID_JAR:-$sdk_root/platforms/android-34/android.jar}"
out="$repo_root/.tools/ironbound-probe-build"
src="$repo_root/tools/ironbound-probe"
mkdir -p "$out/classes" "$out/dex"
javac -source 8 -target 8 -bootclasspath "$android_jar" -d "$out/classes" "$src/src/app/ironbound/probe/CaptureService.java"
jar cf "$out/classes.jar" -C "$out/classes" .
"$build_tools/d8" --min-api 23 --lib "$android_jar" --output "$out/dex" "$out/classes.jar"
"$build_tools/aapt2" link -I "$android_jar" --manifest "$src/AndroidManifest.xml" -o "$out/unsigned.apk"
(cd "$out/dex" && zip -q -u "$out/unsigned.apk" classes.dex)
"$build_tools/zipalign" -f 4 "$out/unsigned.apk" "$out/aligned.apk"
if [[ ! -f "$out/probe-debug.jks" ]]; then
    keytool -genkeypair -keystore "$out/probe-debug.jks" -storepass android -keypass android \
        -alias probe -dname 'CN=IRONBOUND Diagnostic' -keyalg RSA -keysize 2048 -validity 3650 -noprompt >/dev/null 2>&1
fi
"$build_tools/apksigner" sign --ks "$out/probe-debug.jks" --ks-key-alias probe \
    --ks-pass pass:android --key-pass pass:android --out "$out/ironbound-probe.apk" "$out/aligned.apk"
"$build_tools/apksigner" verify --verbose "$out/ironbound-probe.apk"
echo "$out/ironbound-probe.apk"
