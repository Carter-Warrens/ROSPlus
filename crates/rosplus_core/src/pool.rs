//! In-process pooled ownership. A lease returns its buffer on final release.
//! This is not an inter-process shared-memory implementation.
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

pub struct Pool {
    free: Mutex<Vec<Vec<u8>>>,
    pub chunk_size: usize,
    pub capacity: usize,
    spills: AtomicU64,
}
pub struct Lease {
    bytes: Vec<u8>,
    pool: Option<Arc<Pool>>,
    len: usize,
}
impl Pool {
    pub fn new(chunks: usize, chunk_size: usize) -> Result<Arc<Self>, &'static str> {
        if chunks == 0
            || chunk_size == 0
            || chunks
                .checked_mul(chunk_size)
                .filter(|n| *n <= 512 * 1024 * 1024)
                .is_none()
        {
            return Err("pool must be nonempty and at most 512 MiB");
        }
        Ok(Arc::new(Self {
            free: Mutex::new((0..chunks).map(|_| vec![0; chunk_size]).collect()),
            chunk_size,
            capacity: chunks,
            spills: AtomicU64::new(0),
        }))
    }
    pub fn acquire(self: &Arc<Self>, len: usize, allow_spill: bool) -> Result<Lease, &'static str> {
        if len <= self.chunk_size {
            if let Some(bytes) = self.free.lock().unwrap().pop() {
                return Ok(Lease {
                    bytes,
                    pool: Some(self.clone()),
                    len,
                });
            }
        }
        if !allow_spill {
            return Err("pool exhausted or message exceeds chunk size");
        }
        self.spills.fetch_add(1, Ordering::Relaxed);
        eprintln!(
            "{{\"level\":\"WARN\",\"component\":\"pool\",\"message\":\"message spilled to heap\"}}"
        );
        Ok(Lease {
            bytes: vec![0; len],
            pool: None,
            len,
        })
    }
    pub fn stats(&self) -> (usize, usize, u64) {
        let free = self.free.lock().unwrap().len();
        (
            self.capacity - free,
            free,
            self.spills.load(Ordering::Relaxed),
        )
    }
}
impl Lease {
    pub fn bytes(&self) -> &[u8] {
        &self.bytes[..self.len]
    }
    pub fn bytes_mut(&mut self) -> &mut [u8] {
        &mut self.bytes[..self.len]
    }
}
impl Drop for Lease {
    fn drop(&mut self) {
        if let Some(pool) = &self.pool {
            pool.free
                .lock()
                .unwrap()
                .push(std::mem::take(&mut self.bytes));
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn lease_lifetime_and_exhaustion() {
        let p = Pool::new(1, 1024).unwrap();
        let mut a = p.acquire(8, false).unwrap();
        a.bytes_mut()[0] = 42;
        let a = Arc::new(a);
        let b = a.clone();
        drop(a);
        assert_eq!(b.bytes()[0], 42);
        assert!(p.acquire(8, false).is_err());
        drop(b);
        assert_eq!(p.stats(), (0, 1, 0));
        assert!(p.acquire(2048, false).is_err());
        drop(p.acquire(2048, true).unwrap());
        assert_eq!(p.stats(), (0, 1, 1));
    }
}
