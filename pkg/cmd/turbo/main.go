package main

import (
	"bytes"
	"context"
	"encoding/json"
	"encoding/xml"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"rosplus.local/control/migration"
	"rosplus.local/control/server"
	"runtime"
	"strings"
	"syscall"
	"time"
)

func main() {
	if e := run(os.Args[1:]); e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
}
func run(a []string) error {
	if len(a) == 0 {
		return errors.New("usage: turbo serve|create|list|build|run|stop|status|doctor|devices|migrate|benchmark|test|bag")
	}
	switch a[0] {
	case "serve":
		f := flag.NewFlagSet("serve", flag.ContinueOnError)
		root := f.String("root", ".rosplus-workspaces", "workspace directory")
		addr := f.String("listen", "127.0.0.1:8080", "listen address")
		frontend := f.String("frontend", "frontend/dist", "built frontend directory")
		safetyBinary := f.String("safety-binary", "crates/target/debug/rosplus-safety", "separate simulated watchdog binary; empty disables")
		cert := f.String("tls-cert", "", "TLS certificate")
		key := f.String("tls-key", "", "TLS private key")
		if e := f.Parse(a[1:]); e != nil {
			return e
		}
		if runtime.GOOS != "linux" {
			return errors.New("server execution targets Linux; remote CLI works on this platform")
		}
		host, _, e := net.SplitHostPort(*addr)
		if e != nil {
			return e
		}
		if host != "localhost" && net.ParseIP(host) != nil && !net.ParseIP(host).IsLoopback() {
			return errors.New("this local developer server must bind to loopback; multi-user sandboxing is not implemented")
		}
		if host != "localhost" && (net.ParseIP(host) == nil || !net.ParseIP(host).IsLoopback()) {
			return errors.New("loopback address required")
		}
		s, e := server.New(*root, os.Getenv("ROSPLUS_API_TOKEN"), *frontend)
		if e != nil {
			return e
		}
		if *safetyBinary != "" {
			if e = s.StartSafety(*safetyBinary); e != nil {
				return e
			}
		}
		h := &http.Server{Addr: *addr, Handler: s, ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 30 * time.Second}
		ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
		defer stop()
		go func() {
			<-ctx.Done()
			s.Close()
			c, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			h.Shutdown(c)
		}()
		defer s.Close()
		fmt.Fprintf(os.Stderr, "ROSPlus local Web-IDE: http://%s\n", *addr)
		if *cert != "" || *key != "" {
			e = h.ListenAndServeTLS(*cert, *key)
		} else {
			e = h.ListenAndServe()
		}
		if e == http.ErrServerClosed {
			return nil
		}
		return e
	case "doctor":
		out := map[string]any{"os": runtime.GOOS, "arch": runtime.GOARCH, "ros_distro": os.Getenv("ROS_DISTRO")}
		for _, v := range []string{"cargo", "rustc", "go", "python3", "ros2", "colcon", "cmake"} {
			p, e := exec.LookPath(v)
			if e != nil {
				out[v] = nil
			} else {
				out[v] = p
			}
		}
		return printJSON(out)
	case "devices":
		devices := []string{}
		for _, p := range []string{"/dev/video*", "/dev/ttyUSB*", "/dev/ttyACM*"} {
			m, _ := filepath.Glob(p)
			devices = append(devices, m...)
		}
		return printJSON(map[string]any{"devices": devices})
	case "migrate":
		if len(a) < 2 {
			return errors.New("usage: turbo migrate SOURCE --output DIRECTORY")
		}
		f := flag.NewFlagSet("migrate", flag.ContinueOnError)
		output := f.String("output", "", "destination directory")
		dry := f.Bool("dry-run", false, "preview only")
		noTests := f.Bool("no-tests", false, "omit failing validation scaffolds")
		if e := f.Parse(a[2:]); e != nil {
			return e
		}
		if *output == "" {
			return errors.New("--output is required")
		}
		result, e := migration.Tree(a[1], *output, migration.Options{GenerateTests: !*noTests, DryRun: *dry})
		if e != nil {
			return e
		}
		if e = printJSON(result); e != nil {
			return e
		}
		return result.IncompleteError()
	case "benchmark":
		for i, value := range a[1:] {
			if value == "--compare" {
				args := append([]string{}, a[1:i+1]...)
				args = append(args, a[i+2:]...)
				return command("python3", append([]string{"scripts/benchmark_compare.py"}, args...)...)
			}
		}
		return command("crates/target/release/rosplus-runtime", append([]string{"benchmark"}, a[1:]...)...)
	case "bag":
		if len(a) < 2 || (a[1] != "record" && a[1] != "play") {
			return errors.New("usage: turbo bag record|play [ROS arguments]")
		}
		return command("ros2", append([]string{"bag"}, a[1:]...)...)
	case "test":
		return tests(a[1:])
	case "list":
		return request("GET", "/api/v1/workspace", nil)
	case "create":
		if len(a) < 2 {
			return errors.New("usage: turbo create NAME [TEMPLATE]")
		}
		t := "empty"
		if len(a) > 2 {
			t = a[2]
		}
		return request("POST", "/api/v1/workspace/create", map[string]any{"name": a[1], "template": t})
	case "build", "run", "stop", "status":
		if len(a) < 2 {
			return errors.New("workspace ID required")
		}
		path := "/api/v1/workspace/" + a[1] + "/" + a[0]
		if a[0] == "status" {
			return request("GET", path, nil)
		}
		b := map[string]any{}
		if a[0] == "run" {
			if len(a) < 3 {
				return errors.New("usage: turbo run ID TARGET [NODE ARGS...]")
			}
			b["target"] = a[2]
			b["args"] = a[3:]
		}
		if a[0] == "stop" && len(a) > 2 {
			b["node_name"] = a[2]
		}
		return request("POST", path, b)
	case "--version", "version":
		fmt.Println("ROSPlus 0.2.0")
		return nil
	}
	return fmt.Errorf("unknown command %q", a[0])
}
func request(method, path string, value any) error {
	base := os.Getenv("ROSPLUS_URL")
	if base == "" {
		base = "http://127.0.0.1:8080"
	}
	b, e := json.Marshal(value)
	if e != nil {
		return e
	}
	r, e := http.NewRequest(method, strings.TrimRight(base, "/")+path, bytes.NewReader(b))
	if e != nil {
		return e
	}
	r.Header.Set("Authorization", "Bearer "+os.Getenv("ROSPLUS_API_TOKEN"))
	r.Header.Set("Content-Type", "application/json")
	c := &http.Client{Timeout: 11 * time.Minute}
	resp, e := c.Do(r)
	if e != nil {
		return e
	}
	defer resp.Body.Close()
	data, e := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if e != nil {
		return e
	}
	fmt.Println(string(data))
	if resp.StatusCode >= 400 {
		return fmt.Errorf("API returned %s", resp.Status)
	}
	var result struct {
		Success *bool `json:"success"`
	}
	_ = json.Unmarshal(data, &result)
	if result.Success != nil && !*result.Success {
		return errors.New("operation failed")
	}
	return nil
}
func printJSON(v any) error { return json.NewEncoder(os.Stdout).Encode(v) }
func command(name string, args ...string) error {
	c := exec.Command(name, args...)
	c.Stdin = os.Stdin
	c.Stdout = os.Stdout
	c.Stderr = os.Stderr
	c.Env = append(os.Environ(), "PYTHONPATH=src"+string(os.PathListSeparator)+os.Getenv("PYTHONPATH"))
	return c.Run()
}

type Suite struct {
	XMLName  xml.Name `xml:"testsuite"`
	Name     string   `xml:"name,attr"`
	Tests    int      `xml:"tests,attr"`
	Failures int      `xml:"failures,attr"`
	Cases    []Case   `xml:"testcase"`
}
type Case struct {
	Name    string  `xml:"name,attr"`
	Time    float64 `xml:"time,attr"`
	Failure *string `xml:"failure,omitempty"`
	Output  string  `xml:"system-out"`
}

func tests(a []string) error {
	f := flag.NewFlagSet("test", flag.ContinueOnError)
	junit := f.String("junit-xml", "test-results.xml", "JUnit output")
	if e := f.Parse(a); e != nil {
		return e
	}
	suite := Suite{Name: "rosplus"}
	commands := [][]string{{"python3", "-m", "unittest", "discover", "-s", "tests", "-v"}, {"cargo", "test", "--manifest-path", "crates/Cargo.toml"}, {"go", "test", "-race", "./..."}, {"npm", "run", "build"}}
	for i, args := range commands {
		start := time.Now()
		c := exec.Command(args[0], args[1:]...)
		c.Env = append(os.Environ(), "PYTHONPATH=src"+string(os.PathListSeparator)+os.Getenv("PYTHONPATH"))
		if i == 2 {
			c.Dir = "pkg"
		}
		if i == 3 {
			c.Dir = "frontend"
		}
		out, e := c.CombinedOutput()
		fmt.Print(string(out))
		item := Case{Name: strings.Join(args, " "), Time: time.Since(start).Seconds(), Output: string(out)}
		if e != nil {
			t := e.Error()
			item.Failure = &t
			suite.Failures++
		}
		suite.Cases = append(suite.Cases, item)
		suite.Tests++
	}
	b, e := xml.MarshalIndent(suite, "", "  ")
	if e != nil {
		return e
	}
	if e = os.WriteFile(*junit, append([]byte(xml.Header), b...), 0600); e != nil {
		return e
	}
	if suite.Failures > 0 {
		return fmt.Errorf("%d suites failed", suite.Failures)
	}
	return nil
}
