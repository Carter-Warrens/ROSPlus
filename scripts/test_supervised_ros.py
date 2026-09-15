#!/usr/bin/env python3
"""Go API -> supervised native/legacy nodes -> real DDS messages."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
import socket
import shutil

ROOT=Path(__file__).resolve().parents[1]
TOKEN='disposable-supervised-ros-test-token'

def main():
    with tempfile.TemporaryDirectory() as directory:
        with socket.socket() as s:
            s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        env=dict(os.environ,ROSPLUS_API_TOKEN=TOKEN,ROS_DOMAIN_ID='177',ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST')
        log=open(Path(directory)/'server.log','w+')
        process=subprocess.Popen([str(ROOT/'build/turbo'),'serve','--listen',f'127.0.0.1:{port}','--root',str(Path(directory)/'workspaces'),'--safety-binary',str(ROOT/'crates/target/debug/rosplus-safety')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        def api(path,method='GET',data=None):
            req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)
            except urllib.error.HTTPError as error:
                raise RuntimeError(f'{method} {path}: {error.code} {error.read().decode()}') from error
        try:
            for _ in range(100):
                if process.poll() is not None:log.seek(0);raise RuntimeError(log.read())
                try:api('/health');break
                except OSError:time.sleep(.05)
            w=api('/api/v1/workspace/create','POST',{'name':'supervised_ros','template':'talker_listener'})
            path='/api/v1/workspace/'+w['id']
            build=api(path+'/build','POST',{})
            if not build['success']:raise RuntimeError(build)
            results=[{'test':'colcon_template_build','passed':True}]
            plugin=Path(w['path'])/'libexample_native.so'
            subprocess.run([
                'cc','-std=c11','-Wall','-Wextra','-Werror','-fPIC','-shared',
                '-I',str(ROOT/'native'),str(ROOT/'native/example_native_publisher.c'),
                '-o',str(plugin)
            ],check=True)
            rust_plugin=Path(w['path'])/'libexample_native_rust.so'
            shutil.copyfile(ROOT/'crates/target/release/librosplus_native_rust_example.so',rust_plugin)
            stalled_plugin=Path(w['path'])/'libstalled_native.so'
            subprocess.run([
                'cc','-std=c11','-Wall','-Wextra','-Werror','-fPIC','-shared',
                '-I',str(ROOT/'native'),str(ROOT/'tests/fixtures/native/stalled_native_publisher.c'),
                '-o',str(stalled_plugin)
            ],check=True)
            for name,publisher,subscriber,expected in [
                ('native_to_legacy','native:talker','src/listener.py','ROSPlus native'),
                ('plugin_to_legacy','native:plugin:libexample_native.so','src/listener.py','ROSPlus plugin'),
                ('rust_plugin_to_legacy','native:plugin:libexample_native_rust.so','src/listener.py','ROSPlus Rust plugin'),
                ('legacy_to_native','src/talker.py','native:listener','hello '),
                ('stock_cpp_to_native','ros2:demo_nodes_cpp:talker','native:listener','Hello World'),
            ]:
                before=len(api(path+'/logs')['logs'])
                api(path+'/run','POST',{'target':subscriber})
                api(path+'/run','POST',{'target':publisher})
                deadline=time.monotonic()+15
                while time.monotonic()<deadline:
                    time.sleep(.1)
                    logs=api(path+'/logs')['logs'][before:]
                    matched=[l for l in logs if expected in l['message'] and ('received' in l['message'])]
                    if len(matched)>=5:break
                else:raise RuntimeError(f'{name}: no DDS exchange: {logs}')
                metrics=api(path+'/metrics')
                if metrics['native_nodes']<1 or metrics['legacy_nodes']<1:raise AssertionError(metrics)
                if metrics['safety_monitor']['executor_connected'] is not True:raise AssertionError(metrics['safety_monitor'])
                api(path+'/stop','POST',{})
                time.sleep(.2)
                stopped_logs=api(path+'/logs')['logs'][before:]
                if any('ExternalShutdownException' in item['message'] for item in stopped_logs):
                    raise AssertionError('normal stop produced a shutdown traceback')
                if name == 'plugin_to_legacy' and not any('plugin_shutdown' in item['message'] for item in stopped_logs):
                    raise AssertionError('native plugin shutdown callback was not observed')
                result={'test':name,'passed':True,'messages_observed':len(matched),'executor_progress_healthy':True}
                if name == 'plugin_to_legacy':result['abi']='v1-c';result['shutdown_callback_observed']=True
                if name == 'rust_plugin_to_legacy':result['abi']='v1-rust'
                results.append(result)
            started=time.monotonic()
            api(path+'/run','POST',{'target':'native:plugin:libstalled_native.so'})
            deadline=started+.5
            while time.monotonic()<deadline:
                safety=api(path+'/metrics')['safety_monitor']
                if safety['estop_triggered'] is True:break
                time.sleep(.005)
            else:raise AssertionError('stalled native callback did not trigger E-Stop')
            elapsed_ms=(time.monotonic()-started)*1000
            if elapsed_ms>=100:raise AssertionError(f'E-Stop response took {elapsed_ms:.1f} ms')
            deadline=time.monotonic()+4
            while time.monotonic()<deadline:
                status=api(path+'/status')
                stalled=[n for n in status['nodes'] if n['name']=='libstalled_native']
                if stalled and stalled[0]['status'] in ('stopped','error'):break
                time.sleep(.02)
            else:raise AssertionError('stalled native process was not stopped')
            safety_events=[json.loads(line) for line in (Path(directory)/'workspaces/safety-gpio.jsonl').read_text().splitlines()]
            if not safety_events or safety_events[-1]['reason']!='E_STOP':raise AssertionError('GPIO simulator did not record E_STOP')
            results.append({'test':'stalled_native_callback_estop','passed':True,'response_ms':elapsed_ms,'threshold_ms':100,'heartbeat_source':'executor_progress_pipe','gpio_event':safety_events[-1]['reason']})
            print(json.dumps({'supervised_dds':results}),flush=True)
            destination=os.environ.get('ROSPLUS_SUPERVISED_REPORT')
            if destination:Path(destination).write_text(json.dumps(results,indent=2))
        except Exception:
            if 'path' in locals():
                try:print(json.dumps(api(path+'/logs'),indent=2),flush=True)
                except Exception:pass
            log.flush();log.seek(0);print(log.read(),flush=True)
            raise
        finally:
            process.send_signal(signal.SIGINT)
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            log.close()
if __name__=='__main__':main()
