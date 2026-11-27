//! Typemetric Rust adapter for Ruby YJIT
//! Provides high-level idiomatic bindings to the core C99 typemetric engine.

pub mod value;
pub mod version;

pub mod sys {
    use libc::{size_t, uint8_t, uint16_t, uint32_t, uint64_t};

    pub const TM_MAX_PARAMS: usize = 8;
    pub const TM_MAX_CANDIDATES: usize = 64;
    pub const TM_MAX_TYPES: usize = 32;

    #[repr(C)]
    #[derive(Debug, Clone, Copy)]
    pub struct tm_type_vector_t {
        pub scalar_key: uint64_t,
        pub kinds: [uint8_t; TM_MAX_PARAMS],
        pub arity: uint8_t,
        pub flags: uint8_t,
        pub reserved: uint16_t,
        pub payload: uint32_t,
    }

    #[repr(C)]
    #[derive(Debug, Clone, Copy)]
    pub struct tm_metric_config_t {
        pub dist_matrix: [[uint16_t; TM_MAX_TYPES]; TM_MAX_TYPES],
        pub param_weights: [uint16_t; TM_MAX_PARAMS],
        pub custom_dist: Option<extern "C" fn(uint8_t, uint8_t, *mut libc::c_void) -> uint32_t>,
        pub user_ctx: *mut libc::c_void,
    }

    extern "C" {
        pub fn tm_vector_init(
            vec: *mut tm_type_vector_t,
            kinds: *const uint8_t,
            arity: uint8_t,
            payload: uint32_t,
        ) -> libc::c_int;

        pub fn tm_metric_config_init_default(cfg: *mut tm_metric_config_t);

        pub fn tm_vector_distance(
            a: *const tm_type_vector_t,
            b: *const tm_type_vector_t,
            cfg: *const tm_metric_config_t,
        ) -> uint32_t;

        pub fn tm_gonzalez_select(
            candidates: *const tm_type_vector_t,
            candidate_count: size_t,
            k: size_t,
            primary_idx: size_t,
            out_indices: *mut size_t,
            cfg: *const tm_metric_config_t,
        ) -> libc::c_int;
    }
}
