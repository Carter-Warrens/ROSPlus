package server

import "os/exec"

func configureProcess(c *exec.Cmd) {}
func killProcess(c *exec.Cmd, force bool) {
	if c != nil && c.Process != nil {
		_ = c.Process.Kill()
	}
}
