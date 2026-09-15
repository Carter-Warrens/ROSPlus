package server

import (
	"encoding/binary"
	"errors"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"
)

type Safety struct {
	mu               sync.Mutex
	connected, estop bool
	latency          float64
	executorHealthy  bool
	executorCount    int
	executorAgeMS    float64
	stop             chan struct{}
	done             chan struct{}
	once             sync.Once
	cmd              *exec.Cmd
	dir              string
}

func (s *Server) StartSafety(binaryPath string) error {
	binaryPath, e := filepath.Abs(binaryPath)
	if e != nil {
		return e
	}
	dir, e := os.MkdirTemp("", "rosplus-safety-")
	if e != nil {
		return e
	}
	socket := filepath.Join(dir, "monitor.sock")
	client := filepath.Join(dir, "client.sock")
	cmd := exec.Command(binaryPath, "--simulate", "--socket", socket, "--log", filepath.Join(s.Root, "safety-gpio.jsonl"), "--timeout-ms", "50")
	cmd.Stderr = os.Stderr
	if e = cmd.Start(); e != nil {
		os.RemoveAll(dir)
		return e
	}
	failed := true
	defer func() {
		if failed {
			cmd.Process.Kill()
			cmd.Wait()
			os.RemoveAll(dir)
		}
	}()
	deadline := time.Now().Add(2 * time.Second)
	for {
		if _, e = os.Stat(socket); e == nil {
			break
		}
		if time.Now().After(deadline) {
			return errors.New("safety socket did not become ready")
		}
		time.Sleep(5 * time.Millisecond)
	}
	conn, e := net.DialUnix("unixgram", &net.UnixAddr{Name: client, Net: "unixgram"}, &net.UnixAddr{Name: socket, Net: "unixgram"})
	if e != nil {
		return e
	}
	s.safety = &Safety{stop: make(chan struct{}), done: make(chan struct{}), cmd: cmd, dir: dir}
	failed = false
	go s.safetyLoop(conn)
	return nil
}
func (s *Server) safetyLoop(conn *net.UnixConn) {
	m := s.safety
	defer close(m.done)
	defer conn.Close()
	defer os.RemoveAll(m.dir)
	defer m.cmd.Wait()
	tick := time.NewTicker(10 * time.Millisecond)
	defer tick.Stop()
	count := 0
	nativeCount := 0
	oldestProgress := time.Time{}
	for {
		select {
		case <-m.stop:
			m.cmd.Process.Kill()
			return
		case <-tick.C:
			packet := make([]byte, 16)
			binary.LittleEndian.PutUint64(packet, uint64(time.Now().UnixNano()))
			// Never delay the independent watchdog while another API operation holds
			// the workspace lock. Reuse the last snapshot and keep aging it.
			if s.mu.TryLock() {
				count = 0
				nativeCount = 0
				oldestProgress = time.Time{}
				for _, w := range s.items {
					for _, n := range w.Nodes {
						if n.Status == "running" {
							count++
							if n.Mode == "native" && !n.stopping {
								nativeCount++
								if oldestProgress.IsZero() || n.lastProgress.Before(oldestProgress) {
									oldestProgress = n.lastProgress
								}
							}
						}
					}
				}
				s.mu.Unlock()
			}
			maxExecutorAge := time.Duration(0)
			executorHealthy := true
			if nativeCount > 0 {
				maxExecutorAge = time.Since(oldestProgress)
				executorHealthy = !oldestProgress.IsZero() && maxExecutorAge < 40*time.Millisecond
			}
			binary.LittleEndian.PutUint32(packet[8:], uint32(count))
			flags := uint32(1)
			if nativeCount == 0 || executorHealthy {
				flags |= 2
			}
			binary.LittleEndian.PutUint32(packet[12:], flags)
			start := time.Now()
			conn.SetDeadline(start.Add(20 * time.Millisecond))
			_, e := conn.Write(packet)
			b := make([]byte, 1)
			if e == nil {
				_, e = conn.Read(b)
			}
			m.mu.Lock()
			m.connected = e == nil
			m.latency = float64(time.Since(start).Microseconds())
			m.executorHealthy = nativeCount > 0 && executorHealthy
			m.executorCount = nativeCount
			m.executorAgeMS = float64(maxExecutorAge.Microseconds()) / 1000
			if e != nil || b[0] != 0 {
				m.estop = true
			}
			trip := m.estop
			m.mu.Unlock()
			if trip {
				s.mu.Lock()
				items := []*Workspace{}
				for _, w := range s.items {
					s.log(w, "error", "safety", "simulated E-Stop: stopping supervised nodes")
					items = append(items, w)
				}
				s.mu.Unlock()
				for _, w := range items {
					s.stop(w, "")
				}
				m.cmd.Process.Kill()
				return
			}
		}
	}
}
func (s *Server) tripSafety() {
	if s.safety != nil {
		s.safety.mu.Lock()
		s.safety.estop = true
		s.safety.mu.Unlock()
	}
}
func (s *Server) safetyStatus() Object {
	if s.safety == nil {
		return Object{"connected": false, "estop_triggered": nil, "heartbeat_latency_us": nil, "simulated": true, "scope": "executor_progress", "executor_connected": false, "native_executor_count": 0, "executor_heartbeat_age_ms": nil}
	}
	m := s.safety
	m.mu.Lock()
	defer m.mu.Unlock()
	age := any(nil)
	if m.executorCount > 0 {
		age = m.executorAgeMS
	}
	return Object{"connected": m.connected, "estop_triggered": m.estop, "heartbeat_latency_us": m.latency, "simulated": true, "scope": "executor_progress", "executor_connected": m.executorHealthy, "native_executor_count": m.executorCount, "executor_heartbeat_age_ms": age}
}
func (s *Server) closeSafety() {
	if s.safety != nil {
		s.safety.once.Do(func() { close(s.safety.stop) })
		<-s.safety.done
	}
}
