package server

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

type Object = map[string]any
type Workspace struct {
	ID           string           `json:"id"`
	Name         string           `json:"name"`
	Path         string           `json:"path"`
	Status       string           `json:"status"`
	Created      string           `json:"created"`
	LastActivity string           `json:"last_activity"`
	Template     string           `json:"template"`
	Nodes        map[string]*Node `json:"-"`
	Logs         []Object         `json:"-"`
	Building     bool             `json:"-"`
	Sequence     uint64           `json:"-"`
	BuildMu      sync.Mutex       `json:"-"`
}
type Server struct {
	Root, Token, Frontend string
	mu                    sync.Mutex
	items                 map[string]*Workspace
	closing               bool
	safety                *Safety
}

func New(root, token, frontend string) (*Server, error) {
	if len(token) < 16 {
		return nil, errors.New("API token must contain at least 16 characters")
	}
	root, err := filepath.Abs(root)
	if err != nil {
		return nil, err
	}
	if err = os.MkdirAll(root, 0700); err != nil {
		return nil, err
	}
	root, err = filepath.EvalSymlinks(root)
	if err != nil {
		return nil, err
	}
	s := &Server{Root: root, Token: token, Frontend: frontend, items: map[string]*Workspace{}}
	entries, err := os.ReadDir(root)
	if err != nil {
		return nil, err
	}
	for _, e := range entries {
		if !e.IsDir() || !uuidPattern.MatchString(e.Name()) {
			continue
		}
		b, err := os.ReadFile(filepath.Join(root, e.Name(), ".rosplus-workspace.json"))
		if err != nil {
			continue
		}
		w := new(Workspace)
		if json.Unmarshal(b, w) != nil || w.ID != e.Name() {
			continue
		}
		w.Path = filepath.Join(root, e.Name())
		w.Status = "idle"
		w.Nodes = map[string]*Node{}
		w.Logs = []Object{}
		s.items[w.ID] = w
	}
	return s, nil
}

var namePattern = regexp.MustCompile(`^[a-zA-Z0-9_-]{1,64}$`)
var uuidPattern = regexp.MustCompile(`^[a-f0-9-]{36}$`)

func now() string { return time.Now().UTC().Format(time.RFC3339Nano) }
func (s *Server) persist(w *Workspace) error {
	b, e := json.MarshalIndent(w, "", "  ")
	if e != nil {
		return e
	}
	p := filepath.Join(w.Path, ".rosplus-workspace.json")
	if e = os.WriteFile(p+".tmp", b, 0600); e != nil {
		return e
	}
	return os.Rename(p+".tmp", p)
}
func (s *Server) log(w *Workspace, level, node, message string) {
	if len(message) > 16384 {
		message = message[:16384] + " [truncated]"
	}
	w.LastActivity = now()
	w.Sequence++
	event := Object{"type": "log", "sequence": w.Sequence, "workspace_id": w.ID, "timestamp": w.LastActivity, "severity": strings.ToLower(level), "level": strings.ToUpper(level), "component": "supervisor", "node": node, "node_name": node, "message": message}
	w.Logs = append(w.Logs, event)
	if len(w.Logs) > 1000 {
		w.Logs = w.Logs[len(w.Logs)-1000:]
	}
}
func public(w *Workspace) Object {
	return Object{"id": w.ID, "name": w.Name, "path": w.Path, "status": w.Status, "created": w.Created, "last_activity": w.LastActivity, "node_count": len(w.Nodes)}
}
func (s *Server) create(name, template string) (Object, error) {
	if !namePattern.MatchString(name) {
		return nil, errors.New("invalid workspace name")
	}
	if template == "" {
		template = "empty"
	}
	if template != "empty" && template != "talker_listener" && template != "camera" {
		return nil, errors.New("unknown template")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closing {
		return nil, errors.New("server shutting down")
	}
	for _, w := range s.items {
		if w.Name == name {
			return nil, errors.New("workspace name already exists")
		}
	}
	b := make([]byte, 16)
	if _, e := rand.Read(b); e != nil {
		return nil, e
	}
	b[6] = (b[6] & 15) | 64
	b[8] = (b[8] & 63) | 128
	id := fmt.Sprintf("%x-%x-%x-%x-%x", b[:4], b[4:6], b[6:8], b[8:10], b[10:])
	w := &Workspace{ID: id, Name: name, Path: filepath.Join(s.Root, id), Status: "idle", Created: now(), LastActivity: now(), Template: template, Nodes: map[string]*Node{}, Logs: []Object{}}
	if e := os.Mkdir(w.Path, 0700); e != nil {
		return nil, e
	}
	ok := false
	defer func() {
		if !ok {
			os.RemoveAll(w.Path)
		}
	}()
	files := map[string]string{"README.md": "# " + name + "\n"}
	if template == "talker_listener" {
		files = rosTemplate(name)
	}
	if template == "camera" {
		files["README.md"] += "\nCamera device configuration is required before running.\n"
	}
	for p, v := range files {
		dst := filepath.Join(w.Path, p)
		if e := os.MkdirAll(filepath.Dir(dst), 0700); e != nil {
			return nil, e
		}
		if e := os.WriteFile(dst, []byte(v), 0600); e != nil {
			return nil, e
		}
	}
	if e := s.persist(w); e != nil {
		return nil, e
	}
	s.items[id] = w
	s.log(w, "info", "control-plane", "workspace created")
	ok = true
	return public(w), nil
}

// Reject symlinks in every existing path component, including the workspace root.
// This local developer service does not claim hostile-code sandboxing.
func safe(w *Workspace, relative string) (string, error) {
	if relative == "" {
		relative = "."
	}
	if filepath.IsAbs(relative) {
		return "", errors.New("absolute paths forbidden")
	}
	clean := filepath.Clean(relative)
	if clean == ".." || strings.HasPrefix(clean, ".."+string(os.PathSeparator)) {
		return "", errors.New("path escapes workspace")
	}
	p := w.Path
	parts := append([]string{"."}, strings.Split(clean, string(os.PathSeparator))...)
	for _, part := range parts {
		p = filepath.Join(p, part)
		info, e := os.Lstat(p)
		if e == nil && info.Mode()&os.ModeSymlink != 0 {
			return "", errors.New("symlinks forbidden")
		}
		if e != nil && !os.IsNotExist(e) {
			return "", e
		}
	}
	return p, nil
}
func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}
func failure(w http.ResponseWriter, status int, e error) {
	writeJSON(w, status, Object{"error": e.Error(), "code": status})
}
func body(w http.ResponseWriter, r *http.Request, v any) error {
	r.Body = http.MaxBytesReader(w, r.Body, 2<<20)
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	if e := d.Decode(v); e != nil && e != io.EOF {
		return e
	}
	var extra any
	if e := d.Decode(&extra); e != io.EOF {
		return errors.New("expected one JSON object")
	}
	return nil
}
func (s *Server) authorized(r *http.Request) bool {
	return subtle.ConstantTimeCompare([]byte(r.Header.Get("Authorization")), []byte("Bearer "+s.Token)) == 1
}
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Cache-Control", "no-store")
	if r.URL.Path == "/health" && r.Method == "GET" {
		safety := s.safetyStatus()
		writeJSON(w, 200, Object{"status": "ok", "timestamp": now(), "version": "0.2.0", "executor_connected": safety["executor_connected"], "safety_monitor_connected": safety["connected"]})
		return
	}
	if !strings.HasPrefix(r.URL.Path, "/api/") && r.URL.Path != "/metrics" {
		if r.Method != "GET" {
			failure(w, 405, errors.New("method not allowed"))
			return
		}
		if s.Frontend != "" {
			http.FileServer(http.Dir(s.Frontend)).ServeHTTP(w, r)
		} else {
			failure(w, 404, errors.New("frontend not built"))
		}
		return
	}
	isWS := websocket.IsWebSocketUpgrade(r) && strings.HasSuffix(r.URL.Path, "/logs")
	if !isWS && !s.authorized(r) {
		failure(w, 401, errors.New("bearer token required"))
		return
	}
	if r.URL.Path == "/metrics" && r.Method == "GET" {
		s.mu.Lock()
		defer s.mu.Unlock()
		count := 0
		for _, ws := range s.items {
			for _, n := range ws.Nodes {
				if n.Status == "running" {
					count++
				}
			}
		}
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		fmt.Fprintf(w, "# TYPE rosplus_workspaces gauge\nrosplus_workspaces %d\n# TYPE rosplus_nodes_running gauge\nrosplus_nodes_running %d\n", len(s.items), count)
		return
	}
	if r.URL.Path == "/api/v1/workspace" && r.Method == "GET" {
		s.mu.Lock()
		list := []Object{}
		for _, v := range s.items {
			list = append(list, public(v))
		}
		s.mu.Unlock()
		sort.Slice(list, func(i, j int) bool { return list[i]["name"].(string) < list[j]["name"].(string) })
		writeJSON(w, 200, Object{"workspaces": list})
		return
	}
	if r.URL.Path == "/api/v1/workspace/create" && r.Method == "POST" {
		var b struct {
			Name     string `json:"name"`
			Template string `json:"template"`
		}
		if e := body(w, r, &b); e != nil {
			failure(w, 400, e)
			return
		}
		v, e := s.create(b.Name, b.Template)
		if e != nil {
			failure(w, 400, e)
		} else {
			writeJSON(w, 201, v)
		}
		return
	}
	parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	if len(parts) < 4 || strings.Join(parts[:3], "/") != "api/v1/workspace" {
		failure(w, 404, errors.New("endpoint not found"))
		return
	}
	s.mu.Lock()
	ws := s.items[parts[3]]
	s.mu.Unlock()
	if ws == nil {
		failure(w, 404, errors.New("workspace not found"))
		return
	}
	tail := strings.Join(parts[4:], "/")
	if isWS {
		s.stream(w, r, ws)
		return
	}
	switch {
	case tail == "" && r.Method == "GET":
		s.mu.Lock()
		defer s.mu.Unlock()
		writeJSON(w, 200, public(ws))
	case tail == "" && r.Method == "DELETE":
		ws.BuildMu.Lock()
		defer ws.BuildMu.Unlock()
		s.stop(ws, "")
		s.mu.Lock()
		defer s.mu.Unlock()
		if e := os.RemoveAll(ws.Path); e != nil {
			failure(w, 500, e)
			return
		}
		delete(s.items, ws.ID)
		writeJSON(w, 200, Object{"id": ws.ID, "message": "Workspace deleted"})
	case tail == "status" && r.Method == "GET":
		s.mu.Lock()
		defer s.mu.Unlock()
		writeJSON(w, 200, s.status(ws))
	case tail == "files" && r.Method == "GET":
		p, e := safe(ws, r.URL.Query().Get("path"))
		if e != nil {
			failure(w, 400, e)
			return
		}
		entries, e := os.ReadDir(p)
		if e != nil {
			failure(w, 404, e)
			return
		}
		list := []Object{}
		for _, entry := range entries {
			if strings.HasPrefix(entry.Name(), ".rosplus-") || entry.Name() == "__pycache__" || entry.Type()&os.ModeSymlink != 0 {
				continue
			}
			info, e := entry.Info()
			if e != nil {
				continue
			}
			rel, _ := filepath.Rel(ws.Path, filepath.Join(p, entry.Name()))
			list = append(list, Object{"name": entry.Name(), "path": rel, "is_directory": entry.IsDir(), "size_bytes": info.Size(), "last_modified": info.ModTime().UTC().Format(time.RFC3339Nano)})
		}
		writeJSON(w, 200, Object{"files": list})
	case strings.HasPrefix(tail, "file/") && (r.Method == "GET" || r.Method == "PUT"):
		relative := strings.TrimPrefix(tail, "file/")
		p, e := safe(ws, relative)
		if e != nil || strings.HasPrefix(filepath.Base(p), ".rosplus-") {
			failure(w, 400, errors.New("invalid file path"))
			return
		}
		if r.Method == "PUT" {
			var b struct {
				Content *string `json:"content"`
			}
			if e = body(w, r, &b); e != nil || b.Content == nil {
				failure(w, 400, errors.New("string content required"))
				return
			}
			if e = os.MkdirAll(filepath.Dir(p), 0700); e == nil {
				e = os.WriteFile(p, []byte(*b.Content), 0600)
			}
			if e != nil {
				failure(w, 400, e)
				return
			}
		}
		info, e := os.Stat(p)
		if e != nil || !info.Mode().IsRegular() {
			failure(w, 404, errors.New("file not found"))
			return
		}
		if info.Size() > 2<<20 {
			failure(w, 413, errors.New("file exceeds editor limit"))
			return
		}
		out := Object{"path": relative, "size_bytes": info.Size(), "last_modified": info.ModTime().UTC().Format(time.RFC3339Nano)}
		if r.Method == "GET" {
			b, e := os.ReadFile(p)
			if e != nil {
				failure(w, 500, e)
				return
			}
			out["content"] = string(b)
			out["language"] = language(p)
		}
		writeJSON(w, 200, out)
	case tail == "build" && r.Method == "POST":
		var b BuildRequest
		if e := body(w, r, &b); e != nil {
			failure(w, 400, e)
			return
		}
		writeJSON(w, 200, s.build(r.Context(), ws, b))
	case tail == "run" && r.Method == "POST":
		var b RunRequest
		if e := body(w, r, &b); e != nil {
			failure(w, 400, e)
			return
		}
		v, e := s.run(ws, b)
		if e != nil {
			failure(w, 400, e)
		} else {
			writeJSON(w, 200, v)
		}
	case tail == "stop" && r.Method == "POST":
		var b struct {
			Node string `json:"node_name"`
		}
		if e := body(w, r, &b); e != nil {
			failure(w, 400, e)
			return
		}
		writeJSON(w, 200, Object{"success": true, "stopped": s.stop(ws, b.Node), "message": "Node(s) stopped"})
	case tail == "graph" && r.Method == "GET":
		s.mu.Lock()
		defer s.mu.Unlock()
		writeJSON(w, 200, s.graph(ws))
	case tail == "metrics" && r.Method == "GET":
		s.mu.Lock()
		defer s.mu.Unlock()
		writeJSON(w, 200, s.metrics(ws))
	case tail == "logs" && r.Method == "GET":
		s.mu.Lock()
		defer s.mu.Unlock()
		writeJSON(w, 200, Object{"logs": ws.Logs})
	default:
		failure(w, 405, errors.New("method or endpoint not supported"))
	}
}
func language(p string) string {
	if l, ok := map[string]string{".py": "python", ".rs": "rust", ".cpp": "cpp", ".go": "go", ".json": "json", ".yaml": "yaml", ".md": "markdown", ".toml": "ini"}[filepath.Ext(p)]; ok {
		return l
	}
	return "plaintext"
}
func (s *Server) status(w *Workspace) Object {
	nodes := []Object{}
	for _, n := range w.Nodes {
		nodes = append(nodes, n.public())
	}
	return Object{"id": w.ID, "status": w.Status, "nodes": nodes, "last_activity": w.LastActivity, "executor_mode": "normal"}
}
func (s *Server) metrics(w *Workspace) Object {
	running := 0
	native := 0
	for _, n := range w.Nodes {
		if n.Mode == "native" {
			native++
		}
		if n.Status == "running" {
			running++
		}
	}
	return Object{"total_nodes": len(w.Nodes), "native_nodes": native, "legacy_nodes": len(w.Nodes) - native, "running_nodes": running, "avg_latency_us": nil, "p99_latency_us": nil, "total_messages": nil, "messages_per_second": nil, "missed_deadlines": nil, "shm_pool": nil, "safety_monitor": s.safetyStatus(), "executor_mode": "normal", "measurement_status": "executor progress monitored; aggregate ROS transport metrics unavailable"}
}
func (s *Server) graph(w *Workspace) Object {
	g := Object{"nodes": []any{}, "edges": []any{}}
	p, e := safe(w, "rosplus.graph.json")
	if e == nil {
		b, e := os.ReadFile(p)
		if e == nil {
			_ = json.Unmarshal(b, &g)
		}
	}
	if nodes, ok := g["nodes"].([]any); ok {
		for _, v := range nodes {
			if n, ok := v.(map[string]any); ok {
				id, _ := n["id"].(string)
				n["status"] = "stopped"
				n["color"] = "gray"
				if p := w.Nodes[id]; p != nil && p.Status == "running" {
					n["status"] = "healthy"
					n["color"] = "green"
				} else if p := w.Nodes[id]; p != nil && p.Status == "error" {
					n["status"] = "error"
					n["color"] = "red"
				}
			}
		}
	}
	return g
}
func (s *Server) Close() {
	s.closeSafety()
	s.mu.Lock()
	s.closing = true
	items := []*Workspace{}
	for _, w := range s.items {
		items = append(items, w)
	}
	s.mu.Unlock()
	for _, w := range items {
		s.stop(w, "")
	}
}
