#!/usr/bin/env python3
"""Real DDS integration gates. Requires sourced ROS 2 and built rcl adapter."""
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
BINARY = str(ROOT / 'crates/target/release/rosplus-runtime')
ADAPTER = os.environ.get('ROSPLUS_RCL_ADAPTER', str(ROOT / 'build/librosplus_rcl.so'))

def run_pair(name, publisher, subscriber, expected, domain, required):
    env = dict(os.environ, ROS_DOMAIN_ID=str(domain), ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST', PYTHONUNBUFFERED='1')
    with tempfile.TemporaryDirectory() as directory:
        processes = []
        start = time.monotonic()
        try:
            with open(Path(directory) / 'subscriber.log', 'w+') as sublog, open(Path(directory) / 'publisher.log', 'w+') as publog:
                sub = subprocess.Popen(subscriber, env=env, stdout=sublog, stderr=subprocess.STDOUT, start_new_session=True)
                processes.append(sub)
                time.sleep(0.5)
                pub = subprocess.Popen(publisher, env=env, stdout=publog, stderr=subprocess.STDOUT, start_new_session=True)
                processes.append(pub)
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    time.sleep(0.1)
                    sublog.seek(0)
                    output = sublog.read()
                    observed=len(set(re.findall(r'ROSPlus native (\d+)', output))) if expected=='ROSPlus native' else output.count(expected)
                    if observed >= required:
                        return {'test': name, 'passed': True, 'messages_observed': observed, 'duration_seconds': round(time.monotonic() - start, 3)}
                    if sub.poll() is not None:
                        raise RuntimeError(f'{name}: subscriber exited ({sub.returncode}): {output}')
                    if pub.poll() is not None and pub.returncode != 0:
                        publog.seek(0)
                        raise RuntimeError(f'{name}: publisher exited: {publog.read()}')
                publog.seek(0)
                raise RuntimeError(f'{name}: timed out\nSUBSCRIBER:\n{output}\nPUBLISHER:\n{publog.read()}')
        finally:
            for process in processes:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
            for process in processes:
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


def main():
    publish = [BINARY, 'dds-publish', '--adapter', ADAPTER, '--messages', '100', '--frequency', '100']
    subscribe = [BINARY, 'dds-subscribe', '--adapter', ADAPTER, '--messages', '100']
    cases = [
        ('rust_to_stock_python', publish, ['ros2', 'run', 'demo_nodes_py', 'listener'], 'ROSPlus native', 100),
        ('stock_cpp_to_rust', ['ros2', 'run', 'demo_nodes_cpp', 'talker'], subscribe, '"event":"received"', 5),
        ('rust_to_rust', publish, subscribe, 'ROSPlus native', 100),
    ]
    results = []
    for index, (name, pub, sub, expected, required) in enumerate(cases):
        result = run_pair(name, pub, sub, expected, 173 + index, required)
        results.append(result)
        print(json.dumps(result), flush=True)
    destination = os.environ.get('ROSPLUS_DDS_REPORT')
    if destination:
        Path(destination).write_text(json.dumps({'transport': 'stock ROS 2 rcl/RMW, std_msgs/msg/String', 'tests': results}, indent=2))

if __name__ == '__main__':
    main()
