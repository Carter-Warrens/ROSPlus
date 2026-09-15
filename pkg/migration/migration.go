// Package migration transforms a bounded Python call-expression AST while
// preserving application statements. It is not a complete Python compiler.
package migration

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"unicode"
)

type Result struct {
	FilesScanned  int      `json:"files_scanned"`
	FilesMigrated int      `json:"files_migrated"`
	FilesManual   int      `json:"files_manual"`
	FilesCopied   int      `json:"files_copied"`
	Warnings      []string `json:"warnings"`
	Outputs       []string `json:"outputs"`
	Status        string   `json:"status"`
	Validation    string   `json:"validation"`
}
type Options struct{ GenerateTests, DryRun bool }
type token struct {
	text       string
	start, end int
	kind       byte
}
type Call struct {
	Name             string
	Start, Open, End int
	Arguments        string
}
type edit struct {
	start, end int
	text       string
}

var importLine = regexp.MustCompile(`(?m)^[\t ]*import rospy[\t ]*(?:#[^\n]*)?(?:\n|$)`)
var unsupportedImport = regexp.MustCompile(`(?m)^[\t ]*(?:from rospy\b|import rospy\s+as\b|import [^\n]*,\s*rospy\b|import rospy\s*,)`)
var ros1CPP = regexp.MustCompile(`(?m)^\s*#\s*include\s*[<"]ros/ros\.h[>"]`)

// lex excludes strings/comments from identifier recognition, including triple
// quoted literals. Unknown syntax is never reported as validated Python.
func lex(source string) ([]token, error) {
	out := []token{}
	for i := 0; i < len(source); {
		start := i
		c := source[i]
		if c == '#' {
			for i < len(source) && source[i] != '\n' {
				i++
			}
			continue
		}
		if c == '\'' || c == '"' {
			quote := c
			triple := i+2 < len(source) && source[i+1] == quote && source[i+2] == quote
			step := 1
			if triple {
				step = 3
			}
			i += step
			closed := false
			for i < len(source) {
				if source[i] == '\\' {
					i += 2
					continue
				}
				if source[i] == quote && (!triple || (i+2 < len(source) && source[i+1] == quote && source[i+2] == quote)) {
					i += step
					closed = true
					break
				}
				i++
			}
			if !closed {
				return nil, errors.New("unterminated Python string")
			}
			out = append(out, token{source[start:i], start, i, 's'})
			continue
		}
		if unicode.IsSpace(rune(c)) {
			i++
			continue
		}
		if c == '_' || c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' {
			i++
			for i < len(source) {
				c = source[i]
				if !(c == '_' || c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9') {
					break
				}
				i++
			}
			out = append(out, token{source[start:i], start, i, 'n'})
			continue
		}
		i++
		out = append(out, token{source[start:i], start, i, 'p'})
	}
	return out, nil
}

// Calls parses balanced call expressions rooted at the rospy module. Control
// flow and user callbacks remain byte-for-byte unchanged in the output.
func Calls(source string) ([]Call, error) {
	tokens, e := lex(source)
	if e != nil {
		return nil, e
	}
	calls := []Call{}
	for i := 0; i+3 < len(tokens); i++ {
		if tokens[i].kind != 'n' || tokens[i].text != "rospy" || tokens[i+1].text != "." || tokens[i+2].kind != 'n' || tokens[i+3].text != "(" {
			continue
		}
		depth := 1
		end := i + 4
		for ; end < len(tokens); end++ {
			if tokens[end].kind == 's' {
				continue
			}
			if tokens[end].text == "(" {
				depth++
			}
			if tokens[end].text == ")" {
				depth--
				if depth == 0 {
					break
				}
			}
			if depth > 256 {
				return nil, errors.New("Python expression nesting exceeds supported limit")
			}
		}
		if depth != 0 {
			return nil, errors.New("unbalanced rospy call")
		}
		calls = append(calls, Call{tokens[i+2].text, tokens[i].start, tokens[i+3].end, tokens[end].end, source[tokens[i+3].end:tokens[end].start]})
	}
	return calls, nil
}

func Transform(source string) (string, []string, error) {
	if len(source) > 2<<20 {
		return "", nil, errors.New("Python source exceeds 2 MiB limit")
	}
	calls, e := Calls(source)
	if e != nil {
		return "", nil, e
	}
	warnings := []string{}
	edits := []edit{}
	if unsupportedImport.MatchString(source) {
		warnings = append(warnings, "aliased, combined or from-rospy imports require manual migration")
	}
	for _, span := range importLine.FindAllStringIndex(source, -1) {
		edits = append(edits, edit{span[0], span[1], "# rospy import replaced by ROSPlus helpers\n"})
	}
	mapping := map[string]string{
		"init_node":  "_rosplus_init",
		"Publisher":  "_rosplus_publisher",
		"Subscriber": "_rosplus_subscriber",
		"Rate":       "_RosPlusRate",
		"Duration":   "_RosPlusDuration",
		"Timer":      "_rosplus_timer",
		"Service":    "_rosplus_service",
		"get_param":  "_rosplus_get_param",
		"set_param":  "_rosplus_set_param",
		"has_param":  "_rosplus_has_param",
		"sleep":      "_rosplus_sleep",
		"spin":       "_rosplus_spin",
	}
	for _, call := range calls {
		if replacement, ok := mapping[call.Name]; ok {
			edits = append(edits, edit{call.Start, call.Open, replacement + "("})
			if call.Name == "init_node" && strings.Contains(call.Arguments, "=") {
				warnings = append(warnings, "non-default init_node options require review")
			}
			if call.Name == "Publisher" || call.Name == "Subscriber" {
				args, _ := lex(call.Arguments)
				for i := 1; i < len(args); i++ {
					if args[i].text == "=" && args[i-1].text != "queue_size" {
						warnings = append(warnings, "publisher/subscriber keyword options require review")
					}
				}
			}
			if call.Name == "Timer" {
				warnings = append(warnings, "timer callback receives no ROS 1 TimerEvent; timer behavior requires review")
			}
			if call.Name == "Service" {
				warnings = append(warnings, "service response adaptation requires review")
			}
			if call.Name == "get_param" || call.Name == "set_param" || call.Name == "has_param" {
				warnings = append(warnings, "ROS 1 global parameter names become node-local ROS 2 parameters")
			}
			continue
		}
		if call.Name == "is_shutdown" && strings.TrimSpace(call.Arguments) == "" {
			edits = append(edits, edit{call.Start, call.End, "(not _rclpy.ok())"})
			continue
		}
		if level, ok := map[string]string{"loginfo": "info", "logwarn": "warning", "logerr": "error", "logdebug": "debug"}[call.Name]; ok {
			edits = append(edits, edit{call.Start, call.Open, "_rosplus_log('" + level + "', "})
			continue
		}
		warnings = append(warnings, "rospy."+call.Name+" requires manual migration")
	}
	tokens, _ := lex(source)
	for _, t := range tokens {
		if t.kind != 'n' {
			continue
		}
		if strings.HasPrefix(t.text, "_rosplus") || t.text == "_rclpy" || t.text == "_RosPlusRate" || t.text == "_Node" || t.text == "_time" {
			warnings = append(warnings, "source identifier conflicts with generated helper namespace")
		}
		if t.text == "actionlib" || t.text == "tf" || t.text == "dynamic_reconfigure" {
			warnings = append(warnings, "unsupported ROS 1 dependency "+t.text+" remains")
		}
		if t.text == "rospy" {
			covered := false
			for _, edit := range edits {
				if t.start >= edit.start && t.end <= edit.end {
					covered = true
					break
				}
			}
			if !covered {
				warnings = append(warnings, "unconverted rospy reference or binding remains")
			}
		}
	}
	sort.Slice(edits, func(i, j int) bool { return edits[i].start > edits[j].start })
	output := source
	last := len(source)
	for _, v := range edits {
		if v.end > last {
			return "", nil, errors.New("overlapping Python transformation")
		}
		output = output[:v.start] + v.text + output[v.end:]
		last = v.start
	}
	// Future imports must precede generated helper imports.
	future := regexp.MustCompile(`(?m)^from __future__ import [^\n]+\n?`)
	prefix := strings.Join(future.FindAllString(output, -1), "\n")
	output = future.ReplaceAllString(output, "")
	set := map[string]bool{}
	unique := []string{}
	for _, w := range warnings {
		if !set[w] {
			set[w] = true
			unique = append(unique, w)
		}
	}
	sort.Strings(unique)
	notes := ""
	for _, w := range unique {
		notes += "# TODO: MANUAL MIGRATION REQUIRED: " + w + "\n"
	}
	return "#!/usr/bin/env python3\n" + prefix + "\n" + runtimeHelpers + "\n" + notes + output, unique, nil
}

func Tree(source, output string, options Options) (Result, error) {
	result := Result{Warnings: []string{}, Outputs: []string{}, Status: "unvalidated", Validation: "not_run"}
	source, e := filepath.Abs(source)
	if e != nil {
		return result, e
	}
	source, e = filepath.EvalSymlinks(source)
	if e != nil {
		return result, e
	}
	output, e = filepath.Abs(output)
	if e != nil {
		return result, e
	}
	// Resolve existing parents too, so a symlink cannot hide recursive output.
	output, e = resolveDestination(output)
	if e != nil {
		return result, e
	}
	relative, e := filepath.Rel(source, output)
	if e != nil {
		return result, e
	}
	if relative == "." || relative != ".." && !strings.HasPrefix(relative, ".."+string(os.PathSeparator)) {
		return result, errors.New("output must be outside source tree")
	}
	if info, e := os.Stat(source); e != nil || !info.IsDir() {
		return result, errors.New("source directory not found")
	}
	if entries, e := os.ReadDir(output); e == nil && len(entries) > 0 {
		return result, errors.New("output directory must be empty")
	}
	e = filepath.WalkDir(source, func(path string, d os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if d.IsDir() {
			if d.Name() == ".git" || d.Name() == "__pycache__" || d.Name() == ".venv" || d.Name() == "node_modules" {
				return filepath.SkipDir
			}
			return nil
		}
		extension := strings.ToLower(filepath.Ext(path))
		isPython := extension == ".py"
		isCPP := extension == ".cc" || extension == ".cpp" || extension == ".cxx" || extension == ".h" || extension == ".hh" || extension == ".hpp"
		if !isPython && !isCPP {
			return nil
		}
		result.FilesScanned++
		if d.Type()&os.ModeSymlink != 0 {
			result.FilesManual++
			result.Warnings = append(result.Warnings, path+": symlink skipped")
			return nil
		}
		b, e := os.ReadFile(path)
		if e != nil {
			return e
		}
		relative, _ := filepath.Rel(source, path)
		target := filepath.Join(output, relative)
		text := string(b)
		if isCPP {
			if !ros1CPP.MatchString(text) {
				return nil
			}
			result.FilesManual++
			warning := relative + ": ROS 1 C++ source requires manual roscpp-to-rclcpp migration"
			result.Warnings = append(result.Warnings, warning)
			result.Outputs = append(result.Outputs, target)
			if !options.DryRun {
				if e = os.MkdirAll(filepath.Dir(target), 0700); e != nil {
					return e
				}
				note := "// TODO: MANUAL MIGRATION REQUIRED: ROS 1 C++ source requires manual roscpp-to-rclcpp migration\n"
				if e = os.WriteFile(target, []byte(note+text), 0600); e != nil {
					return e
				}
			}
			return nil
		}
		hasROS := importLine.MatchString(text) || unsupportedImport.MatchString(text)
		if hasROS {
			generated, warnings, err := Transform(text)
			if err != nil {
				result.FilesManual++
				result.Warnings = append(result.Warnings, relative+": "+err.Error())
				return nil
			}
			text = generated
			if len(warnings) > 0 {
				result.FilesManual++
			} else {
				result.FilesMigrated++
			}
			for _, w := range warnings {
				result.Warnings = append(result.Warnings, relative+": "+w)
			}
		} else {
			result.FilesCopied++
		}
		result.Outputs = append(result.Outputs, target)
		if !options.DryRun {
			if e = os.MkdirAll(filepath.Dir(target), 0700); e != nil {
				return e
			}
			if e = os.WriteFile(target, []byte(text), 0600); e != nil {
				return e
			}
			if hasROS && options.GenerateTests {
				test := filepath.Join(output, "tests", "test_"+strings.NewReplacer("/", "_", "\\", "_", ".", "_").Replace(relative)+"_migration.py")
				if e = os.MkdirAll(filepath.Dir(test), 0700); e != nil {
					return e
				}
				if e = os.WriteFile(test, []byte("import unittest\n\nclass MigrationValidation(unittest.TestCase):\n    def test_equivalence(self):\n        self.fail('ROS/bag behavioral validation has not been implemented for this node')\n"), 0600); e != nil {
					return e
				}
			}
		}
		return nil
	})
	if e != nil {
		return result, e
	}
	if result.FilesManual > 0 {
		result.Status = "partial"
	}
	if !options.DryRun {
		if e = os.MkdirAll(output, 0700); e != nil {
			return result, e
		}
		b, e := json.MarshalIndent(result, "", "  ")
		if e != nil {
			return result, e
		}
		e = os.WriteFile(filepath.Join(output, "migration_result.json"), b, 0600)
		if e != nil {
			return result, e
		}
	}
	return result, nil
}

func (r Result) IncompleteError() error {
	return fmt.Errorf("migration is %s; behavioral validation is required", r.Status)
}

func resolveDestination(path string) (string, error) {
	resolved, err := filepath.EvalSymlinks(path)
	if err == nil {
		return resolved, nil
	}
	if !os.IsNotExist(err) {
		return "", err
	}
	parent := filepath.Dir(path)
	if parent == path {
		return "", err
	}
	resolved, err = resolveDestination(parent)
	if err != nil {
		return "", err
	}
	return filepath.Join(resolved, filepath.Base(path)), nil
}
