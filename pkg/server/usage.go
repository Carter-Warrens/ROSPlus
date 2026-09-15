package server

import (
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
)

var clockOnce sync.Once
var clockTicks float64

// Linux /proc stat includes all threads. CPU is the process lifetime average,
// expressed as a percentage of one logical CPU (multi-threaded nodes can exceed 100).
func processUsage(pid int, elapsed float64) (any, any) {
	var memory any
	if b, e := os.ReadFile(fmt.Sprintf("/proc/%d/status", pid)); e == nil {
		for _, line := range strings.Split(string(b), "\n") {
			f := strings.Fields(line)
			if len(f) >= 2 && f[0] == "VmRSS:" {
				if kb, e := strconv.ParseFloat(f[1], 64); e == nil {
					memory = kb / 1024
				}
			}
		}
	}
	clockOnce.Do(func() {
		if b, e := exec.Command("getconf", "CLK_TCK").Output(); e == nil {
			clockTicks, _ = strconv.ParseFloat(strings.TrimSpace(string(b)), 64)
		}
	})
	if clockTicks <= 0 || elapsed <= 0 {
		return nil, memory
	}
	b, e := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
	if e != nil {
		return nil, memory
	}
	end := strings.LastIndex(string(b), ")")
	if end < 0 {
		return nil, memory
	}
	fields := strings.Fields(string(b[end+1:]))
	if len(fields) < 13 {
		return nil, memory
	}
	user, e1 := strconv.ParseFloat(fields[11], 64)
	system, e2 := strconv.ParseFloat(fields[12], 64)
	if e1 != nil || e2 != nil {
		return nil, memory
	}
	return (user + system) / clockTicks / elapsed * 100, memory
}
