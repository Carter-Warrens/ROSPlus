import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ReactFlow,
  Background,
  Controls,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type ReactFlowInstance,
} from "@xyflow/react";
import Editor, { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import "@xyflow/react/dist/style.css";
import "./style.css";
(self as any).MonacoEnvironment = { getWorker: () => new EditorWorker() };
loader.config({ monaco });
type Workspace = { id: string; name: string; status: string };
type Entry = { name: string; path: string; is_directory: boolean };
type Log = {
  timestamp: string;
  severity: string;
  node: string;
  message: string;
  sequence: number;
};
function App() {
  const [token, setToken] = useState(""),
    [connected, setConnected] = useState(false),
    [workspaces, setWorkspaces] = useState<Workspace[]>([]),
    [id, setId] = useState(""),
    [name, setName] = useState("my_robot"),
    [expert, setExpert] = useState(
      localStorage.getItem("rosplus.expert") === "true",
    ),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(""),
    [files, setFiles] = useState<Entry[]>([]),
    [directory, setDirectory] = useState("."),
    [path, setPath] = useState(""),
    [content, setContent] = useState(""),
    [language, setLanguage] = useState("python"),
    [nodes, setNodes] = useState<Node[]>([]),
    [edges, setEdges] = useState<Edge[]>([]),
    [logs, setLogs] = useState<Log[]>([]),
    [metrics, setMetrics] = useState<any>(null),
    [runTarget, setRunTarget] = useState("src/talker.py"),
    [filter, setFilter] = useState(""),
    [dirty, setDirty] = useState(false);
  const [liveNodes, setLiveNodes] = useState<any[]>([]);
  const [selectedEdge,setSelectedEdge]=useState('');
  const graphDirty = useRef(false);
  const flow = useRef<ReactFlowInstance<Node, Edge> | null>(null);
  const logEnd = useRef<HTMLDivElement>(null);
  async function api(route: string, method = "GET", data?: unknown) {
    const r = await fetch(route, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: data === undefined ? undefined : JSON.stringify(data),
    });
    const v = await r.json();
    if (!r.ok) throw Error(v.error || r.statusText);
    return v;
  }
  async function perform(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy("");
    }
  }
  const base = `/api/v1/workspace/${id}`;
  async function refresh() {
    const v = await api("/api/v1/workspace");
    setWorkspaces(v.workspaces);
    setConnected(true);
    if (!id && v.workspaces.length) setId(v.workspaces[0].id);
  }
  async function list(dir: string) {
    const v = await api(`${base}/files?path=${encodeURIComponent(dir)}`);
    setFiles(v.files);
    setDirectory(dir);
  }
  async function open(p: string) {
    if (dirty && !confirm("Discard unsaved file edits?")) return;
    const v = await api(
      `${base}/file/${p.split("/").map(encodeURIComponent).join("/")}`,
    );
    setPath(p);
    setContent(v.content);
    setLanguage(v.language);
    setDirty(false);
    setRunTarget(p);
  }
  async function saveGraph() {
    const g = {
      nodes: nodes.map((n) => ({
        id: n.id,
        label: n.data.label,
        type: n.data.kind || "publisher",
        mode: "legacy",
        managed_topic: n.data.managed === true,
        position: n.position,
      })),
      edges: edges.map((e) => ({
        source: e.source,
        target: e.target,
        topic: e.data?.topic || "/chatter",
        message_type: "std_msgs/msg/String",
      })),
    };
    await api(`${base}/file/rosplus.graph.json`, "PUT", {
      content: JSON.stringify(g, null, 2),
    });
    graphDirty.current = false;
  }
  useEffect(() => {
    localStorage.setItem("rosplus.expert", String(expert));
  }, [expert]);
  useEffect(() => {
    if (!id || !connected) return;
    setLogs([]);
    setPath("");
    setDirty(false);
    graphDirty.current = false;
    perform("Loading", async () => {
      await list(".");
      const g = await api(`${base}/graph`);
      setNodes(
        g.nodes.map((n: any, i: number) => ({
          id: n.id,
          position: n.position || { x: 100 + i * 260, y: 150 },
          data: { label: n.label, kind: n.type, managed: n.managed_topic },
        })),
      );
      setEdges(
        g.edges.map((e: any, i: number) => ({
          ...e,
          id: `edge-${i}`,
          label: e.topic,
          data: { topic: e.topic },
        })),
      );
    });
    let alive = true;
    let socket: WebSocket;
    let timer: ReturnType<typeof setTimeout>;
    let delay = 500;
    let last = 0;
    function connect() {
      if (!alive) return;
      socket = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${base}/logs`,
      );
      socket.onopen = () => {
        delay = 500;
        socket.send(
          JSON.stringify({ type: "subscribe", workspace_id: id, token }),
        );
      };
      socket.onmessage = (e) => {
        const v = JSON.parse(e.data);
        if (v.type === "log" && v.sequence > last) {
          last = v.sequence;
          setLogs((l) => [...l, v].slice(-500));
        }
        if (v.type === "metrics") setMetrics(v.data);
        if (v.type === "node_update") {
          setLiveNodes(v.nodes);
          setNodes((ns) =>
            ns.map((n) => ({
              ...n,
              style: {
                borderColor: v.nodes.some(
                  (p: any) => p.name === n.id && p.status === "running",
                )
                  ? "#42d9aa"
                  : v.nodes.some(
                        (p: any) => p.name === n.id && p.status === "error",
                      )
                    ? "#ff9a86"
                    : "#34515b",
              },
            })),
          );
        }
      };
      socket.onclose = (e) => {
        if (alive && e.code !== 1008) {
          timer = setTimeout(connect, delay);
          delay = Math.min(delay * 2, 10000);
        } else if (e.code === 1008) setError("Log authentication failed");
      };
      socket.onerror = () => socket.close();
    }
    connect();
    return () => {
      alive = false;
      clearTimeout(timer);
      socket?.close();
    };
  }, [id, connected]);
  async function add(
    kind: "publisher" | "subscriber",
    position?: { x: number; y: number },
  ) {
    const label = `${kind}_${crypto.randomUUID().slice(0, 8)}`;
    const template =
      kind === "publisher"
        ? `import rclpy\nfrom rclpy.executors import ExternalShutdownException\nfrom rclpy.node import Node\nfrom std_msgs.msg import String\n\nrclpy.init()\nnode = Node('${label}')\npublisher = node.create_publisher(String, '/chatter', 10)\ntimer = node.create_timer(0.1, lambda: publisher.publish(String(data='hello')))\ntry:\n    rclpy.spin(node)\nexcept (KeyboardInterrupt, ExternalShutdownException):\n    pass\nfinally:\n    node.destroy_node()\n    rclpy.try_shutdown()\n`
        : `import rclpy\nfrom rclpy.executors import ExternalShutdownException\nfrom rclpy.node import Node\nfrom std_msgs.msg import String\n\nrclpy.init()\nnode = Node('${label}')\nsubscription = node.create_subscription(String, '/chatter', lambda msg: node.get_logger().info(msg.data), 10)\ntry:\n    rclpy.spin(node)\nexcept (KeyboardInterrupt, ExternalShutdownException):\n    pass\nfinally:\n    node.destroy_node()\n    rclpy.try_shutdown()\n`;
    await api(`${base}/file/src/${label}.py`, "PUT", { content: "#!/usr/bin/env python3\n"+template });
    setNodes((ns) => [
      ...ns,
      {
        id: label,
        position: position || {
          x: 100 + nodes.length * 40,
          y: 100 + nodes.length * 55,
        },
        data: { label, kind, managed: true },
      },
    ]);
    graphDirty.current = true;
    await list("src");
    setRunTarget(`src/${label}.py`);
  }
  return (
    <div className="shell">
      <header>
        <a className="brand" href="/">
          ROS<span>Plus</span>
          <small>WORKBENCH</small>
        </a>
        <div className="mode">
          <button
            className={!expert ? "active" : ""}
            onClick={() => setExpert(false)}
          >
            Simple
          </button>
          <button
            className={expert ? "active" : ""}
            onClick={() => setExpert(true)}
          >
            Expert
          </button>
        </div>
        <span className="badge">LOCAL DEVELOPMENT</span>
      </header>
      {!connected ? (
        <main className="welcome">
          <p className="eyebrow">BUILD · CONNECT · OBSERVE</p>
          <h1>
            Your robot’s
            <br />
            <em>working space.</em>
          </h1>
          <p>
            Connect to your local ROSPlus service to edit nodes, run builds, and
            inspect live output.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              perform("Connecting", refresh);
            }}
          >
            <label>
              API token
              <input
                type="password"
                required
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Token from your server environment"
              />
            </label>
            <button disabled={!!busy}>{busy || "Open workbench →"}</button>
          </form>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </main>
      ) : (
        <>
          <section className="topbar">
            <select
              aria-label="Workspace"
              value={id}
              onChange={(e) => {
                if (!dirty || confirm("Discard unsaved edits?"))
                  setId(e.target.value);
              }}
            >
              <option value="">Select workspace</option>
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
            <input
              aria-label="New workspace name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <button
              disabled={!!busy}
              onClick={() =>
                perform("Creating", async () => {
                  const w = await api("/api/v1/workspace/create", "POST", {
                    name,
                    template: "talker_listener",
                  });
                  await refresh();
                  setId(w.id);
                })
              }
            >
              + Workspace
            </button>
            <div className="spacer" />
            <button
              disabled={!id || !!busy}
              onClick={() =>
                perform("Building", async () => {
                  const b = await api(`${base}/build`, "POST", {});
                  if (!b.success) throw Error(b.errors.join("\n"));
                })
              }
            >
              Build
            </button>
            <button
              disabled={!id || !!busy}
              onClick={() =>
                perform("Running", async () => {
                  await api(`${base}/run`, "POST", { target: runTarget });
                })
              }
            >
              Run
            </button>
            <button
              className="stop"
              disabled={!id || !!busy}
              onClick={() =>
                perform("Stopping", async () => {
                  await api(`${base}/stop`, "POST", {});
                })
              }
            >
              Stop all
            </button>
          </section>
          <div className="advisory">
            Standard scheduling · Hard real-time disabled · Safety GPIO is
            simulated; no physical motor protection
          </div>
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          <main className="workarea">
            <aside>
              <p className="eyebrow">NODE PALETTE</p>
              <h2>Build your graph</h2>
              <p className="muted">Add a ROS 2 node to your workspace.</p>
              {["publisher", "subscriber"].map((kind) => (
                <button
                  className="palette"
                  draggable={!!id}
                  onDragStart={(e) => {
                    e.dataTransfer.setData("application/rosplus-node", kind);
                    e.dataTransfer.effectAllowed = "copy";
                  }}
                  key={kind}
                  disabled={!id || !!busy}
                  onClick={() => perform("Adding node", () => add(kind as any))}
                >
                  <span>{kind === "publisher" ? "↗" : "↙"}</span>
                  {kind}
                  <small>Python · ROS 2</small>
                </button>
              ))}
              <label>
                {expert ? "Run target" : "Node to run"}
                {expert ? (
                  <input
                    value={runTarget}
                    onChange={(e) => setRunTarget(e.target.value)}
                  />
                ) : (
                  <select
                    value={runTarget}
                    onChange={(e) => setRunTarget(e.target.value)}
                  >
                    <option value="native:talker">
                      Rust talker (built-in)
                    </option>
                    <option value="native:listener">
                      Rust listener (built-in)
                    </option>
                    {nodes.map((n) => (
                      <option key={n.id} value={`src/${n.id}.py`}>
                        {String(n.data.label)}
                      </option>
                    ))}
                  </select>
                )}
              </label>
              {edges.some(e=>e.id===selectedEdge)&&<label>Connection topic<input aria-label="Connection topic" value={String(edges.find(e=>e.id===selectedEdge)?.data?.topic||'/chatter')} onChange={event=>{const topic=event.target.value;setEdges(es=>es.map(e=>e.id===selectedEdge?{...e,label:topic,data:{...e.data,topic}}:e));graphDirty.current=true}}/></label>}
              <p className="muted">
                Start the listener and talker separately to see messages flow.
              </p>
              {expert && (
                <>
                  <p className="eyebrow">FILES / {directory}</p>
                  <button
                    onClick={() =>
                      perform("Loading", () =>
                        list(
                          directory.split("/").slice(0, -1).join("/") || ".",
                        ),
                      )
                    }
                  >
                    ↑ Parent
                  </button>
                  {files.map((f) => (
                    <button
                      className="file"
                      key={f.path}
                      onClick={() =>
                        perform("Opening", () =>
                          f.is_directory ? list(f.path) : open(f.path),
                        )
                      }
                    >
                      {f.is_directory ? "▸" : "·"} {f.name}
                    </button>
                  ))}
                </>
              )}
            </aside>
            <section className="center">
              <div className="canvas-title">
                <h2>
                  Node graph <small>{nodes.length} nodes</small>
                </h2>
                <button
                  disabled={!id || !!busy}
                  onClick={() => perform("Saving graph", saveGraph)}
                >
                  Save graph
                </button>
              </div>
              <div
                className="canvas"
                onDragOver={(e) => {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "copy";
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  const kind = e.dataTransfer.getData(
                    "application/rosplus-node",
                  );
                  if (id && (kind === "publisher" || kind === "subscriber")) {
                    const position = flow.current?.screenToFlowPosition({
                      x: e.clientX,
                      y: e.clientY,
                    });
                    perform("Adding node", () => add(kind, position));
                  }
                }}
              >
                <ReactFlow
                  onEdgeClick={(_,edge)=>setSelectedEdge(edge.id)}
                  onInit={(instance) => {
                    flow.current = instance;
                  }}
                  onNodeClick={(_, n) => setRunTarget(`src/${n.id}.py`)}
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={(c) => {
                    setNodes((ns) => applyNodeChanges(c, ns));
                    graphDirty.current = true;
                  }}
                  onEdgesChange={(c) => {
                    setEdges((es) => applyEdgeChanges(c, es));
                    graphDirty.current = true;
                  }}
                  onConnect={(c) => {
                    setEdges((es) =>
                      addEdge(
                        {
                          ...c,
                          label: "/chatter",
                          data: { topic: "/chatter" },
                        },
                        es,
                      ),
                    );
                    graphDirty.current = true;
                  }}
                  onNodeDoubleClick={(_, n) => {
                    setExpert(true);
                    perform("Opening", () => open(`src/${n.id}.py`));
                  }}
                  fitView
                >
                  <Background color="#26414a" />
                  <Controls />
                </ReactFlow>
              </div>
              <div className="graph-note">
                Saved connections set topics for generated nodes on their next
                run.
              </div>
              {expert && (
                <div className="editor">
                  <div className="canvas-title">
                    <span>
                      {path || "Select a file"}
                      {dirty ? " • unsaved" : ""}
                    </span>
                    <button
                      disabled={!path || !!busy}
                      onClick={() =>
                        perform("Saving", async () => {
                          await api(`${base}/file/${path}`, "PUT", { content });
                          setDirty(false);
                        })
                      }
                    >
                      Save file
                    </button>
                  </div>
                  <Editor
                    height="280px"
                    theme="vs-dark"
                    language={language}
                    value={content}
                    onChange={(v) => {
                      setContent(v || "");
                      setDirty(true);
                    }}
                    options={{
                      minimap: { enabled: false },
                      fontSize: 13,
                      readOnly: !path,
                      automaticLayout: true,
                    }}
                  />
                </div>
              )}
            </section>
            <aside className="stats">
              <p className="eyebrow">RUNTIME</p>
              <h2>Live status</h2>
              <strong>{metrics?.running_nodes ?? "—"}</strong>
              <p>running nodes</p>
              <hr />
              <dl>
                <dt>Transport latency</dt>
                <dd>Not measured</dd>
                <dt>Native transport</dt>
                <dd>ROS 2 String endpoints</dd>
                <dt>Watchdog</dt>
                <dd>
                  {metrics?.safety_monitor?.estop_triggered
                    ? "E-STOP"
                    : metrics?.safety_monitor?.connected
                      ? "Simulator connected"
                      : "Disconnected"}
                </dd>
                {liveNodes.map((n) => (
                  <React.Fragment key={n.name}>
                    <dt>
                      {n.name} · {n.status}
                    </dt>
                    <dd>
                      {typeof n.cpu_percent === "number"
                        ? n.cpu_percent.toFixed(1) + "% CPU"
                        : "CPU —"}{" "}
                      /{" "}
                      {typeof n.memory_mb === "number"
                        ? n.memory_mb.toFixed(1) + " MB"
                        : "RAM —"}
                    </dd>
                  </React.Fragment>
                ))}
              </dl>
            </aside>
          </main>
          <section className="console">
            <div className="canvas-title">
              <h2>Live console</h2>
              <input
                aria-label="Filter logs"
                placeholder="Filter logs…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
              <span>{busy || "Ready"}</span>
            </div>
            <div className="log-lines">
              {!logs.length && (
                <p className="muted">Node and build output will appear here.</p>
              )}
              {logs
                .filter((l) => `${l.node} ${l.message}`.includes(filter))
                .map((l) => (
                  <div key={l.sequence} className={l.severity}>
                    <time>{l.timestamp.slice(11, 23)}</time>
                    <b>{l.node}</b>
                    <span>{l.message}</span>
                  </div>
                ))}
              <div ref={logEnd} />
            </div>
          </section>
        </>
      )}
      <footer>
        ROSPlus / 0.2 <span>Real behavior. Measured progress.</span>
      </footer>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
