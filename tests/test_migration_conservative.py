import ast
import tempfile
import unittest
from pathlib import Path
from rosplus.migration import migrate_python,migrate_tree

class MigrationTests(unittest.TestCase):
    def test_preserves_publisher_and_callback_body(self):
        source="""import rospy
from std_msgs.msg import String
rospy.init_node('combo')
pub = rospy.Publisher('/out', String, queue_size=5)
def callback(msg):
    pub.publish(String(data=msg.data.upper()))
sub = rospy.Subscriber('/in', String, callback)
rospy.spin()
"""
        generated,warnings=migrate_python(source,'combo')
        ast.parse(generated)
        self.assertFalse(warnings)
        self.assertIn('msg.data.upper()',generated)
        self.assertIn("_rosplus_subscriber('/in', String, callback)",generated)
    def test_unsupported_never_claims_success(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'source';source.mkdir();(source/'node.py').write_text("import rospy\nrospy.Service('x', object, callback)\n")
            result=migrate_tree(source,Path(root)/'output')
            self.assertEqual(result.status,'partial')
    def test_output_recursion_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):migrate_tree(Path(root),Path(root)/'output')
    def test_validation_scaffold_fails_not_passes(self):
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)/'output';migrate_tree(Path(__file__).parent/'fixtures/ros1_workspace',output)
            text=next((output/'tests').glob('test_*.py')).read_text()
            self.assertIn('self.fail',text)
