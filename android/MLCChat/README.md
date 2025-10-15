# MLC-LLM Android

Checkout [Documentation page](https://llm.mlc.ai/docs/deploy/android.html) for more information.

## Preparing the project

1. Run the Android build diagnostic to verify that the SDK, NDK and required
   command line tools are installed:

   ```bash
   python android/diagnose_android_build.py
   ```

   The diagnostic highlights missing prerequisites (such as `ANDROID_SDK_ROOT`,
   `ANDROID_NDK`, `JAVA_HOME`, or the Rust `aarch64-linux-android` target) before
   you attempt to assemble the APK.

2. Build the precompiled runtime and package the chat models:

   ```bash
   python android/mlc4j/prepare_libs.py
   mlc_llm package --mlc-llm-source-dir . --package-config android/MLCChat/mlc-package-config.json --output android/MLCChat/dist
   ```

3. Open this `MLCChat/` folder as a project in Android Studio and build the
   desired APK variant.
