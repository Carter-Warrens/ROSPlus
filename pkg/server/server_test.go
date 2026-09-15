package server

import (
	"bytes"
	"encoding/json"
	"github.com/gorilla/websocket"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const testToken = "test-token-123456789"

func setup(t *testing.T) (*Server, *httptest.Server) {
	t.Helper()
	s, e := New(t.TempDir(), testToken, "")
	if e != nil {
		t.Fatal(e)
	}
	h := httptest.NewServer(s)
	t.Cleanup(func() { s.Close(); h.Close() })
	return s, h
}
func call(t *testing.T, h *httptest.Server, method, path, body string, code int) Object {
	t.Helper()
	r, _ := http.NewRequest(method, h.URL+path, strings.NewReader(body))
	r.Header.Set("Authorization", "Bearer "+testToken)
	resp, e := http.DefaultClient.Do(r)
	if e != nil {
		t.Fatal(e)
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != code {
		t.Fatalf("%s %s: %d %s", method, path, resp.StatusCode, b)
	}
	v := Object{}
	json.Unmarshal(b, &v)
	return v
}
func createTest(t *testing.T, s *Server) *Workspace {
	t.Helper()
	v, e := s.create("robot", "empty")
	if e != nil {
		t.Fatal(e)
	}
	return s.items[v["id"].(string)]
}
func TestAPIWorkspacePersistenceAndFiles(t *testing.T) {
	s, h := setup(t)
	v := call(t, h, "POST", "/api/v1/workspace/create", `{"name":"robot"}`, 201)
	id := v["id"].(string)
	p := "/api/v1/workspace/" + id
	call(t, h, "PUT", p+"/file/src/test.py", `{"content":"print('ok')"}`, 200)
	f := call(t, h, "GET", p+"/file/src/test.py", "", 200)
	if f["content"] != "print('ok')" {
		t.Fatal(f)
	}
	call(t, h, "PUT", p+"/file/../../outside", `{"content":"x"}`, 400)
	call(t, h, "POST", p+"/status", "{}", 405)
	call(t, h, "POST", p+"/run", `{"target":9}`, 400)
	call(t, h, "POST", p+"/build", "{}", 200)
	s2, e := New(s.Root, testToken, "")
	if e != nil || len(s2.items) != 1 {
		t.Fatalf("persistence: %v", e)
	}
	call(t, h, "DELETE", p, "", 200)
	call(t, h, "GET", p, "", 404)
}
func TestAuthenticationAndInput(t *testing.T) {
	_, h := setup(t)
	r, e := http.Get(h.URL + "/api/v1/workspace")
	if e != nil {
		t.Fatal(e)
	}
	r.Body.Close()
	if r.StatusCode != 401 {
		t.Fatal(r.StatusCode)
	}
	call(t, h, "POST", "/api/v1/workspace/create", `{"name":"bad/path"}`, 400)
	call(t, h, "POST", "/api/v1/workspace/create", `{"name":"ok","unknown":1}`, 400)
	call(t, h, "POST", "/api/v1/workspace/create", `{"name":"ok"} {}`, 400)
	call(t, h, "POST", "/api/v1/workspace/create", `[]`, 400)
}
func TestSymlinkBoundary(t *testing.T) {
	s, _ := setup(t)
	w := createTest(t, s)
	outside := t.TempDir()
	os.WriteFile(filepath.Join(outside, "secret"), []byte("secret"), 0600)
	os.Symlink(outside, filepath.Join(w.Path, "escape"))
	if _, e := safe(w, "escape/secret"); e == nil {
		t.Fatal("symlink accepted")
	}
}

func TestNativePluginTargetValidation(t *testing.T) {
	s, _ := setup(t)
	w := createTest(t, s)
	adapter := filepath.Join(t.TempDir(), "adapter.so")
	if e := os.WriteFile(adapter, []byte("test"), 0600); e != nil {
		t.Fatal(e)
	}
	t.Setenv("ROSPLUS_RCL_ADAPTER", adapter)
	if _, e := s.run(w, RunRequest{Target: "native:plugin:../escape.so"}); e == nil {
		t.Fatal("escaping native plugin path accepted")
	}
	if _, e := s.run(w, RunRequest{Target: "native:unknown"}); e == nil {
		t.Fatal("unknown native target accepted")
	}
}
func waitNode(t *testing.T, s *Server, w *Workspace, name string, condition func(*Node) bool) {
	t.Helper()
	end := time.Now().Add(5 * time.Second)
	for time.Now().Before(end) {
		s.mu.Lock()
		n := w.Nodes[name]
		ok := n != nil && condition(n)
		s.mu.Unlock()
		if ok {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("node condition timed out")
}
func TestRestartAndShutdown(t *testing.T) {
	s, _ := setup(t)
	w := createTest(t, s)
	os.WriteFile(filepath.Join(w.Path, "crash.py"), []byte("raise SystemExit(7)\n"), 0600)
	_, e := s.run(w, RunRequest{Target: "crash.py", Restart: "on-failure", MaxRestarts: 2})
	if e != nil {
		t.Fatal(e)
	}
	waitNode(t, s, w, "crash", func(n *Node) bool { return n.Status == "error" && n.Restarts == 2 })
	os.WriteFile(filepath.Join(w.Path, "wait.py"), []byte("import time\nprint('alive', flush=True)\ntime.sleep(60)\n"), 0600)
	if _, e = s.run(w, RunRequest{Target: "wait.py"}); e != nil {
		t.Fatal(e)
	}
	if _, e = s.run(w, RunRequest{Target: "wait.py"}); e == nil {
		t.Fatal("duplicate accepted")
	}
	stopped := s.stop(w, "")
	if len(stopped) != 1 {
		t.Fatal(stopped)
	}
	waitNode(t, s, w, "wait", func(n *Node) bool { return n.Status == "stopped" })
}
func TestNativeFailsClosed(t *testing.T) {
	s, _ := setup(t)
	w := createTest(t, s)
	if _, e := s.run(w, RunRequest{Target: "node.rs", Mode: "native"}); e == nil {
		t.Fatal("native unexpectedly accepted")
	}
}
func TestBuildFailure(t *testing.T) {
	s, h := setup(t)
	w := createTest(t, s)
	os.WriteFile(filepath.Join(w.Path, "bad.py"), []byte("def broken(\n"), 0600)
	v := call(t, h, "POST", "/api/v1/workspace/"+w.ID+"/build", "{}", 200)
	if v["success"] != false {
		t.Fatal(v)
	}
}
func TestWebSocketAuthAndLogs(t *testing.T) {
	s, h := setup(t)
	w := createTest(t, s)
	u := "ws" + strings.TrimPrefix(h.URL, "http") + "/api/v1/workspace/" + w.ID + "/logs"
	c, _, e := websocket.DefaultDialer.Dial(u, nil)
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close()
	c.WriteJSON(Object{"type": "subscribe", "workspace_id": w.ID, "token": testToken})
	c.SetReadDeadline(time.Now().Add(2 * time.Second))
	var v Object
	if e = c.ReadJSON(&v); e != nil {
		t.Fatal(e)
	}
	if v["type"] != "log" {
		t.Fatal(v)
	}
	bad, _, e := websocket.DefaultDialer.Dial(u, nil)
	if e != nil {
		t.Fatal(e)
	}
	defer bad.Close()
	bad.WriteJSON(Object{"type": "subscribe", "workspace_id": w.ID, "token": "bad"})
	bad.SetReadDeadline(time.Now().Add(time.Second))
	if _, _, e = bad.ReadMessage(); e == nil {
		t.Fatal("bad token accepted")
	}
}
func TestOutputJSON(t *testing.T) {
	s, _ := setup(t)
	w := createTest(t, s)
	s.mu.Lock()
	defer s.mu.Unlock()
	b, e := json.Marshal(s.metrics(w))
	if e != nil || !bytes.Contains(b, []byte(`"avg_latency_us":null`)) {
		t.Fatalf("unavailable metrics must be null: %s %v", b, e)
	}
}
func TestWatchdogCrashStopsNodes(t *testing.T) {
	binary := filepath.Join("..", "..", "crates", "target", "debug", "rosplus-safety")
	if _, e := os.Stat(binary); e != nil {
		t.Skip("build Rust safety first")
	}
	s, _ := setup(t)
	if e := s.StartSafety(binary); e != nil {
		t.Fatal(e)
	}
	w := createTest(t, s)
	os.WriteFile(filepath.Join(w.Path, "wait.py"), []byte("import time\ntime.sleep(60)\n"), 0600)
	if _, e := s.run(w, RunRequest{Target: "wait.py"}); e != nil {
		t.Fatal(e)
	}
	deadline := time.Now().Add(time.Second)
	for s.safetyStatus()["connected"] != true && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}
	s.safety.cmd.Process.Kill()
	waitNode(t, s, w, "wait", func(n *Node) bool { return n.Status == "stopped" })
	if s.safetyStatus()["estop_triggered"] != true {
		t.Fatal("watchdog crash did not latch stop")
	}
	if _, e := s.run(w, RunRequest{Target: "wait.py"}); e == nil {
		t.Fatal("run permitted after E-Stop")
	}
}
func TestGraphRemapsGeneratedEndpoints(t *testing.T) {
	s, _ := setup(t)
	w := createTest(t, s)
	path := filepath.Join(w.Path, "rosplus.graph.json")
	os.WriteFile(path, []byte(`{"nodes":[{"id":"talker","managed_topic":true}],"edges":[{"source":"talker","target":"listener","topic":"/robot/events"}]}`), 0600)
	args, e := graphArgs(w, &Node{Name: "talker", Target: "src/talker.py", Mode: "legacy"})
	if e != nil || !strings.Contains(strings.Join(args, " "), "/chatter:=/robot/events") {
		t.Fatalf("%v %v", args, e)
	}
	os.WriteFile(path, []byte(`{"nodes":[{"id":"talker","managed_topic":true}],"edges":[]}`), 0600)
	args, e = graphArgs(w, &Node{Name: "talker", Target: "src/talker.py", Mode: "legacy"})
	if e != nil || !strings.Contains(strings.Join(args, " "), "/rosplus/unconnected/talker") {
		t.Fatalf("%v %v", args, e)
	}
}
func TestRustSourceWithoutManifestFailsBuild(t *testing.T) {
	s, h := setup(t)
	w := createTest(t, s)
	os.WriteFile(filepath.Join(w.Path, "node.rs"), []byte("fn main() {}"), 0600)
	v := call(t, h, "POST", "/api/v1/workspace/"+w.ID+"/build", "{}", 200)
	if v["success"] != false {
		t.Fatal("Rust-only workspace incorrectly reported a successful no-op build")
	}
}
