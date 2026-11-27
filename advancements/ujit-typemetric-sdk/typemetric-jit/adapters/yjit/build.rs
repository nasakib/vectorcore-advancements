fn main() {
    println!("cargo:rerun-if-changed=../../core/src");
    println!("cargo:rerun-if-changed=../../core/include");

    cc::Build::new()
        .include("../../core/include")
        .file("../../core/src/metric_space.c")
        .file("../../core/src/gonzalez.c")
        .file("../../core/src/short_key.c")
        .file("../../core/src/trace_stitch.c")
        .flag("-std=c99")
        .flag("-O3")
        .compile("typemetric");
}
