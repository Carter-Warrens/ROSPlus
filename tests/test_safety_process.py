import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time
import unittest

BINARY=Path(__file__).parents[1]/'crates/target/debug/rosplus-safety'
@unittest.skipUnless(BINARY.exists(),'build the Rust safety binary first')
class SafetyProcessTests(unittest.TestCase):
    def test_separate_process_latches_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'s.sock';log=Path(d)/'gpio.jsonl'
            p=subprocess.Popen([str(BINARY),'--simulate','--socket',str(path),'--log',str(log),'--timeout-ms','40'],stderr=subprocess.PIPE)
            try:
                for _ in range(100):
                    if path.exists():break
                    time.sleep(.005)
                s=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
                with s:
                    s.bind(str(Path(d)/'client.sock'));s.settimeout(.2)
                    for _ in range(8):
                        s.sendto(struct.pack('<QII',time.time_ns(),1,3),str(path));self.assertEqual(s.recv(1),b'\x00');time.sleep(.005)
                    start=time.monotonic();p.wait(timeout=.2)
                    self.assertLess(time.monotonic()-start,.1)
                events=[json.loads(line) for line in log.read_text().splitlines()]
                self.assertEqual(events[-1]['reason'],'E_STOP')
                self.assertEqual(events[-1]['state'],'LOW')
                self.assertNotEqual(p.returncode,0)
            finally:
                if p.poll() is None:p.kill();p.wait()
                p.stderr.close()
    def test_bad_health_trips_immediately(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'s.sock';log=Path(d)/'gpio.jsonl'
            p=subprocess.Popen([str(BINARY),'--simulate','--socket',str(path),'--log',str(log)],stderr=subprocess.PIPE)
            try:
                for _ in range(100):
                    if path.exists():break
                    time.sleep(.005)
                with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as s:s.sendto(struct.pack('<QII',time.time_ns(),1,0),str(path))
                p.wait(timeout=.2)
                self.assertEqual(json.loads(log.read_text().splitlines()[-1])['reason'],'E_STOP')
            finally:
                if p.poll() is None:p.kill();p.wait()
                p.stderr.close()
