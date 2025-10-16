package org.apache.tvm;

/** Stubbed module representation used for builds without native artifacts. */
public class Module {
    public Function getFunction(String name) {
        return new Function();
    }
}
