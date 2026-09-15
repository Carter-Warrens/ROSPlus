//! Versioned C ABI for native nodes loaded into a dedicated runtime process.
use crate::{heartbeat::Heartbeat, ros::RosNode, scheduler};
use libloading::{Library, Symbol};
use rosplus_plugin_api::{DescriptorV1, ABI_VERSION, PUBLISHER, SUBSCRIBER};
use serde_json::json;
use signal_hook::consts::{SIGINT, SIGTERM};
use std::{
    ffi::{c_char, c_int, c_void, CString},
    mem::size_of,
    path::Path,
    ptr,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::{Duration, Instant},
};

type Entry = unsafe extern "C" fn() -> *const DescriptorV1;

pub struct Options<'a> {
    pub plugin: &'a str,
    pub adapter: &'a str,
    pub messages: usize,
    pub timeout: Duration,
    pub fifo: bool,
    pub arguments: &'a [String],
    pub heartbeat: &'a mut Heartbeat,
}

struct Instance {
    state: *mut c_void,
    shutdown: Option<rosplus_plugin_api::Lifecycle>,
    destroy: rosplus_plugin_api::Lifecycle,
}
impl Drop for Instance {
    fn drop(&mut self) {
        unsafe {
            if let Some(shutdown) = self.shutdown {
                shutdown(self.state);
            }
            (self.destroy)(self.state);
        }
    }
}

fn error_text(buffer: &[c_char]) -> String {
    let length = buffer
        .iter()
        .position(|value| *value == 0)
        .unwrap_or(buffer.len());
    let bytes: Vec<u8> = buffer[..length].iter().map(|value| *value as u8).collect();
    String::from_utf8_lossy(&bytes).into_owned()
}

pub fn run(options: Options<'_>) -> Result<(), Box<dyn std::error::Error>> {
    if options.messages > 1_000_000 {
        return Err("invalid plugin message count or timeout".into());
    }
    let canonical = Path::new(options.plugin).canonicalize()?;
    options.heartbeat.beat(true)?;
    if canonical.extension().and_then(|v| v.to_str()) != Some("so") {
        return Err("native plugin must be a .so shared library".into());
    }
    unsafe {
        let library = Library::new(&canonical)?;
        let entry: Symbol<Entry> = library.get(b"rosplus_native_node_v1")?;
        let descriptor_ptr = entry();
        if descriptor_ptr.is_null() {
            return Err("native plugin returned a null descriptor".into());
        }
        let descriptor = &*descriptor_ptr;
        if descriptor.abi_version != ABI_VERSION
            || descriptor.struct_size as usize != size_of::<DescriptorV1>()
        {
            return Err(format!(
                "unsupported native plugin ABI {} (descriptor size {})",
                descriptor.abi_version, descriptor.struct_size
            )
            .into());
        }
        if descriptor.direction != PUBLISHER && descriptor.direction != SUBSCRIBER {
            return Err("native plugin direction must be publisher or subscriber".into());
        }
        if descriptor.name.is_null() || descriptor.topic.is_null() {
            return Err("native plugin name and topic are required".into());
        }
        if descriptor.name_length == 0
            || descriptor.name_length > 64
            || descriptor.topic_length == 0
            || descriptor.topic_length > 255
        {
            return Err("native plugin name or topic length is invalid".into());
        }
        let name = std::str::from_utf8(std::slice::from_raw_parts(
            descriptor.name.cast::<u8>(),
            descriptor.name_length,
        ))?;
        let topic = std::str::from_utf8(std::slice::from_raw_parts(
            descriptor.topic.cast::<u8>(),
            descriptor.topic_length,
        ))?;
        if name.is_empty()
            || !name.bytes().all(|c| c.is_ascii_alphanumeric() || c == b'_')
            || !topic.starts_with('/')
        {
            return Err("native plugin contains an invalid node name or topic".into());
        }
        let create = descriptor.create.ok_or("native plugin is missing create")?;
        let tick = descriptor.tick.ok_or("native plugin is missing tick")?;
        let destroy = descriptor
            .destroy
            .ok_or("native plugin is missing destroy")?;
        let c_arguments: Vec<CString> = options
            .arguments
            .iter()
            .map(|v| CString::new(v.as_str()))
            .collect::<Result<_, _>>()?;
        let argument_ptrs: Vec<*const c_char> = c_arguments.iter().map(|v| v.as_ptr()).collect();
        let mut error = [0 as c_char; 1024];
        let state = create(
            argument_ptrs.len() as c_int,
            argument_ptrs.as_ptr(),
            error.as_mut_ptr(),
            error.len(),
        );
        if state.is_null() {
            return Err(format!("native plugin create failed: {}", error_text(&error)).into());
        }
        let _instance = Instance {
            state,
            shutdown: descriptor.shutdown,
            destroy,
        };
        let scheduling = if options.fifo {
            scheduler::configure(20, None, false)
        } else {
            scheduler::Scheduling {
                policy: "normal".into(),
                cpu: None,
                memory_locked: false,
                warnings: vec![],
            }
        };
        println!(
            "{}",
            json!({"event":"plugin_loaded","abi_version":ABI_VERSION,"name":name,"topic":topic,"direction":descriptor.direction,"library":canonical,"scheduling":scheduling})
        );
        let mut ros = RosNode::new(
            options.adapter,
            name,
            topic,
            descriptor.direction == PUBLISHER,
        )?;
        let mut output = vec![0u8; 1024 * 1024];
        let stop = Arc::new(AtomicBool::new(false));
        signal_hook::flag::register(SIGINT, stop.clone())?;
        signal_hook::flag::register(SIGTERM, stop.clone())?;
        let mut completed = 0usize;
        let deadline = (!options.timeout.is_zero()).then(|| Instant::now() + options.timeout);
        let period = Duration::from_micros(descriptor.period_us.clamp(100, 60_000_000));
        let mut next_tick = Instant::now();
        let mut wcet = Duration::ZERO;
        let mut missed_deadlines = 0u64;
        let mut consecutive_overruns = 0u8;
        while !stop.load(Ordering::Relaxed)
            && (options.messages == 0 || completed < options.messages)
            && deadline.is_none_or(|value| Instant::now() < value)
        {
            options.heartbeat.beat(false)?;
            let input = if descriptor.direction == SUBSCRIBER {
                match ros.take()? {
                    Some(message) => message.into_bytes(),
                    None => {
                        options
                            .heartbeat
                            .wait_until(Instant::now() + Duration::from_millis(1))?;
                        continue;
                    }
                }
            } else {
                vec![]
            };
            error.fill(0);
            let mut output_len = 0usize;
            let tick_started = Instant::now();
            let status = tick(
                state,
                if input.is_empty() {
                    ptr::null()
                } else {
                    input.as_ptr()
                },
                input.len(),
                output.as_mut_ptr(),
                output.len(),
                &mut output_len,
                error.as_mut_ptr(),
                error.len(),
            );
            let tick_time = tick_started.elapsed();
            options.heartbeat.beat(true)?;
            wcet = wcet.max(tick_time);
            if tick_time > period {
                missed_deadlines += 1;
            }
            if tick_time > period.mul_f64(1.1) {
                consecutive_overruns += 1;
            } else {
                consecutive_overruns = 0;
            }
            if status < 0 {
                return Err(format!("native plugin tick failed: {}", error_text(&error)).into());
            }
            if output_len > output.len() {
                return Err("native plugin reported output beyond buffer capacity".into());
            }
            if descriptor.direction == PUBLISHER && status == 1 {
                let message = std::str::from_utf8(&output[..output_len])?;
                ros.publish(message)?;
                println!("{}", json!({"event":"plugin_published","message":message}));
            } else if descriptor.direction == SUBSCRIBER {
                println!(
                    "{}",
                    json!({"event":"plugin_received","message":String::from_utf8(input)?})
                );
            }
            if consecutive_overruns >= 3 {
                return Err(
                    "native plugin disabled after three consecutive callback budget overruns"
                        .into(),
                );
            }
            completed += 1;
            if descriptor.direction == PUBLISHER {
                next_tick += period;
                let now = Instant::now();
                if next_tick > now {
                    options.heartbeat.wait_until(next_tick)?;
                }
            }
        }
        if options.messages > 0 && completed < options.messages && !stop.load(Ordering::Relaxed) {
            return Err(format!(
                "native plugin completed {completed}/{} ticks before timeout",
                options.messages
            )
            .into());
        }
        println!(
            "{}",
            json!({"event":"plugin_summary","name":name,"completed":completed,"stopped":stop.load(Ordering::Relaxed),"wcet_us":wcet.as_secs_f64()*1e6,"missed_deadlines":missed_deadlines})
        );
        drop(ros);
        drop(_instance);
        drop(library);
    }
    Ok(())
}
