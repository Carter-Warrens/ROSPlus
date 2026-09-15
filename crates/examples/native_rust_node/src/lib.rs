use rosplus_plugin_api::{DescriptorV1, ABI_VERSION, PUBLISHER};
use std::{
    ffi::{c_char, c_int, c_void},
    ptr, slice,
};

struct State(u64);

unsafe extern "C" fn create(
    _argc: c_int,
    _argv: *const *const c_char,
    _error: *mut c_char,
    _error_capacity: usize,
) -> *mut c_void {
    Box::into_raw(Box::new(State(0))).cast()
}

unsafe extern "C" fn tick(
    opaque: *mut c_void,
    _input: *const u8,
    _input_length: usize,
    output: *mut u8,
    output_capacity: usize,
    output_length: *mut usize,
    _error: *mut c_char,
    _error_capacity: usize,
) -> c_int {
    if opaque.is_null() || output.is_null() || output_length.is_null() {
        return -1;
    }
    let state = &mut *opaque.cast::<State>();
    let message = format!("ROSPlus Rust plugin {}", state.0);
    if message.len() > output_capacity {
        return -1;
    }
    slice::from_raw_parts_mut(output, output_capacity)[..message.len()]
        .copy_from_slice(message.as_bytes());
    *output_length = message.len();
    state.0 += 1;
    1
}

unsafe extern "C" fn destroy(opaque: *mut c_void) {
    if !opaque.is_null() {
        drop(Box::from_raw(opaque.cast::<State>()));
    }
}

static DESCRIPTOR: DescriptorV1 = DescriptorV1 {
    abi_version: ABI_VERSION,
    struct_size: std::mem::size_of::<DescriptorV1>() as u32,
    name: c"rosplus_native_rust_example".as_ptr(),
    name_length: "rosplus_native_rust_example".len(),
    topic: c"/chatter".as_ptr(),
    topic_length: "/chatter".len(),
    direction: PUBLISHER,
    period_us: 100_000,
    create: Some(create),
    tick: Some(tick),
    shutdown: None,
    destroy: Some(destroy),
};

#[no_mangle]
pub extern "C" fn rosplus_native_node_v1() -> *const DescriptorV1 {
    ptr::addr_of!(DESCRIPTOR)
}
