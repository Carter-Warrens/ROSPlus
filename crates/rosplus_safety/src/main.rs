use std::{
    fs::OpenOptions,
    io::Write,
    os::unix::{fs::PermissionsExt, net::UnixDatagram},
    path::PathBuf,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
fn main() {
    if let Err(e) = run() {
        eprintln!("{e}");
        std::process::exit(1)
    }
}
fn run() -> Result<(), Box<dyn std::error::Error>> {
    let a: Vec<String> = std::env::args().collect();
    let val = |k: &str, d: &str| {
        a.iter()
            .position(|v| v == k)
            .and_then(|i| a.get(i + 1))
            .cloned()
            .unwrap_or(d.into())
    };
    if !a.iter().any(|x| x == "--simulate") {
        return Err(
            "this binary supports --simulate only; physical GPIO is not implemented".into(),
        );
    }
    let path = PathBuf::from(val("--socket", "rosplus-safety.sock"));
    let timeout: u64 = val("--timeout-ms", "50").parse()?;
    if !(5..=1000).contains(&timeout) {
        return Err("timeout must be 5..1000 ms".into());
    }
    let socket = UnixDatagram::bind(&path)?;
    std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600))?;
    socket.set_read_timeout(Some(Duration::from_millis(1)))?;
    let log_path = PathBuf::from(val("--log", "safety-gpio.jsonl"));
    let mut log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)?;
    let mut bytes = log.metadata()?.len();
    let mut event = |state: &str, reason: &str| -> std::io::Result<()> {
        if bytes >= 100 * 1024 * 1024 {
            log.flush()?;
            rotate(&log_path, 9)?;
            log = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&log_path)?;
            bytes = 0;
        }
        let line = serde_json::json!({"timestamp_ns":SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos() as u64,"component":"safety","level":if reason=="E_STOP"{"ERROR"}else{"INFO"},"state":state,"reason":reason,"simulated":true}).to_string();
        writeln!(log, "{line}")?;
        bytes += line.len() as u64 + 1;
        log.flush()
    };
    event("LOW", "WAITING_FOR_HEARTBEAT")?;
    let mut last = None;
    let mut estop = false;
    let mut high = false;
    let mut last_timestamp = 0u64;
    let mut last_pwm = Instant::now();
    loop {
        let mut b = [0u8; 17];
        match socket.recv_from(&mut b) {
            Ok((n, peer)) => {
                if n == 16 {
                    let timestamp = u64::from_le_bytes(b[..8].try_into()?);
                    let flags = u32::from_le_bytes(b[12..16].try_into()?);
                    let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_nanos() as u64;
                    // Check the deadline before accepting a late packet: a trip is latched.
                    if last.is_some_and(|t: Instant| t.elapsed() >= Duration::from_millis(timeout))
                    {
                        estop = true;
                    }
                    if flags & 3 != 3 {
                        estop = true;
                    } else if !estop
                        && timestamp > last_timestamp
                        && now.abs_diff(timestamp) <= timeout * 1_000_000
                    {
                        last = Some(Instant::now());
                        last_timestamp = timestamp;
                    }
                    if let Some(peer) = peer.as_pathname() {
                        let _ = socket.send_to(&[if estop { 1 } else { 0 }], peer);
                    }
                }
            }
            Err(e)
                if e.kind() == std::io::ErrorKind::WouldBlock
                    || e.kind() == std::io::ErrorKind::TimedOut => {}
            Err(e) => return Err(e.into()),
        }
        if last.is_some_and(|t| t.elapsed() >= Duration::from_millis(timeout)) {
            estop = true;
        }
        if estop {
            event("LOW", "E_STOP")?;
            break;
        }
        if last.is_some() && last_pwm.elapsed() >= Duration::from_micros(500) {
            high = !high;
            event(if high { "HIGH" } else { "LOW" }, "PWM_SIMULATED")?;
            last_pwm = Instant::now();
        }
    }
    // A simulated trip exits nonzero so supervisors cannot misreport a healthy monitor.
    std::fs::remove_file(path)?;
    Err("simulated E-Stop latched".into())
}

fn rotate(path: &std::path::Path, retained: usize) -> std::io::Result<()> {
    for index in (0..retained).rev() {
        let from = if index == 0 {
            path.to_path_buf()
        } else {
            PathBuf::from(format!("{}.{}", path.display(), index))
        };
        let to = PathBuf::from(format!("{}.{}", path.display(), index + 1));
        match std::fs::rename(from, to) {
            Ok(()) => {}
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e),
        }
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rotation_retains_recent_files() {
        let dir = std::env::temp_dir().join(format!("rosplus-log-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let p = dir.join("gpio.jsonl");
        for i in 0..4 {
            std::fs::write(&p, i.to_string()).unwrap();
            rotate(&p, 2).unwrap();
        }
        assert_eq!(
            std::fs::read_to_string(dir.join("gpio.jsonl.1")).unwrap(),
            "3"
        );
        assert_eq!(
            std::fs::read_to_string(dir.join("gpio.jsonl.2")).unwrap(),
            "2"
        );
        assert!(!dir.join("gpio.jsonl.3").exists());
        std::fs::remove_dir_all(dir).unwrap();
    }
}
