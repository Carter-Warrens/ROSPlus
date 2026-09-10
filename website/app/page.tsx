import {
  Activity,
  ArrowUpRight,
  Bot,
  Braces,
  Cable,
  Check,
  CircleDot,
  CodeXml,
  Gauge,
  HeartPulse,
  Layers,
  ShieldCheck,
  SquareTerminal,
} from 'lucide-react';

const structuredData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'SoftwareSourceCode',
      '@id': 'https://rosplus.kchin1977.chatgpt.site/#software',
      name: 'ROSPlus',
      description:
        'A dual-mode runtime add-on layer for ROS 2 with native and legacy execution paths.',
      codeRepository: 'https://github.com/Carter-Warrens/ROSPlus',
      programmingLanguage: ['Rust', 'Go', 'Python', 'TypeScript'],
      runtimePlatform: 'ROS 2 on Linux',
      license: 'https://github.com/Carter-Warrens/ROSPlus/blob/main/LICENSE',
      author: { '@id': 'https://ros-plus.com/#organization' },
    },
    {
      '@type': 'Organization',
      '@id': 'https://rosplus.kchin1977.chatgpt.site/#organization',
      name: 'Carter Warrens LLC',
      url: 'https://www.carterwarrens.com/',
      email: 'kareem@carterwarrens.com',
    },
    {
      '@type': 'WebSite',
      '@id': 'https://rosplus.kchin1977.chatgpt.site/#website',
      url: 'https://rosplus.kchin1977.chatgpt.site/',
      name: 'ROSPlus',
      description: 'The performance layer for ROS 2.',
      publisher: { '@id': 'https://rosplus.kchin1977.chatgpt.site/#organization' },
      inLanguage: 'en-US',
    },
    {
      '@type': 'WebPage',
      '@id': 'https://rosplus.kchin1977.chatgpt.site/#webpage',
      url: 'https://rosplus.kchin1977.chatgpt.site/',
      name: 'ROSPlus — The Performance Layer for ROS 2',
      isPartOf: { '@id': 'https://rosplus.kchin1977.chatgpt.site/#website' },
      about: { '@id': 'https://rosplus.kchin1977.chatgpt.site/#software' },
      inLanguage: 'en-US',
    },
  ],
};

const capabilities = [
  {
    icon: SquareTerminal,
    title: 'One command surface',
    text: 'The turbo CLI brings build, run, test, deploy, migrate, and benchmark workflows into one tool.',
  },
  {
    icon: Layers,
    title: 'Two execution paths',
    text: 'Performance-critical Rust nodes use the native executor. Existing Python and C++ nodes keep stock ROS 2 behavior.',
  },
  {
    icon: HeartPulse,
    title: 'Independent safety rail',
    text: 'A separate watchdog process monitors the runtime and supports simulated GPIO during development.',
  },
  {
    icon: Activity,
    title: 'Visible system health',
    text: 'Structured logs, Prometheus metrics, node status, and missed-deadline tracking surface runtime behavior.',
  },
];

const current = [
  'Isolated workspace lifecycle and secure file access',
  'Legacy Python node supervision with structured logs',
  'Graph, metrics, status, health, and Prometheus endpoints',
  'Heartbeat watchdog with simulated GPIO E-Stop',
  'ROS 1 Python publisher and subscriber migration path',
];

const boundaries = [
  'Native Rust executor and shared-memory transport',
  'Measured DDS and Zenoh interoperability',
  'Physical watchdog and motor relay integration',
  'Real-time performance certification on target hardware',
];

export default function Home() {
  return (
    <main>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />
      <nav className="nav shell" aria-label="Primary navigation">
        <a className="wordmark" href="#top" aria-label="ROSPlus home">
          <span className="mark"><Bot size={20} strokeWidth={1.8} /></span>
          <span>ROS<span>Plus</span></span>
        </a>
        <div className="nav-links">
          <a href="#architecture">Architecture</a>
          <a href="#status">Status</a>
          <a href="#targets">Targets</a>
        </div>
        <a className="nav-github" href="https://github.com/Carter-Warrens/ROSPlus" target="_blank" rel="noreferrer">
          <CodeXml size={16} /> GitHub <ArrowUpRight size={14} />
        </a>
      </nav>

      <section className="hero shell" id="top">
        <div className="hero-copy">
          <p className="kicker"><CircleDot size={13} /> An add-on runtime for ROS 2</p>
          <h1>Keep the ecosystem.<br /><em>Change the ceiling.</em></h1>
          <p className="lede">
            ROSPlus gives new robotics code a high-performance path while existing ROS 2 nodes continue to run unmodified.
          </p>
          <div className="hero-actions">
            <a className="button primary" href="https://github.com/Carter-Warrens/ROSPlus" target="_blank" rel="noreferrer">
              Explore the project <ArrowUpRight size={16} />
            </a>
            <a className="button quiet" href="#architecture">See how it works</a>
          </div>
          <p className="compatibility"><Check size={15} /> Add-on layer. Stock ROS 2 stays intact.</p>
        </div>

        <div className="runtime-window" aria-label="Illustration of ROSPlus supervising native and legacy ROS 2 nodes">
          <div className="window-bar"><span /><span /><span /><p>rosplus runtime / live topology</p></div>
          <div className="runtime-status">
            <span><i className="live-dot" /> supervisor online</span>
            <code>transport: DDS</code>
          </div>
          <div className="topology">
            <div className="node native-node">
              <span>Native mode</span>
              <strong>vision_pipeline</strong>
              <code>Rust · 0 missed</code>
            </div>
            <div className="topic-line"><span>/camera/frame</span></div>
            <div className="node legacy-node">
              <span>Legacy mode</span>
              <strong>nav2_controller</strong>
              <code>rclcpp · stock executor</code>
            </div>
          </div>
          <div className="telemetry">
            <div><span>HEARTBEAT</span><strong>OK</strong></div>
            <div><span>MESSAGES</span><strong>12.8k/s</strong></div>
            <div><span>SAFETY</span><strong>ARMED</strong></div>
          </div>
          <p className="window-note">Illustrative interface. Values shown are demonstrative.</p>
        </div>
      </section>

      <div className="signal-strip" aria-hidden="true">
        <div><span>Native performance</span><i>+</i><span>Legacy compatibility</span><i>+</i><span>Independent safety</span><i>+</i><span>Fleet visibility</span></div>
      </div>

      <section className="architecture shell" id="architecture">
        <div className="section-intro">
          <p className="section-number">01 / Architecture</p>
          <h2>One supervisory layer.<br />Two ways to run.</h2>
          <p>ROSPlus manages both paths through a common command surface while nodes communicate over the same transport.</p>
        </div>

        <div className="architecture-map">
          <div className="mode mode-native">
            <div className="mode-heading"><Braces size={21} /><span>Native mode</span></div>
            <h3>The faster lane for new code</h3>
            <p>Rust nodes run inside the ROSPlus executor with scheduling, shared-memory, and allocation controls designed for deterministic workloads.</p>
            <code>turbo run perception --native</code>
          </div>
          <div className="mode mode-legacy">
            <div className="mode-heading"><Cable size={21} /><span>Legacy mode</span></div>
            <h3>Your existing ROS 2 graph</h3>
            <p>Standard rclpy and rclcpp nodes run as supervised subprocesses on stock ROS 2. Existing packages require no ROSPlus-specific rewrite.</p>
            <code>turbo run nav2 --legacy</code>
          </div>
          <div className="transport-rail">
            <span>DDS by default</span>
            <div><i /><i /><i /><i /><i /></div>
            <span>Zenoh for fleets</span>
          </div>
          <div className="supervision-row">
            <span><ShieldCheck size={18} /> Safety monitor</span>
            <span><Gauge size={18} /> Runtime metrics</span>
            <span><SquareTerminal size={18} /> Unified CLI</span>
          </div>
        </div>
      </section>

      <section className="capabilities shell">
        <p className="section-number">02 / Product surface</p>
        <div className="capability-heading">
          <h2>A more direct way<br />to build with ROS 2</h2>
          <p>Progressive disclosure keeps the first run approachable while giving experienced teams access to code, metrics, and configuration.</p>
        </div>
        <div className="capability-grid">
          {capabilities.map(({ icon: Icon, title, text }, index) => (
            <article key={title}>
              <span className="cap-index">0{index + 1}</span>
              <Icon size={25} strokeWidth={1.5} />
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="status-section" id="status">
        <div className="shell status-shell">
          <div className="status-copy">
            <p className="section-number">03 / Project status</p>
            <h2>A running reference slice,<br />with honest boundaries.</h2>
            <p>The repository separates behavior that runs today from native integrations that still require ROS 2, Linux, and robotics hardware validation.</p>
            <a href="https://github.com/Carter-Warrens/ROSPlus/blob/main/docs/IMPLEMENTATION_STATUS.md" target="_blank" rel="noreferrer">
              Read the implementation record <ArrowUpRight size={15} />
            </a>
          </div>
          <div className="status-ledger">
            <div>
              <p><span className="live-dot" /> Running in the reference slice</p>
              <ul>{current.map(item => <li key={item}><Check size={15} />{item}</li>)}</ul>
            </div>
            <div>
              <p><span className="boundary-dot" /> Native integration boundary</p>
              <ul>{boundaries.map(item => <li key={item}><span>○</span>{item}</li>)}</ul>
            </div>
          </div>
        </div>
      </section>

      <section className="targets shell" id="targets">
        <div className="targets-head">
          <div>
            <p className="section-number">04 / Engineering targets</p>
            <h2>The standard<br />the native path must meet</h2>
          </div>
          <p>Targets from the requirements document. These are acceptance criteria for future hardware testing, not published benchmark results.</p>
        </div>
        <div className="target-grid">
          <article><strong>≤ 100 µs</strong><span>p99 intra-process latency</span><small>Native mode · 1 KB messages</small></article>
          <article><strong>1M+</strong><span>messages per second</span><small>Target on i7-class hardware</small></article>
          <article><strong>&lt; 1 ms</strong><span>soft real-time jitter</span><small>Stock Ubuntu under load</small></article>
          <article><strong>&lt; 100 ms</strong><span>safety E-Stop response</span><small>Heartbeat failure to power cut</small></article>
        </div>
      </section>

      <section className="closing">
        <div className="shell closing-inner">
          <p>ROSPlus / Carter Warrens</p>
          <h2>Build on ROS 2.<br /><em>Run beyond its defaults.</em></h2>
          <div>
            <a className="button primary" href="https://github.com/Carter-Warrens/ROSPlus" target="_blank" rel="noreferrer">View the repository <ArrowUpRight size={16} /></a>
            <a href="mailto:kareem@carterwarrens.com">kareem@carterwarrens.com</a>
          </div>
        </div>
      </section>

      <footer className="footer shell">
        <div className="wordmark"><span className="mark"><Bot size={18} strokeWidth={1.8} /></span><span>ROS<span>Plus</span></span></div>
        <p>An add-on runtime layer for ROS 2</p>
        <p>© {new Date().getFullYear()} Carter Warrens LLC</p>
      </footer>
    </main>
  );
}
