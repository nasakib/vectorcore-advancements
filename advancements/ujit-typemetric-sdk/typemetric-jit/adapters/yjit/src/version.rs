//! YJIT Block Version Pruner and Bit-Packed Context State
//!
//! Replaces YJIT's hard version ceiling (defaulting to 4 versions per basic block)
//! with continuous Metric k-Center diversity pruning.

use crate::value::RubyValType;
use crate::sys::{tm_gonzalez_select, tm_type_vector_t, tm_vector_init, tm_metric_config_t};

pub const MAX_PARAMS: usize = 8;
pub const MAX_BLOCK_VERSIONS: usize = 64;

/// Represents a compiled YJIT block version
#[derive(Debug, Clone)]
pub struct YjitBlockVersion {
    pub block_id: u32,
    pub code_offset: u32,
    pub exec_count: u32,
    pub param_types: [RubyValType; MAX_PARAMS],
    pub num_params: u8,
}

/// Bit-packed context state for rapid `ctx.get_local_type()` matching.
/// Compresses up to 8 local variable types into a single 64-bit scalar key.
#[repr(transparent)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default)]
pub struct PackedContextKey(pub u64);

impl PackedContextKey {
    #[inline(always)]
    pub fn from_types(types: &[RubyValType]) -> Self {
        let mut key: u64 = 0;
        let len = types.len().min(MAX_PARAMS);
        for (i, &t) in types.iter().take(len).enumerate() {
            key |= (t.as_type_id() as u64) << (i * 8);
        }
        PackedContextKey(key)
    }

    #[inline(always)]
    pub fn matches(&self, other: &PackedContextKey) -> bool {
        self.0 == other.0
    }
}

/// Selects K diverse representative versions from a set of candidate versions
/// using Gonzalez Farthest-Point Sampling on the Ruby type manifold.
pub fn prune_block_versions(
    versions: &[YjitBlockVersion],
    target_k: usize,
    hottest_idx: usize,
    cfg: &tm_metric_config_t,
) -> Result<Vec<usize>, i32> {
    if versions.is_empty() {
        return Ok(Vec::new());
    }
    if versions.len() <= target_k {
        return Ok((0..versions.len()).collect());
    }

    let n = versions.len().min(MAX_BLOCK_VERSIONS);
    let mut raw_candidates: [tm_type_vector_t; MAX_BLOCK_VERSIONS] = unsafe { std::mem::zeroed() };

    for (i, v) in versions.iter().take(n).enumerate() {
        let mut kinds = [0u8; MAX_PARAMS];
        for p in 0..(v.num_params as usize).min(MAX_PARAMS) {
            kinds[p] = v.param_types[p].as_type_id();
        }
        unsafe {
            tm_vector_init(
                &mut raw_candidates[i],
                kinds.as_ptr(),
                v.num_params,
                v.code_offset,
            );
        }
    }

    let mut selected = vec![0usize; target_k];
    let status = unsafe {
        tm_gonzalez_select(
            raw_candidates.as_ptr(),
            n,
            target_k,
            hottest_idx,
            selected.as_mut_ptr(),
            cfg,
        )
    };

    if status == 0 {
        Ok(selected)
    } else {
        Err(status)
    }
}
