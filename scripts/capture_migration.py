#!/usr/bin/env python3
"""Capture ten std_msgs/String outputs for the supplied talker fixture only."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ros',choices=['1','2'],required=True)
    parser.add_argument('--node',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    processes=[]
    messages=[]
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['ROS_LOG_DIR']=tmp
        os.environ['ROS_HOME']=tmp
        try:
            if args.ros=='1':
                import xmlrpc.client
                master=subprocess.Popen(['roscore'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                processes.append(master)
                for _ in range(100):
                    try:
                        xmlrpc.client.ServerProxy('http://localhost:11311').getPid('/rosplus_validation')
                        break
                    except OSError:time.sleep(.05)
                import rospy
                from std_msgs.msg import String
                rospy.init_node('rosplus_validation',disable_signals=True)
                subscription=rospy.Subscriber('/chatter',String,lambda msg:messages.append(msg.data))
            else:
                import rclpy
                from std_msgs.msg import String
                rclpy.init()
                node=rclpy.create_node('rosplus_validation')
                subscription=node.create_subscription(String,'/chatter',lambda msg:messages.append(msg.data),10)
            child=subprocess.Popen(['python3',args.node],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,start_new_session=True)
            processes.append(child)
            deadline=time.monotonic()+15
            while len(messages)<10 and time.monotonic()<deadline:
                if args.ros=='1':time.sleep(.01)
                else:rclpy.spin_once(node,timeout_sec=.1)
                if child.poll() is not None:raise RuntimeError(child.stderr.read().decode())
            if len(messages)<10:raise RuntimeError(f'only captured {len(messages)} messages')
            Path(args.output).write_text(json.dumps({'ros':args.ros,'messages':messages[:10]},indent=2))
            if args.ros=='2':node.destroy_node();rclpy.shutdown()
            else:rospy.signal_shutdown('validation complete')
        finally:
            for p in processes:
                if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
            for p in reversed(processes):
                try:p.wait(timeout=3)
                except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
                if p.stderr:p.stderr.close()
if __name__=='__main__':main()
