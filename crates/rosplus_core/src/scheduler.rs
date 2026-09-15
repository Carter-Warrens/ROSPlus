use serde::Serialize;
#[derive(Debug, Serialize)]
pub struct Scheduling {
    pub policy: String,
    pub cpu: Option<usize>,
    pub memory_locked: bool,
    pub warnings: Vec<String>,
}
/// Request capabilities, then report what the kernel actually accepted.
pub fn configure(priority: i32, cpu: Option<usize>, lock_memory: bool) -> Scheduling {
    let mut result = Scheduling {
        policy: "normal".into(),
        cpu: None,
        memory_locked: false,
        warnings: vec![],
    };
    if !(1..=99).contains(&priority) {
        result.warnings.push("FIFO priority must be 1..99".into());
        return result;
    }
    unsafe {
        let param = libc::sched_param {
            sched_priority: priority,
        };
        if libc::sched_setscheduler(0, libc::SCHED_FIFO, &param) == 0 {
            result.policy = "soft_rt".into();
        } else {
            result.warnings.push(format!(
                "SCHED_FIFO unavailable: {}",
                std::io::Error::last_os_error()
            ));
        }
        if let Some(cpu) = cpu {
            if cpu < libc::CPU_SETSIZE as usize {
                let mut set: libc::cpu_set_t = std::mem::zeroed();
                libc::CPU_ZERO(&mut set);
                libc::CPU_SET(cpu, &mut set);
                if libc::sched_setaffinity(0, std::mem::size_of_val(&set), &set) == 0 {
                    result.cpu = Some(cpu);
                } else {
                    result.warnings.push(format!(
                        "CPU affinity unavailable: {}",
                        std::io::Error::last_os_error()
                    ));
                }
            } else {
                result.warnings.push("CPU index out of range".into());
            }
        }
        if lock_memory {
            if libc::mlockall(libc::MCL_CURRENT | libc::MCL_FUTURE) == 0 {
                result.memory_locked = true;
            } else {
                result.warnings.push(format!(
                    "Memory locking unavailable: {}",
                    std::io::Error::last_os_error()
                ));
            }
        }
    }
    result
}
