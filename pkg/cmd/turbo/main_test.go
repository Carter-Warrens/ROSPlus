package main

import "testing"

func TestPythonAdapterPreservesROSEnvironment(t *testing.T) {
	t.Setenv("PYTHONPATH", "/opt/ros/test/python")
	if e := command("python3", "-c", "import os; assert '/opt/ros/test/python' in os.environ['PYTHONPATH'].split(os.pathsep)"); e != nil {
		t.Fatal(e)
	}
}
