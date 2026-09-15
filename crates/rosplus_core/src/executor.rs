use crate::pool::Pool;
use serde::Serialize;
use std::sync::Arc;
use std::time::{Duration, Instant};
pub struct NodeContext {
    pub pool: Arc<Pool>,
}
pub trait RosPlusNode: Send {
    fn name(&self) -> &str;
    fn init(&mut self, _: &NodeContext) -> Result<(), String> {
        Ok(())
    }
    fn tick(&mut self, context: &NodeContext) -> Result<(), String>;
    fn shutdown(&mut self) {}
}
#[derive(Clone, Serialize)]
pub struct Stats {
    pub name: String,
    pub ticks: u64,
    pub missed_deadlines: u64,
    pub wcet_us: f64,
    pub active: bool,
    pub error: Option<String>,
}
struct Entry {
    node: Box<dyn RosPlusNode>,
    priority: u8,
    budget: Duration,
    consecutive: u8,
    stats: Stats,
}
pub struct Runtime {
    ctx: NodeContext,
    nodes: Vec<Entry>,
}
impl Runtime {
    pub fn new(pool: Arc<Pool>) -> Self {
        Self {
            ctx: NodeContext { pool },
            nodes: vec![],
        }
    }
    pub fn add(
        &mut self,
        mut node: Box<dyn RosPlusNode>,
        priority: u8,
        budget: Duration,
    ) -> Result<(), String> {
        if self.nodes.iter().any(|n| n.stats.name == node.name()) {
            return Err("duplicate node name".into());
        }
        node.init(&self.ctx)?;
        let stats = Stats {
            name: node.name().into(),
            ticks: 0,
            missed_deadlines: 0,
            wcet_us: 0.,
            active: true,
            error: None,
        };
        self.nodes.push(Entry {
            node,
            priority,
            budget,
            consecutive: 0,
            stats,
        });
        self.nodes.sort_by_key(|n| std::cmp::Reverse(n.priority));
        Ok(())
    }
    pub fn tick(&mut self) {
        for n in &mut self.nodes {
            if !n.stats.active {
                continue;
            }
            let start = Instant::now();
            let result = n.node.tick(&self.ctx);
            let elapsed = start.elapsed();
            n.stats.ticks += 1;
            n.stats.wcet_us = n.stats.wcet_us.max(elapsed.as_secs_f64() * 1e6);
            if elapsed > n.budget {
                n.stats.missed_deadlines += 1;
            }
            if elapsed > n.budget.mul_f64(1.1) {
                n.consecutive += 1;
            } else {
                n.consecutive = 0;
            }
            if let Err(e) = result {
                n.stats.error = Some(e);
                n.stats.active = false;
            }
            if n.consecutive >= 3 {
                n.stats.error = Some("three consecutive budget overruns".into());
                n.stats.active = false;
            }
            if !n.stats.active {
                n.node.shutdown();
            }
        }
    }
    pub fn stats(&self) -> Vec<Stats> {
        self.nodes.iter().map(|n| n.stats.clone()).collect()
    }
}
impl Drop for Runtime {
    fn drop(&mut self) {
        for n in &mut self.nodes {
            if n.stats.active {
                n.node.shutdown();
            }
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    struct Slow;
    impl RosPlusNode for Slow {
        fn name(&self) -> &str {
            "slow"
        }
        fn tick(&mut self, _: &NodeContext) -> Result<(), String> {
            std::thread::sleep(Duration::from_millis(2));
            Ok(())
        }
    }
    #[test]
    fn budgets_disable_after_three() {
        let mut r = Runtime::new(Pool::new(1, 8).unwrap());
        r.add(Box::new(Slow), 1, Duration::from_micros(1)).unwrap();
        for _ in 0..4 {
            r.tick();
        }
        let s = &r.stats()[0];
        assert_eq!(s.ticks, 3);
        assert!(!s.active);
        assert_eq!(s.missed_deadlines, 3);
    }
}
