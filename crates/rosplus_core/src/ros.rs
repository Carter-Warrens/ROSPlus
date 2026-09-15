//! Optional dynamically loaded adapter to stock rcl. String messages only for now.
use libloading::Library;
use std::ffi::{c_char, c_int, c_void, CStr, CString};
type New =
    unsafe extern "C" fn(*const c_char, *const c_char, c_int, *mut c_char, usize) -> *mut c_void;
type Free = unsafe extern "C" fn(*mut c_void);
type Publish = unsafe extern "C" fn(*mut c_void, *const c_char) -> c_int;
type Take = unsafe extern "C" fn(*mut c_void, *mut c_char, usize) -> c_int;
type Error = unsafe extern "C" fn(*mut c_void) -> *const c_char;
pub struct RosNode {
    handle: *mut c_void,
    free: Free,
    publish: Publish,
    take: Take,
    error: Error,
    _library: Library,
    buffer: Vec<c_char>,
}
impl RosNode {
    pub fn new(
        library: &str,
        name: &str,
        topic: &str,
        publisher: bool,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        let name = CString::new(name)?;
        let topic = CString::new(topic)?;
        unsafe {
            let library = Library::new(library)?;
            let new: New = *library.get(b"rosplus_rcl_new")?;
            let free: Free = *library.get(b"rosplus_rcl_free")?;
            let publish: Publish = *library.get(b"rosplus_rcl_publish")?;
            let take: Take = *library.get(b"rosplus_rcl_take")?;
            let error: Error = *library.get(b"rosplus_rcl_error")?;
            let mut err = [0 as c_char; 1024];
            let handle = new(
                name.as_ptr(),
                topic.as_ptr(),
                publisher as c_int,
                err.as_mut_ptr(),
                err.len(),
            );
            if handle.is_null() {
                return Err(CStr::from_ptr(err.as_ptr())
                    .to_string_lossy()
                    .into_owned()
                    .into());
            }
            Ok(Self {
                handle,
                free,
                publish,
                take,
                error,
                _library: library,
                buffer: vec![0; 1024 * 1024 + 1],
            })
        }
    }
    fn error(&self) -> String {
        unsafe {
            CStr::from_ptr((self.error)(self.handle))
                .to_string_lossy()
                .into_owned()
        }
    }
    pub fn publish(&mut self, text: &str) -> Result<(), String> {
        let text = CString::new(text).map_err(|e| e.to_string())?;
        if unsafe { (self.publish)(self.handle, text.as_ptr()) } == 0 {
            Ok(())
        } else {
            Err(self.error())
        }
    }
    pub fn take(&mut self) -> Result<Option<String>, String> {
        let out = &mut self.buffer;
        match unsafe { (self.take)(self.handle, out.as_mut_ptr(), out.len()) } {
            0 => Ok(None),
            1 => unsafe { CStr::from_ptr(out.as_ptr()) }
                .to_str()
                .map(|s| Some(s.to_owned()))
                .map_err(|e| e.to_string()),
            _ => Err(self.error()),
        }
    }
}
impl Drop for RosNode {
    fn drop(&mut self) {
        unsafe { (self.free)(self.handle) }
    }
}
