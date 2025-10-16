package org.apache.tvm;

/**
 * Simple value wrapper mirroring the methods used by {@link Function} in the
 * production tvm4j runtime.
 */
public class TVMValue {
    public Module asModule() {
        return new Module();
    }

    public String asString() {
        return "";
    }
}
