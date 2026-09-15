use rosplus_core::{pool::Pool, scheduler};
use std::{
    os::unix::net::UnixDatagram,
    sync::Arc,
    time::{Duration, Instant},
};
fn main() {
    if let Err(e) = run() {
        eprintln!("{e}");
        std::process::exit(1)
    }
}
fn run() -> Result<(), Box<dyn std::error::Error>> {
    let a: Vec<String> = std::env::args().collect();
    let command = a.get(1).map(String::as_str).unwrap_or("");
    if command == "plugin-run" {
        return run_plugin(&a[2..]);
    }
    let mut seen = std::collections::HashSet::new();
    let mut index = 2;
    while index < a.len() {
        let option = a[index].as_str();
        if !seen.insert(option) {
            return Err(format!("duplicate option {option}").into());
        }
        let flag = option == "--fifo"
            || (command.starts_with("dds-") && option == "--quiet")
            || (command == "dds-publish" && option == "--latency-payload");
        let value = matches!(option, "--messages" | "--frequency")
            || (command == "benchmark" && matches!(option, "--size" | "--safety-socket"))
            || (command.starts_with("dds-")
                && matches!(
                    option,
                    "--adapter" | "--name" | "--topic" | "--timeout-seconds"
                ))
            || (command == "dds-publish" && option == "--size")
            || (command == "dds-subscribe" && option == "--latency-report");
        if flag {
            index += 1;
        } else if value {
            if a.get(index + 1).is_none_or(|v| v.starts_with("--")) {
                return Err(format!("missing value for {option}").into());
            }
            index += 2;
        } else {
            return Err(format!("unknown option {option} for {command}").into());
        }
    }
    let val = |key: &str, default: &str| {
        a.iter()
            .position(|s| s == key)
            .and_then(|i| a.get(i + 1))
            .cloned()
            .unwrap_or(default.into())
    };
    if matches!(
        a.get(1).map(String::as_str),
        Some("dds-publish" | "dds-subscribe")
    ) {
        let mut heartbeat = rosplus_core::heartbeat::Heartbeat::from_env()?;
        heartbeat.beat(true)?;
        let publisher = a[1] == "dds-publish";
        let count: usize = val("--messages", "10").parse()?;
        let timeout: u64 = val("--timeout-seconds", "15").parse()?;
        if count == 0 || count > 1_000_000 || timeout == 0 || timeout > 3600 {
            return Err("invalid message count or timeout".into());
        }
        let scheduling = if a.iter().any(|v| v == "--fifo") {
            scheduler::configure(20, None, false)
        } else {
            rosplus_core::scheduler::Scheduling {
                policy: "normal".into(),
                cpu: None,
                memory_locked: false,
                warnings: vec![],
            }
        };
        println!(
            "{}",
            serde_json::json!({"event":"scheduling","details":scheduling})
        );
        let mut node = rosplus_core::ros::RosNode::new(
            &val("--adapter", "build/librosplus_rcl.so"),
            &val(
                "--name",
                if publisher {
                    "rosplus_native_talker"
                } else {
                    "rosplus_native_listener"
                },
            ),
            &val("--topic", "/chatter"),
            publisher,
        )?;
        if publisher {
            let hz: f64 = val("--frequency", "10").parse()?;
            if !(1.0..=10000.0).contains(&hz) {
                return Err("DDS frequency must be 1..10000 Hz".into());
            }
            heartbeat.wait_until(Instant::now() + Duration::from_secs(2))?;
            let publish_started = Instant::now();
            let mut next_publish = publish_started;
            let mut missed = 0;
            for i in 0..count {
                heartbeat.beat(false)?;
                let text = if a.iter().any(|v| v == "--latency-payload") {
                    let size: usize = val("--size", "1024").parse()?;
                    if !(64..=1024 * 1024).contains(&size) {
                        return Err("DDS payload must be 64..1048576 bytes".into());
                    }
                    let mut text = format!("rosplus-latency:{i}:{}:", monotonic_ns()?);
                    text.extend(std::iter::repeat_n('x', size.saturating_sub(text.len())));
                    text
                } else {
                    format!("ROSPlus native {i}")
                };
                node.publish(&text)?;
                heartbeat.beat(true)?;
                if !a.iter().any(|v| v == "--quiet") {
                    println!(
                        "{}",
                        serde_json::json!({"event":"published","message":text})
                    );
                }
                next_publish += Duration::from_secs_f64(1.0 / hz);
                let now = Instant::now();
                if next_publish > now {
                    heartbeat.wait_until(next_publish)?;
                } else {
                    missed += 1;
                }
            }
            println!(
                "{}",
                serde_json::json!({"event":"publisher_summary","messages":count,"duration_seconds":publish_started.elapsed().as_secs_f64(),"configured_frequency_hz":hz,"pacing_deadlines_missed":missed})
            );
        } else {
            let deadline = Instant::now() + Duration::from_secs(timeout);
            let mut received = 0;
            let mut latencies = Vec::with_capacity(count);
            while received < count && Instant::now() < deadline {
                heartbeat.beat(false)?;
                if let Some(text) = node.take()? {
                    heartbeat.beat(true)?;
                    received += 1;
                    if text.starts_with("rosplus-latency:") {
                        if let Some(sent) =
                            text.split(':').nth(2).and_then(|v| v.parse::<u64>().ok())
                        {
                            if let Some(elapsed) = monotonic_ns()?.checked_sub(sent) {
                                latencies.push(elapsed as f64 / 1000.0);
                            }
                        }
                    }
                    if !a.iter().any(|v| v == "--quiet") {
                        println!("{}", serde_json::json!({"event":"received","message":text}));
                    }
                } else {
                    heartbeat.wait_until(Instant::now() + Duration::from_millis(1))?;
                }
            }
            let report_path = val("--latency-report", "");
            if !report_path.is_empty() {
                latencies.sort_by(f64::total_cmp);
                let percentile = |q: f64| {
                    if latencies.is_empty() {
                        None
                    } else {
                        Some(latencies[((latencies.len() - 1) as f64 * q).ceil() as usize])
                    }
                };
                let report = serde_json::json!({"benchmark":"dds_cross_process","transport":"stock rcl/RMW std_msgs/msg/String","scheduler":scheduling,"cpu_load":"not controlled","expected_messages":count,"received_messages":received,"latency_samples":latencies.len(),"clock":"CLOCK_MONOTONIC; endpoints must share the same host clock","p50_latency_us":percentile(0.5),"p95_latency_us":percentile(0.95),"p99_latency_us":percentile(0.99),"max_latency_us":latencies.last(),"includes":"payload construction after timestamp, serialization, DDS, wake-up, deserialization and receive copy"});
                std::fs::write(report_path, serde_json::to_vec_pretty(&report)?)?;
                println!("{report}");
            }
            if received < count {
                return Err(format!("received {received}/{count} messages before timeout").into());
            }
        }
        return Ok(());
    }
    if a.get(1).map(String::as_str) != Some("benchmark") {
        return Err(
            "usage: rosplus-runtime benchmark|dds-publish|dds-subscribe|plugin-run [options]"
                .into(),
        );
    }
    let count: usize = val("--messages", "10000").parse()?;
    let size: usize = val("--size", "1024").parse()?;
    let hz: u64 = val("--frequency", "1000").parse()?;
    if count == 0 || count > 10_000_000 || size == 0 || size > 16 * 1024 * 1024 || hz > 1_000_000 {
        return Err("invalid benchmark limits".into());
    }
    let p = Pool::new(4, size)?;
    let mut samples = Vec::with_capacity(count);
    let schedule = if a.iter().any(|s| s == "--fifo") {
        Some(scheduler::configure(20, None, false))
    } else {
        None
    };
    let socket_path = val("--safety-socket", "");
    let socket = if !socket_path.is_empty() {
        let s = UnixDatagram::unbound()?;
        s.connect(socket_path)?;
        Some(s)
    } else {
        None
    };
    let period = if hz == 0 {
        Duration::ZERO
    } else {
        Duration::from_secs_f64(1. / hz as f64)
    };
    let start = Instant::now();
    let mut next = start;
    let mut missed = 0;
    for i in 0..count {
        let mut lease = p.acquire(size, false)?;
        lease.bytes_mut()[0] = (i % 256) as u8;
        let sent = Instant::now();
        let message = Arc::new(lease);
        let received = message.clone();
        std::hint::black_box(received.bytes());
        samples.push(sent.elapsed().as_secs_f64() * 1e6);
        drop(received);
        drop(message);
        if let Some(s) = &socket {
            let mut packet = [0u8; 16];
            packet[..8].copy_from_slice(
                &(std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)?
                    .as_nanos() as u64)
                    .to_le_bytes(),
            );
            packet[8..12].copy_from_slice(&2u32.to_le_bytes());
            packet[12..].copy_from_slice(&3u32.to_le_bytes());
            s.send(&packet)?;
        }
        if !period.is_zero() {
            next += period;
            let now = Instant::now();
            if now < next {
                std::thread::sleep(next - now);
            } else {
                missed += 1;
            }
        }
    }
    let seconds = start.elapsed().as_secs_f64();
    samples.sort_by(f64::total_cmp);
    let percentile = |q: f64| samples[((count - 1) as f64 * q).ceil() as usize];
    println!(
        "{}",
        serde_json::json!({"benchmark":"in_process_arc_handoff","transport":"none","scope":"ownership handoff only; excludes DDS, serialization and executor scheduling","messages":count,"message_size":size,"frequency_hz":hz,"duration_seconds":seconds,"messages_per_second":count as f64/seconds,"p50_latency_us":percentile(0.50),"p95_latency_us":percentile(0.95),"p99_latency_us":percentile(0.99),"pacing_deadlines_missed":missed,"scheduler":schedule,"spill_events":p.stats().2})
    );
    Ok(())
}

fn run_plugin(arguments: &[String]) -> Result<(), Box<dyn std::error::Error>> {
    let mut plugin = None;
    let mut adapter = "build/librosplus_rcl.so".to_owned();
    let mut messages = 0usize;
    let mut timeout = 0u64;
    let mut fifo = false;
    let mut plugin_arguments = &[][..];
    let mut seen = std::collections::HashSet::new();
    let mut index = 0usize;
    while index < arguments.len() {
        let option = arguments[index].as_str();
        if option == "--" {
            plugin_arguments = &arguments[index + 1..];
            break;
        }
        if !seen.insert(option) {
            return Err(format!("duplicate option {option}").into());
        }
        if option == "--fifo" {
            fifo = true;
            index += 1;
            continue;
        }
        if !matches!(
            option,
            "--plugin" | "--adapter" | "--messages" | "--timeout-seconds"
        ) {
            return Err(format!("unknown option {option} for plugin-run").into());
        }
        let value = arguments
            .get(index + 1)
            .filter(|value| !value.starts_with("--"))
            .ok_or_else(|| format!("missing value for {option}"))?;
        match option {
            "--plugin" => plugin = Some(value.clone()),
            "--adapter" => adapter = value.clone(),
            "--messages" => messages = value.parse()?,
            "--timeout-seconds" => timeout = value.parse()?,
            _ => unreachable!(),
        }
        index += 2;
    }
    let plugin = plugin.ok_or("--plugin is required")?;
    let mut heartbeat = rosplus_core::heartbeat::Heartbeat::from_env()?;
    rosplus_core::plugin::run(rosplus_core::plugin::Options {
        plugin: &plugin,
        adapter: &adapter,
        messages,
        timeout: Duration::from_secs(timeout),
        fifo,
        arguments: plugin_arguments,
        heartbeat: &mut heartbeat,
    })
}

fn monotonic_ns() -> std::io::Result<u64> {
    let mut time: libc::timespec = unsafe { std::mem::zeroed() };
    if unsafe { libc::clock_gettime(libc::CLOCK_MONOTONIC, &mut time) } != 0 {
        return Err(std::io::Error::last_os_error());
    }
    Ok(time.tv_sec as u64 * 1_000_000_000 + time.tv_nsec as u64)
}
