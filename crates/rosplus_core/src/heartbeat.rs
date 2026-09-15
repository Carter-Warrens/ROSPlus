//! Executor progress sent over a private pipe inherited from the supervisor.
use std::{
    fs::File,
    io::Write,
    os::fd::FromRawFd,
    time::{Duration, Instant},
};

pub struct Heartbeat {
    file: Option<File>,
    counter: u64,
    last: Instant,
}

impl Heartbeat {
    pub fn from_env() -> Result<Self, Box<dyn std::error::Error>> {
        let file = match std::env::var("ROSPLUS_EXECUTOR_HEARTBEAT_FD") {
            Ok(value) => {
                let fd: i32 = value.parse()?;
                if fd != 3 {
                    return Err("executor heartbeat must use inherited file descriptor 3".into());
                }
                // The Go supervisor creates and exclusively transfers this descriptor.
                Some(unsafe { File::from_raw_fd(fd) })
            }
            Err(std::env::VarError::NotPresent) => None,
            Err(error) => return Err(error.into()),
        };
        Ok(Self {
            file,
            counter: 0,
            last: Instant::now() - Duration::from_secs(1),
        })
    }

    pub fn beat(&mut self, force: bool) -> std::io::Result<()> {
        if !force && self.last.elapsed() < Duration::from_millis(10) {
            return Ok(());
        }
        if let Some(file) = &mut self.file {
            self.counter = self.counter.wrapping_add(1);
            file.write_all(&self.counter.to_le_bytes())?;
        }
        self.last = Instant::now();
        Ok(())
    }

    pub fn wait_until(&mut self, deadline: Instant) -> std::io::Result<()> {
        while Instant::now() < deadline {
            self.beat(false)?;
            let remaining = deadline.saturating_duration_since(Instant::now());
            std::thread::sleep(remaining.min(Duration::from_millis(5)));
        }
        self.beat(false)
    }
}
