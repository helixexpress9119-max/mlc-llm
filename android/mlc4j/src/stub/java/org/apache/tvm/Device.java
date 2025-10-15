package org.apache.tvm;

/**
 * Minimal stub implementation of the TVM {@code Device} API that is only used
 * to satisfy the Android build when the actual tvm4j artifacts are not
 * available. The real implementation is provided by the packaging step.
 */
public final class Device {
    public final int deviceType;
    public final int deviceId;

    public Device(int deviceType, int deviceId) {
        this.deviceType = deviceType;
        this.deviceId = deviceId;
    }

    public static Device opencl() {
        return new Device(0, 0);
    }
}
