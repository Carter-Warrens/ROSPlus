package server

import (
	"bufio"
	"context"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

type Node struct {
	stopped                    time.Time
	Name, Target, Mode, Status string
	PID, Restarts              int
	started                    time.Time
	cmd                        *exec.Cmd
	done                       chan struct{}
	stopping                   bool
	request                    RunRequest
	output                     *boundedLog
	lastProgress               time.Time
	progressCounter            uint64
}
type boundedLog struct{ lines int }

func (n *Node) public() Object {
	elapsed := time.Since(n.started).Seconds()
	if !n.stopped.IsZero() {
		elapsed = n.stopped.Sub(n.started).Seconds()
	}
	var cpu, mem any
	if n.Status == "running" {
		cpu, mem = processUsage(n.PID, elapsed)
	}
	return Object{"name": n.Name, "target": n.Target, "mode": n.Mode, "status": n.Status, "pid": n.PID, "uptime_seconds": elapsed, "cpu_percent": cpu, "memory_mb": mem, "restart_count": n.Restarts}
}

type RunRequest struct {
	Target      string   `json:"target"`
	Mode        string   `json:"mode"`
	Args        []string `json:"args"`
	Background  bool     `json:"background"`
	Priority    string   `json:"priority"`
	Restart     string   `json:"restart"`
	MaxRestarts int      `json:"max_restarts"`
}
type BuildRequest struct {
	Packages []string `json:"packages"`
	Release  bool     `json:"release"`
}

func childEnv() []string {
	out := []string{}
	for _, v := range os.Environ() {
		k := strings.SplitN(v, "=", 2)[0]
		if k == "PATH" || k == "HOME" || k == "LANG" || k == "PYTHONPATH" || k == "LD_LIBRARY_PATH" || k == "CMAKE_PREFIX_PATH" || k == "AMENT_PREFIX_PATH" || k == "COLCON_PREFIX_PATH" || k == "RMW_IMPLEMENTATION" || strings.HasPrefix(k, "ROS_") || strings.HasPrefix(k, "CYCLONEDDS") || strings.HasPrefix(k, "FASTRTPS") || k == "CARGO_HOME" || k == "RUSTUP_HOME" {
			out = append(out, v)
		}
	}
	return out
}
func (s *Server) run(w *Workspace, b RunRequest) (Object, error) {
	if b.Mode == "" || b.Mode == "auto" {
		b.Mode = "legacy"
		if strings.HasPrefix(b.Target, "native:") {
			b.Mode = "native"
		}
	}
	if b.Mode != "legacy" && b.Mode != "native" {
		return nil, errors.New("mode must be auto, native, or legacy")
	}
	if b.Mode == "native" && !strings.HasPrefix(b.Target, "native:") {
		return nil, errors.New("native targets use native:talker, native:listener, or native:plugin:PATH")
	}
	if b.Mode == "legacy" && strings.HasPrefix(b.Target, "native:") {
		return nil, errors.New("native target cannot run in legacy mode")
	}
	if b.Priority == "" {
		b.Priority = "normal"
	}
	if b.Priority != "critical" && b.Priority != "high" && b.Priority != "normal" && b.Priority != "low" && b.Priority != "background" {
		return nil, errors.New("invalid priority")
	}
	if b.Mode != "native" && b.Priority != "normal" {
		return nil, errors.New("priority applies to native nodes only")
	}
	if b.Restart == "" {
		b.Restart = "never"
	}
	if b.Restart != "never" && b.Restart != "on-failure" && b.Restart != "always" {
		return nil, errors.New("invalid restart policy")
	}
	if b.MaxRestarts < 0 || b.MaxRestarts > 100 {
		return nil, errors.New("max_restarts must be 0..100")
	}
	if b.Target == "" {
		return nil, errors.New("target required")
	}
	w.BuildMu.Lock()
	defer w.BuildMu.Unlock()
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.safetyStatus()["estop_triggered"] == true {
		return nil, errors.New("E-Stop latched; restart the service after investigating")
	}
	if s.closing || s.items[w.ID] != w {
		return nil, errors.New("workspace unavailable")
	}
	name := strings.TrimSuffix(filepath.Base(b.Target), filepath.Ext(b.Target))
	if plugin, ok := strings.CutPrefix(b.Target, "native:plugin:"); ok {
		name = strings.TrimSuffix(filepath.Base(plugin), filepath.Ext(plugin))
		if !namePattern.MatchString(name) {
			return nil, errors.New("native plugin filename must form a valid node name")
		}
	} else if strings.HasPrefix(b.Target, "native:") {
		name = strings.ReplaceAll(b.Target, ":", "_")
	}
	if strings.HasPrefix(b.Target, "ros2:") {
		pieces := strings.Split(b.Target, ":")
		if len(pieces) != 3 || !namePattern.MatchString(pieces[1]) || !namePattern.MatchString(pieces[2]) {
			return nil, errors.New("ROS target format: ros2:package:executable")
		}
		name = pieces[2]
	}
	if old := w.Nodes[name]; old != nil && (old.Status == "running" || old.Status == "starting") {
		return nil, errors.New("node already running")
	}
	n := &Node{Name: name, Target: b.Target, Mode: b.Mode, Status: "starting", request: b, done: make(chan struct{})}
	if e := s.start(w, n); e != nil {
		return nil, e
	}
	w.Nodes[name] = n
	return Object{"success": true, "node_name": name, "pid": n.PID, "mode": n.Mode, "log_url": "/api/v1/workspace/" + w.ID + "/logs"}, nil
}

// Caller holds s.mu. Each generation has exactly one waiter.
func (s *Server) start(w *Workspace, n *Node) error {
	var argv []string
	if strings.HasPrefix(n.Target, "native:") {
		role := "dds-publish"
		if n.Target == "native:listener" {
			role = "dds-subscribe"
		}
		binary := os.Getenv("ROSPLUS_RUNTIME_BINARY")
		if binary == "" {
			binary = "crates/target/release/rosplus-runtime"
		}
		binary, e := filepath.Abs(binary)
		if e != nil {
			return e
		}
		adapter := os.Getenv("ROSPLUS_RCL_ADAPTER")
		if adapter == "" {
			adapter = "build/librosplus_rcl.so"
		}
		adapter, e = filepath.Abs(adapter)
		if e != nil {
			return e
		}
		if _, e = os.Stat(adapter); e != nil {
			return errors.New("build the ROS 2 rcl adapter before starting native endpoints")
		}
		if plugin, ok := strings.CutPrefix(n.Target, "native:plugin:"); ok {
			pluginPath, pathErr := safe(w, plugin)
			if pathErr != nil {
				return pathErr
			}
			info, statErr := os.Stat(pluginPath)
			if statErr != nil || !info.Mode().IsRegular() || filepath.Ext(pluginPath) != ".so" {
				return errors.New("native plugin must be an existing .so file inside the workspace")
			}
			argv = []string{binary, "plugin-run", "--plugin", pluginPath, "--adapter", adapter}
			if n.request.Priority == "critical" || n.request.Priority == "high" {
				argv = append(argv, "--fifo")
			}
			if len(n.request.Args) > 0 {
				argv = append(argv, "--")
			}
		} else if n.Target == "native:talker" || n.Target == "native:listener" {
			argv = []string{binary, role, "--adapter", adapter}
		} else {
			return errors.New("unknown native target; use native:plugin:PATH for a shared library")
		}
	} else if strings.HasPrefix(n.Target, "ros2:") {
		p := strings.Split(n.Target, ":")
		argv = []string{"ros2", "run", p[1], p[2]}
	} else {
		p, e := safe(w, n.Target)
		if e != nil {
			return e
		}
		info, e := os.Stat(p)
		if e != nil || !info.Mode().IsRegular() {
			return errors.New("target not found")
		}
		if filepath.Ext(p) == ".py" {
			argv = []string{"python3", "-u", p}
		} else if info.Mode()&0111 != 0 {
			argv = []string{p}
		} else {
			return errors.New("target must be Python, an executable, or ros2:package:executable")
		}
	}
	remap, e := graphArgs(w, n)
	if e != nil {
		return e
	}
	if !strings.HasPrefix(n.Target, "native:plugin:") {
		argv = append(argv, remap...)
	}
	argv = append(argv, n.request.Args...)
	cmd := exec.Command(argv[0], argv[1:]...)
	cmd.Dir = w.Path
	cmd.Env = childEnv()
	var progressReader, progressWriter *os.File
	if n.Mode == "native" && s.safety != nil {
		progressReader, progressWriter, e = os.Pipe()
		if e != nil {
			return e
		}
		cmd.ExtraFiles = []*os.File{progressWriter}
		cmd.Env = append(cmd.Env, "ROSPLUS_EXECUTOR_HEARTBEAT_FD=3")
		n.lastProgress = time.Now()
		n.progressCounter = 0
	}
	configureProcess(cmd)
	reader, writer, e := os.Pipe()
	if e != nil {
		if progressReader != nil {
			progressReader.Close()
			progressWriter.Close()
		}
		return e
	}
	cmd.Stdout = writer
	cmd.Stderr = writer
	if e = cmd.Start(); e != nil {
		if progressReader != nil {
			progressReader.Close()
			progressWriter.Close()
		}
		reader.Close()
		writer.Close()
		return e
	}
	if progressWriter != nil {
		progressWriter.Close()
		go s.captureProgress(n, cmd, progressReader)
	}
	writer.Close()
	n.cmd = cmd
	n.PID = cmd.Process.Pid
	n.started = time.Now()
	n.stopped = time.Time{}
	n.Status = "running"
	w.Status = "running"
	s.log(w, "info", n.Name, fmt.Sprintf("started pid=%d", n.PID))
	go s.capture(w, n, cmd, reader)
	return nil
}

func (s *Server) captureProgress(n *Node, cmd *exec.Cmd, reader *os.File) {
	defer reader.Close()
	packet := make([]byte, 8)
	for {
		if _, e := io.ReadFull(reader, packet); e != nil {
			return
		}
		counter := binary.LittleEndian.Uint64(packet)
		s.mu.Lock()
		if n.cmd == cmd && n.Status == "running" && counter > n.progressCounter {
			n.progressCounter = counter
			n.lastProgress = time.Now()
		}
		s.mu.Unlock()
	}
}

func (s *Server) capture(w *Workspace, n *Node, cmd *exec.Cmd, reader *os.File) {
	scanner := bufio.NewScanner(reader)
	scanner.Buffer(make([]byte, 4096), 1<<20)
	for scanner.Scan() {
		s.mu.Lock()
		s.log(w, "info", n.Name, scanner.Text())
		s.mu.Unlock()
	}
	scanErr := scanner.Err()
	reader.Close()
	if scanErr != nil {
		killProcess(cmd, true)
	}
	err := cmd.Wait()
	s.mu.Lock()
	nativeFailure := n.Mode == "native" && err != nil && !n.stopping
	if nativeFailure {
		s.tripSafety()
		s.log(w, "error", "safety", "native executor exited unexpectedly; simulated E-Stop latched")
	}
	if scanErr != nil {
		s.log(w, "error", n.Name, "log stream failed: "+scanErr.Error())
	}
	restart := !nativeFailure && !n.stopping && !s.closing && n.Restarts < n.request.MaxRestarts && (n.request.Restart == "always" || (n.request.Restart == "on-failure" && err != nil))
	if restart {
		n.Restarts++
		n.Status = "starting"
		s.log(w, "warn", n.Name, "restarting after exit")
		s.mu.Unlock()
		time.Sleep(100 * time.Millisecond)
		s.mu.Lock()
		if !n.stopping && !s.closing {
			if e := s.start(w, n); e == nil {
				s.mu.Unlock()
				return
			} else {
				s.log(w, "error", n.Name, e.Error())
			}
		}
	}
	n.Status = "stopped"
	n.stopped = time.Now()
	if err != nil && !n.stopping {
		n.Status = "error"
	}
	s.log(w, "info", n.Name, fmt.Sprintf("process exited: %v", err))
	active := false
	for _, p := range w.Nodes {
		active = active || p.Status == "running" || p.Status == "starting"
	}
	if !active {
		w.Status = "idle"
		if n.Status == "error" {
			w.Status = "error"
		}
	}
	close(n.done)
	s.mu.Unlock()
}
func (s *Server) stop(w *Workspace, name string) []string {
	s.mu.Lock()
	nodes := []*Node{}
	for _, n := range w.Nodes {
		if (name == "" || n.Name == name) && (n.Status == "running" || n.Status == "starting") {
			n.stopping = true
			nodes = append(nodes, n)
			killProcess(n.cmd, false)
		}
	}
	s.mu.Unlock()
	stopped := []string{}
	for _, n := range nodes {
		select {
		case <-n.done:
		case <-time.After(2 * time.Second):
			killProcess(n.cmd, true)
			select {
			case <-n.done:
			case <-time.After(time.Second):
			}
		}
		stopped = append(stopped, n.Name)
	}
	return stopped
}
func (s *Server) build(ctx context.Context, w *Workspace, b BuildRequest) Object {
	w.BuildMu.Lock()
	defer w.BuildMu.Unlock()
	start := time.Now()
	s.mu.Lock()
	if s.items[w.ID] != w || s.closing {
		s.mu.Unlock()
		return Object{"success": false, "errors": []string{"workspace unavailable"}}
	}
	w.Status = "building"
	w.Building = true
	s.log(w, "info", "build", "build started")
	s.mu.Unlock()
	defer func() {
		s.mu.Lock()
		w.Building = false
		w.Status = "idle"
		for _, n := range w.Nodes {
			if n.Status == "running" {
				w.Status = "running"
			}
		}
		s.mu.Unlock()
	}()
	commands := [][]string{}
	rust := false
	rustSource := false
	ros := false
	python := []string{}
	walkErr := filepath.WalkDir(w.Path, func(p string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.IsDir() && (d.Name() == "target" || d.Name() == "node_modules" || d.Name() == "build" || d.Name() == "install" || d.Name() == "log" || d.Name() == ".git") {
			return filepath.SkipDir
		}
		if d.Type()&os.ModeSymlink != 0 {
			return errors.New("build workspace contains symlink")
		}
		if d.IsDir() {
			return nil
		}
		if d.Name() == "package.xml" {
			ros = true
		}
		if filepath.Ext(p) == ".rs" {
			rustSource = true
		}
		if d.Name() == "Cargo.toml" {
			rust = true
		}
		if filepath.Ext(p) == ".py" {
			python = append(python, p)
		}
		return nil
	})
	if rustSource && !rust && !ros {
		walkErr = errors.New("Rust sources require a Cargo.toml manifest")
	}
	if ros {
		c := []string{"colcon", "build"}
		if len(b.Packages) > 0 {
			c = append(c, "--packages-select")
			c = append(c, b.Packages...)
		}
		commands = append(commands, c)
	} else if rust {
		c := []string{"cargo", "build"}
		if b.Release {
			c = append(c, "--release")
		}
		for _, p := range b.Packages {
			c = append(c, "-p", p)
		}
		commands = append(commands, c)
	} else if len(b.Packages) > 0 {
		walkErr = errors.New("package selection requires Cargo or colcon workspace")
	}
	if len(python) > 0 {
		commands = append(commands, append([]string{"python3", "-m", "py_compile"}, python...))
	}
	errs := []string{}
	logs := []string{}
	if walkErr != nil {
		errs = append(errs, walkErr.Error())
	} else {
		for _, argv := range commands {
			cctx, cancel := context.WithTimeout(ctx, 10*time.Minute)
			cmd := exec.CommandContext(cctx, argv[0], argv[1:]...)
			cmd.Dir = w.Path
			cmd.Env = childEnv()
			configureProcess(cmd)
			cmd.Cancel = func() error { killProcess(cmd, true); return nil }
			cmd.WaitDelay = time.Second
			out := &buildOutput{s: s, w: w}
			cmd.Stdout = out
			cmd.Stderr = out
			e := cmd.Run()
			cancel()
			text := string(out.data)
			if len(text) > 1<<20 {
				text = text[len(text)-(1<<20):]
			}
			logs = append(logs, text)
			s.mu.Lock()
			s.log(w, "info", "build", text)
			s.mu.Unlock()
			if e != nil {
				errs = append(errs, e.Error())
				break
			}
		}
	}
	return Object{"success": len(errs) == 0, "log": strings.Join(logs, "\n"), "errors": errs, "warnings": []string{}, "duration_seconds": time.Since(start).Seconds(), "packages_built": len(commands)}
}

// Retain at most 1 MiB while streaming each build chunk to subscribers.
type buildOutput struct {
	s    *Server
	w    *Workspace
	data []byte
}

func (b *buildOutput) Write(p []byte) (int, error) {
	n := len(p)
	b.data = append(b.data, p...)
	if len(b.data) > 1<<20 {
		b.data = b.data[len(b.data)-(1<<20):]
	}
	b.s.mu.Lock()
	b.s.log(b.w, "info", "build", string(p))
	b.s.mu.Unlock()
	return n, nil
}
