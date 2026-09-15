#!/usr/bin/env python3
"""Stock rclpy executor baseline for the same timestamped String workload."""
import argparse,json,math,os,time
from pathlib import Path
import rclpy
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import String

def main():
    p=argparse.ArgumentParser()
    p.add_argument('role',choices=['dds-publish','dds-subscribe'])
    p.add_argument('--messages',type=int,default=10000)
    p.add_argument('--size',type=int,default=1024)
    p.add_argument('--frequency',type=float,default=1000)
    p.add_argument('--latency-report')
    p.add_argument('--timeout-seconds',type=int,default=30)
    p.add_argument('--quiet',action='store_true')
    p.add_argument('--latency-payload',action='store_true')
    p.add_argument('--fifo',action='store_true')
    args=p.parse_args()
    scheduling={'policy':'normal','warnings':[]}
    if args.fifo:
        try:os.sched_setscheduler(0,os.SCHED_FIFO,os.sched_param(20));scheduling['policy']='soft_rt'
        except OSError as e:scheduling['warnings'].append(str(e))
    rclpy.init(args=[])
    node=rclpy.create_node('stock_'+args.role.replace('-','_'))
    executor=SingleThreadedExecutor();executor.add_node(node)
    count=0;latencies=[]
    try:
        if args.role=='dds-publish':
            pub=node.create_publisher(String,'/chatter',10)
            time.sleep(2)
            started=time.monotonic()
            def publish():
                nonlocal count
                prefix=f'rosplus-latency:{count}:{time.monotonic_ns()}:'
                pub.publish(String(data=prefix+'x'*max(0,args.size-len(prefix))))
                count+=1
            timer=node.create_timer(1/args.frequency,publish)
            deadline=started+args.timeout_seconds
            while count<args.messages and time.monotonic()<deadline:executor.spin_once(timeout_sec=.1)
            print(json.dumps({'event':'publisher_summary','messages':count,'duration_seconds':time.monotonic()-started,'configured_frequency_hz':args.frequency}),flush=True)
        else:
            def received(msg):
                nonlocal count
                timestamp=time.monotonic_ns()
                pieces=msg.data.split(':',3)
                if len(pieces)==4 and pieces[0]=='rosplus-latency':latencies.append((timestamp-int(pieces[2]))/1000)
                count+=1
            subscription=node.create_subscription(String,'/chatter',received,10)
            deadline=time.monotonic()+args.timeout_seconds
            while count<args.messages and time.monotonic()<deadline:executor.spin_once(timeout_sec=.1)
            latencies.sort()
            percentile=lambda q:latencies[math.ceil((len(latencies)-1)*q)] if latencies else None
            result={'benchmark':'stock_rclpy_cross_process','transport':'stock rclpy/RMW std_msgs/msg/String','scheduler':scheduling,'expected_messages':args.messages,'received_messages':count,'latency_samples':len(latencies),'p50_latency_us':percentile(.5),'p95_latency_us':percentile(.95),'p99_latency_us':percentile(.99),'max_latency_us':latencies[-1] if latencies else None,'clock':'CLOCK_MONOTONIC; same-host endpoints','includes':'payload construction after timestamp, serialization, DDS, stock executor dispatch and deserialization'}
            if args.latency_report:Path(args.latency_report).write_text(json.dumps(result,indent=2))
            print(json.dumps(result),flush=True)
        if count<args.messages:raise RuntimeError(f'only processed {count}/{args.messages}')
    finally:
        executor.shutdown();node.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
