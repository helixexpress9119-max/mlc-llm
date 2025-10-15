#!/usr/bin/env python3
"""Diagnostic utility for preparing the Android build environment."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
ANDROID_ROOT = REPO_ROOT / "android"
APP_ROOT = ANDROID_ROOT / "MLCChat"
MLC4J_DIST = APP_ROOT / "dist" / "lib" / "mlc4j"
MLC4J_SOURCE = ANDROID_ROOT / "mlc4j"


@dataclass
class CheckResult:
    """Result of a diagnostic check."""

    name: str
    status: str
    details: str
    suggestion: Optional[str] = None

    @property
    def is_ok(self) -> bool:
        return self.status.lower() == "ok"


_OK = "OK"
_WARN = "WARN"
_FAIL = "FAIL"


def _format_result(result: CheckResult) -> str:
    status = result.status.upper()
    suggestion = f" Suggestion: {result.suggestion}" if result.suggestion else ""
    return f"- [{status}] {result.name}: {result.details}.{suggestion}"


def check_env_var(var: str, description: str) -> CheckResult:
    value = os.environ.get(var)
    if value and Path(value).expanduser().exists():
        return CheckResult(var, _OK, f"{description} found at {value}")
    if value:
        return CheckResult(
            var,
            _WARN,
            f"{description} path {value} does not exist",
            suggestion="Verify the path or reinstall the dependency.",
        )
    return CheckResult(
        var,
        _FAIL,
        f"{description} not configured",
        suggestion=f"Set the {var} environment variable to the installation path.",
    )


def check_alternative_env(vars_: Iterable[str], description: str) -> CheckResult:
    for var in vars_:
        value = os.environ.get(var)
        if value and Path(value).expanduser().exists():
            return CheckResult(var, _OK, f"{description} found at {value}")
        if value:
            return CheckResult(
                var,
                _WARN,
                f"{description} path {value} does not exist",
                suggestion="Verify the path or reinstall the dependency.",
            )
    readable = " or ".join(vars_)
    return CheckResult(
        readable,
        _FAIL,
        f"{description} not configured",
        suggestion=f"Set {readable} to your installation path.",
    )


def check_command(name: str, description: str, post_check: Optional[str] = None) -> CheckResult:
    path = shutil.which(name)
    if not path:
        return CheckResult(
            name,
            _FAIL,
            f"{description} not available in PATH",
            suggestion=f"Install {description} and ensure '{name}' is on PATH.",
        )
    if post_check == "rustup_target":
        try:
            completed = subprocess.run(
                [name, "target", "list", "--installed"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as err:
            return CheckResult(
                name,
                _WARN,
                "Rust is available but installed targets could not be determined",
                suggestion=f"Run '{name} target add aarch64-linux-android' manually.\n{err}",
            )
        targets = completed.stdout.split()
        if "aarch64-linux-android" in targets:
            return CheckResult(
                name,
                _OK,
                f"{description} available with aarch64-linux-android target installed",
            )
        return CheckResult(
            name,
            _WARN,
            f"{description} available but missing the aarch64-linux-android target",
            suggestion=f"Run '{name} target add aarch64-linux-android' before building.",
        )
    return CheckResult(name, _OK, f"{description} available at {path}")


def check_path_exists(path: Path, description: str, suggestion: Optional[str] = None) -> CheckResult:
    if path.exists():
        return CheckResult(str(path), _OK, f"{description} available")
    return CheckResult(
        str(path),
        _WARN,
        f"{description} not found",
        suggestion=suggestion,
    )


def check_local_properties() -> CheckResult:
    local_properties = APP_ROOT / "local.properties"
    if not local_properties.exists():
        return CheckResult(
            str(local_properties),
            _WARN,
            "local.properties not found",
            suggestion="Create local.properties with an sdk.dir entry or set ANDROID_HOME.",
        )
    sdk_dir = None
    for line in local_properties.read_text(encoding="utf-8").splitlines():
        if line.startswith("sdk.dir="):
            sdk_dir = line.split("=", 1)[1].strip()
            break
    if sdk_dir:
        sdk_path = Path(sdk_dir)
        if sdk_path.exists():
            return CheckResult(str(local_properties), _OK, f"sdk.dir points to {sdk_path}")
        return CheckResult(
            str(local_properties),
            _WARN,
            f"sdk.dir points to missing path {sdk_path}",
            suggestion="Update sdk.dir to the correct Android SDK location.",
        )
    return CheckResult(
        str(local_properties),
        _WARN,
        "sdk.dir entry missing",
        suggestion="Add sdk.dir=/path/to/android/sdk to local.properties.",
    )


def run_gradle_help() -> CheckResult:
    gradlew = APP_ROOT / "gradlew"
    if not gradlew.exists():
        return CheckResult(
            str(gradlew),
            _FAIL,
            "Gradle wrapper missing",
            suggestion="Restore gradlew to run Gradle tasks.",
        )
    try:
        completed = subprocess.run(
            [str(gradlew), "--version"],
            cwd=APP_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as err:
        return CheckResult(
            "gradlew --version",
            _WARN,
            "Gradle wrapper failed to execute",
            suggestion=f"Investigate Gradle wrapper configuration.\n{err}",
        )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    details = next((line for line in lines if "Gradle" in line), None)
    if details is None:
        details = lines[0] if lines else "Gradle wrapper executed successfully"
    return CheckResult("gradlew", _OK, details)


def main() -> int:
    print("MLC-LLM Android Build Diagnostic\n" + "=" * 35)

    checks: List[CheckResult] = []

    checks.append(check_alternative_env(["ANDROID_SDK_ROOT", "ANDROID_HOME"], "Android SDK"))
    checks.append(check_alternative_env(["ANDROID_NDK", "ANDROID_NDK_HOME"], "Android NDK"))
    checks.append(check_env_var("JAVA_HOME", "JDK"))

    checks.append(check_command("cmake", "CMake"))
    checks.append(check_command("adb", "Android Debug Bridge"))
    checks.append(check_command("rustup", "Rust toolchain", post_check="rustup_target"))

    checks.append(check_local_properties())

    checks.append(
        check_path_exists(
            MLC4J_DIST,
            "Packaged mlc4j Android library",
            suggestion=(
                "Run `python android/mlc4j/prepare_libs.py` after installing the Android NDK "
                "to generate the prebuilt mlc4j artifacts."
            ),
        )
    )

    checks.append(
        check_path_exists(
            APP_ROOT / "mlc-package-config.json",
            "Model packaging configuration",
            suggestion="Create or download mlc-package-config.json for packaging weights.",
        )
    )

    checks.append(run_gradle_help())

    print("\nChecks:")
    for result in checks:
        print(_format_result(result))

    failing = [c for c in checks if not c.is_ok]
    if failing:
        print("\nSummary: Build environment requires attention.")
        for issue in failing:
            if issue.suggestion:
                print(f"  - {issue.name}: {issue.suggestion}")
        print("\nResolve the warnings above before attempting to assemble the APK.")
        return 1

    print("\nSummary: Environment looks ready for building the Android APK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
