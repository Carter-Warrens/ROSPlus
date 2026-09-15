//! Dependency-free types for the ROSPlus native node C ABI.
use std::ffi::{c_char, c_int, c_void};

pub const ABI_VERSION: u32 = 1;
pub const PUBLISHER: u32 = 1;
pub const SUBSCRIBER: u32 = 2;

pub type Create =
    unsafe extern "C" fn(c_int, *const *const c_char, *mut c_char, usize) -> *mut c_void;
pub type Tick = unsafe extern "C" fn(
    *mut c_void,
    *const u8,
    usize,
    *mut u8,
    usize,
    *mut usize,
    *mut c_char,
    usize,
) -> c_int;
pub type Lifecycle = unsafe extern "C" fn(*mut c_void);

#[repr(C)]
pub struct DescriptorV1 {
    pub abi_version: u32,
    pub struct_size: u32,
    pub name: *const c_char,
    pub name_length: usize,
    pub topic: *const c_char,
    pub topic_length: usize,
    pub direction: u32,
    pub period_us: u64,
    pub create: Option<Create>,
    pub tick: Option<Tick>,
    pub shutdown: Option<Lifecycle>,
    pub destroy: Option<Lifecycle>,
}

// A descriptor contains immutable static pointers and function addresses.
unsafe impl Sync for DescriptorV1 {}
