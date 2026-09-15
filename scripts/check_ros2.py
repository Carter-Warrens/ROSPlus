#!/usr/bin/env python3
"""Exercise stock C++ publisher and Python subscriber on an isolated ROS domain."""
import os,subprocess,tempfile,time
from pathlib import Path

def main():
    env=dict(os.environ,ROS_DOMAIN_ID='173',ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST')
    with tempfile.TemporaryDirectory() as d:
        processes=[]
        try:
            with open(Path(d)/'listener.log','w+') as log:
                listener=subprocess.Popen(['ros2','run','demo_nodes_py','listener'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);processes.append(listener)
                talker=subprocess.Popen(['ros2','run','demo_nodes_cpp','talker'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT,start_new_session=True);processes.append(talker)
                deadline=time.monotonic()+15
                while time.monotonic()<deadline:
                    time.sleep(.2);log.flush();log.seek(0);text=log.read()
                    if 'I heard' in text:print('PASS: stock C++ to Python ROS 2 communication');return
                    if any(p.poll() is not None for p in processes):raise RuntimeError('ROS process exited: '+text)
                raise RuntimeError('no DDS message received within 15 seconds')
        finally:
            import signal
            for p in processes:
                if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
            for p in processes:
                try:p.wait(timeout=3)
                except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
if __name__=='__main__':main()
