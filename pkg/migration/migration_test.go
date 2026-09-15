package migration

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPreservesPayloadAndCallback(t *testing.T) {
	source := "import rospy\nfrom std_msgs.msg import String\nrospy.init_node('demo')\npub=rospy.Publisher('/out',String,queue_size=10)\ndef callback(msg):\n    pub.publish(String(data=msg.data.upper()))\nsub=rospy.Subscriber('/in',String,callback)\nrospy.spin()\n"
	out, w, e := Transform(source)
	if e != nil || len(w) > 0 {
		t.Fatalf("%v %v", w, e)
	}
	if !strings.Contains(out, "pub.publish(String(data=msg.data.upper()))") || !strings.Contains(out, "_rosplus_subscriber('/in',String,callback)") {
		t.Fatal(out)
	}
}
func TestStringsAndCommentsAreNotCalls(t *testing.T) {
	source := "import rospy\n# rospy.Publisher('fake')\nx=\"\"\"rospy.Service('fake')\"\"\"\nrospy.spin()\n"
	calls, e := Calls(source)
	if e != nil || len(calls) != 1 || calls[0].Name != "spin" {
		t.Fatalf("%v %v", calls, e)
	}
}
func TestTimerParametersAndServiceTransform(t *testing.T) {
	source := "import rospy\nrospy.init_node('node')\nvalue=rospy.get_param('~value','x')\ntimer=rospy.Timer(rospy.Duration(0.1), callback)\nservice=rospy.Service('/ready', Trigger, ready)\n"
	out, w, e := Transform(source)
	if e != nil || len(w) != 3 {
		t.Fatalf("%v %v", w, e)
	}
	for _, expected := range []string{"_rosplus_get_param", "_rosplus_timer(_RosPlusDuration", "_rosplus_service"} {
		if !strings.Contains(out, expected) {
			t.Fatalf("missing %s in %s", expected, out)
		}
	}
}
func TestUnsupportedCallIsManual(t *testing.T) {
	_, w, e := Transform("import rospy\nrospy.ServiceProxy('x',T)\n")
	if e != nil || len(w) == 0 {
		t.Fatalf("%v %v", w, e)
	}
}
func TestTreeCopiesHelpersAndNeverClaimsValidation(t *testing.T) {
	source := t.TempDir()
	os.WriteFile(filepath.Join(source, "talker.py"), []byte("import rospy\nrospy.spin()\n"), 0600)
	os.WriteFile(filepath.Join(source, "helper.py"), []byte("VALUE=42\n"), 0600)
	out := filepath.Join(t.TempDir(), "output")
	r, e := Tree(source, out, Options{GenerateTests: true})
	if e != nil || r.Status != "unvalidated" || r.FilesCopied != 1 || r.FilesMigrated != 1 {
		t.Fatalf("%+v %v", r, e)
	}
	if _, e = os.Stat(filepath.Join(out, "helper.py")); e != nil {
		t.Fatal(e)
	}
	if _, e = Tree(source, filepath.Join(source, "output"), Options{}); e == nil {
		t.Fatal("recursive output accepted")
	}
}
func TestMalformedCallsRejected(t *testing.T) {
	if _, _, e := Transform("import rospy\nrospy.Publisher('x', Type\n"); e == nil {
		t.Fatal("unbalanced call accepted")
	}
}

func TestOutputSymlinkCannotReenterSource(t *testing.T) {
	source := t.TempDir()
	alias := filepath.Join(t.TempDir(), "alias")
	if err := os.Symlink(source, alias); err != nil {
		t.Skip(err)
	}
	if _, err := Tree(source, filepath.Join(alias, "new", "output"), Options{}); err == nil {
		t.Fatal("recursive symlink output accepted")
	}
}
func TestUnsupportedAttributeRequiresReview(t *testing.T) {
	_, warnings, err := Transform("import rospy\nx = rospy.Time.now()\n")
	if err != nil || len(warnings) == 0 {
		t.Fatalf("%v %v", warnings, err)
	}
}

func TestROS1CPPIsPreservedAndMarkedManual(t *testing.T) {
	source := t.TempDir()
	input := "#include <ros/ros.h>\nint main(int argc, char **argv) { ros::init(argc, argv, \"node\"); }\n"
	if err := os.WriteFile(filepath.Join(source, "node.cpp"), []byte(input), 0600); err != nil {
		t.Fatal(err)
	}
	output := filepath.Join(t.TempDir(), "output")
	result, err := Tree(source, output, Options{})
	if err != nil || result.FilesScanned != 1 || result.FilesManual != 1 || result.Status != "partial" {
		t.Fatalf("%+v %v", result, err)
	}
	generated, err := os.ReadFile(filepath.Join(output, "node.cpp"))
	if err != nil || !strings.Contains(string(generated), "MANUAL MIGRATION REQUIRED") || !strings.Contains(string(generated), input) {
		t.Fatalf("%s %v", generated, err)
	}
}
