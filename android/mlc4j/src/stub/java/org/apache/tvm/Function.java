package org.apache.tvm;

/**
 * Stubbed {@code Function} that mimics the tvm4j API surface used by the
 * Android client. All operations are no-ops so that the project can be built
 * without the native libraries.
 */
public class Function {
    /** Callback interface mirrored from tvm4j. */
    public interface Callback {
        Object invoke(TVMValue... args);
    }

    public static Function getFunction(String name) {
        return new Function();
    }

    public static Function convertFunc(Callback callback) {
        return new Function();
    }

    public Function pushArg(Object value) {
        return this;
    }

    public TVMValue invoke(Object... args) {
        return new TVMValue();
    }
}
