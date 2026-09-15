//! Conservative allocation enforcement using Rust's stable const-function rules.
//! This intentionally accepts only const-compatible computation. I/O, mutexes,
//! arbitrary callbacks and non-const library calls are rejected, even if they
//! happen not to allocate. Pass borrowed buffers into annotated kernels.
//!
//! ```
//! use rosplus_macros::no_alloc;
//! #[no_alloc]
//! fn sum(a: u32, b: u32) -> u32 { a + b }
//! assert_eq!(sum(2, 3), 5);
//! ```
//!
//! Heap allocation fails compilation:
//! ```compile_fail
//! use rosplus_macros::no_alloc;
//! #[no_alloc]
//! fn allocate() -> Box<u32> { Box::new(1) }
//! ```
//!
//! Calls through an allocation-capable helper also fail:
//! ```compile_fail
//! use rosplus_macros::no_alloc;
//! fn hidden() -> Box<u32> { Box::new(1) }
//! #[no_alloc]
//! fn indirect() -> Box<u32> { hidden() }
//! ```
use proc_macro::TokenStream;
use quote::quote;
use syn::{parse_macro_input, ItemFn};

#[proc_macro_attribute]
pub fn no_alloc(arguments: TokenStream, item: TokenStream) -> TokenStream {
    if !arguments.is_empty() {
        return syn::Error::new(
            proc_macro::Span::call_site().into(),
            "no_alloc takes no arguments",
        )
        .to_compile_error()
        .into();
    }
    let mut function = parse_macro_input!(item as ItemFn);
    if function.sig.asyncness.is_some() {
        return syn::Error::new_spanned(&function.sig, "no_alloc does not support async functions")
            .to_compile_error()
            .into();
    }
    function.sig.constness = Some(Default::default());
    quote!(#function).into()
}
