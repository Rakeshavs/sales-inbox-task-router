import React, { useState, useEffect } from 'react';
import { Send, Upload, Sparkles, Database, MessageSquare, Table, RefreshCw, DatabaseZap, CheckCircle2, AlertCircle, HelpCircle, Mail, Layers, ShieldCheck, Filter, UserCheck, Tag, ArrowRight, Users, Briefcase, DollarSign, Megaphone, Handshake, AlertTriangle } from 'lucide-react';

const getApiBase = () => {
  if (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
    return 'http://127.0.0.1:8000';
  }
  const raw = import.meta.env.VITE_API_URL || 'https://sales-inbox-task-router-qgl7.onrender.com';
  return raw.replace(/\/+$/, '');
};

const API_BASE = getApiBase();

export default function App() {
  const [candidateId, setCandidateId] = useState('medharirakeshavs@gmail.com');
  const [rawJsonText, setRawJsonText] = useState('');
  const [parsedEmails, setParsedEmails] = useState([]);
  const [dbTasks, setDbTasks] = useState([]);
  const [activeQueueTab, setActiveQueueTab] = useState('raw_table');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  
  // Stats
  const [stats, setStats] = useState({
    processed: 0,
    tasks_created: 0,
    tasks_updated: 0,
    skipped: 0
  });

  // Chat State
  const [chatQuery, setChatQuery] = useState('');
  const [chatMessages, setChatMessages] = useState([
    {
      sender: 'system',
      text: 'Hello! I am your Sales Inbox Operations Assistant. Route email batches, view team member task queues, or ask natural language questions about processed data.',
      supportingData: null
    }
  ]);
  const [isChatLoading, setIsChatLoading] = useState(false);

  useEffect(() => {
    fetchStats();
    fetchLiveTasks();
  }, [candidateId]);

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/stats?candidate_id=${encodeURIComponent(candidateId)}`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.error("Failed to fetch stats:", e);
    }
  };

  const fetchLiveTasks = async () => {
    try {
      const res = await fetch(`${API_BASE}/tasks?candidate_id=${encodeURIComponent(candidateId)}`);
      if (res.ok) {
        const data = await res.json();
        setDbTasks(data);
      }
    } catch (e) {
      console.error("Failed to fetch live tasks:", e);
    }
  };

  const handleResetDatabase = async () => {
    if (!window.confirm(`Are you sure you want to clear all data for candidate ${candidateId} from MongoDB Atlas?`)) {
      return;
    }

    setIsClearing(true);
    try {
      const res = await fetch(`${API_BASE}/api/reset?candidate_id=${encodeURIComponent(candidateId)}`, {
        method: 'DELETE'
      });

      if (res.ok) {
        const result = await res.json();
        setParsedEmails([]);
        setRawJsonText('');
        setDbTasks([]);
        setStats({ processed: 0, tasks_created: 0, tasks_updated: 0, skipped: 0 });

        setChatMessages(prev => [
          ...prev,
          {
            sender: 'system',
            text: `🧹 Database Cleared! Deleted ${result.deleted_tasks} tasks and ${result.deleted_emails} processed records for ${candidateId} in MongoDB Atlas. Counters reset to 0.`,
            supportingData: result
          }
        ]);
      } else {
        alert("Failed to reset database");
      }
    } catch (e) {
      alert("Error calling reset API");
    } finally {
      setIsClearing(false);
    }
  };

  const handleJsonInputChange = (e) => {
    const val = e.target.value;
    setRawJsonText(val);
    try {
      const parsed = JSON.parse(val);
      if (Array.isArray(parsed)) {
        setParsedEmails(parsed);
      } else if (parsed.emails && Array.isArray(parsed.emails)) {
        setParsedEmails(parsed.emails);
      }
    } catch (err) {
      // JSON typing in progress
    }
  };

  const handleGenerateSampleBatch = async () => {
    setIsGenerating(true);
    try {
      const res = await fetch(`${API_BASE}/api/sample-emails?count=250`);
      if (res.ok) {
        const data = await res.json();
        setParsedEmails(data.emails);
        setRawJsonText(JSON.stringify(data.emails, null, 2));
      }
    } catch (e) {
      alert("Error generating sample email batch");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleIngestBatch = async () => {
    if (!parsedEmails || parsedEmails.length === 0) {
      alert("Please paste a JSON email batch or click 'Generate 250 Sample Emails' first.");
      return;
    }

    setIsProcessing(true);
    let totalProcessed = 0;
    let totalCreated = 0;
    let totalUpdated = 0;
    let totalSkipped = 0;

    const emailsToProcess = parsedEmails.slice(0, 100);
    const chunkSize = 20;

    try {
      for (let i = 0; i < emailsToProcess.length; i += chunkSize) {
        const chunk = emailsToProcess.slice(i, i + chunkSize);
        const res = await fetch(`${API_BASE}/ingest`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            candidate_id: candidateId,
            emails: chunk
          })
        });

        if (res.ok) {
          const result = await res.json();
          totalProcessed += result.processed;
          totalCreated += result.tasks_created;
          totalUpdated += result.tasks_updated;
          totalSkipped += result.skipped;

          await fetchStats();
          await fetchLiveTasks();
        } else {
          const err = await res.json();
          alert(`Ingest Error: ${err.detail || 'Failed to ingest batch chunk'}`);
          break;
        }
      }

      setChatMessages(prev => [
        ...prev,
        {
          sender: 'system',
          text: `✅ Ingested batch of ${totalProcessed} emails!\n• Tasks Created: ${totalCreated}\n• Thread Updates: ${totalUpdated}\n• Skipped Noise: ${totalSkipped}`,
          supportingData: {
            processed: totalProcessed,
            tasks_created: totalCreated,
            tasks_updated: totalUpdated,
            skipped: totalSkipped
          }
        }
      ]);
    } catch (e) {
      alert(`Network error executing /ingest: ${e.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReassignTask = async (taskId, newAssignee) => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          assignee_id: newAssignee,
          confidence: 1.0
        })
      });

      if (res.ok) {
        await fetchLiveTasks();
        await fetchStats();

        setChatMessages(prev => [
          ...prev,
          {
            sender: 'system',
            text: `🔄 Task ${taskId} successfully reassigned to ${newAssignee}! MongoDB Atlas record updated.`,
            supportingData: { task_id: taskId, new_assignee: newAssignee, status: "updated_in_mongodb" }
          }
        ]);
      }
    } catch (e) {
      alert("Failed to reassign task");
    }
  };

  const handleSendChat = async (queryText = chatQuery) => {
    const q = queryText || chatQuery;
    if (!q.trim()) return;

    const userMsg = { sender: 'user', text: q, supportingData: null };
    setChatMessages(prev => [...prev, userMsg]);
    if (queryText === chatQuery) setChatQuery('');
    setIsChatLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_id: candidateId,
          query: q
        })
      });

      if (res.ok) {
        const data = await res.json();
        setChatMessages(prev => [
          ...prev,
          {
            sender: 'system',
            text: data.answer,
            supportingData: data.supporting_data
          }
        ]);
      } else {
        setChatMessages(prev => [
          ...prev,
          {
            sender: 'system',
            text: 'Error contacting chat backend.',
            supportingData: null
          }
        ]);
      }
    } catch (e) {
      setChatMessages(prev => [
        ...prev,
        {
          sender: 'system',
          text: 'Network error executing query.',
          supportingData: null
        }
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const teamRosterMap = {
    u_aarti: { name: "Aarti Menon", dept: "Sales — Enterprise", scope: "Enterprise RFPs > ₹10L & PSU Tenders", icon: Briefcase, color: "text-indigo-400" },
    u_rohit: { name: "Rohit Sharma", dept: "Sales — SMB", scope: "Product enquiries & Demos <= ₹10L", icon: Users, color: "text-blue-400" },
    u_meera: { name: "Meera Iyer", dept: "Marketing", scope: "Webinars, sponsorships & media", icon: Megaphone, color: "text-pink-400" },
    u_karan: { name: "Karan Doshi", dept: "Alliances", scope: "Resellers, channel partners & integrations", icon: Handshake, color: "text-cyan-400" },
    u_divya: { name: "Divya Rao", dept: "Finance", scope: "Invoices, POs, GST & vendor billing", icon: DollarSign, color: "text-emerald-400" },
    u_triage: { name: "Triage Queue", dept: "Operations", scope: "Ambiguous items requiring manual review", icon: AlertTriangle, color: "text-amber-400" }
  };

  const getQueueCount = (assigneeId) => {
    return dbTasks.filter(t => t.assignee_id === assigneeId).length;
  };

  const presetQueries = [
    "How many tasks does Aarti Menon have done?",
    "How many emails this batch were proposal or RFP-related?",
    "How many were marketing versus actual spam we correctly ignored?",
    "Show me everything sitting in triage and why.",
    "What's our spurious rate so far?",
    "Which tasks are high priority but low confidence?",
    "How many emails were about GST refunds?",
    "What's the total deal value of all open RFPs?"
  ];

  return (
    <div className="app-wrapper">
      
      {/* Top Navbar */}
      <nav className="navbar">
        <div className="brand">
          <div className="brand-icon">
            <Mail className="w-6 h-6" />
          </div>
          <div className="brand-text">
            <h1>Sales Inbox → Task Router</h1>
            <p>Alumnx AI Labs FDE Challenge</p>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <div className="db-status-badge">
            <DatabaseZap className="w-3.5 h-3.5" /> MongoDB Atlas Active
          </div>

          <div className="candidate-card">
            <label>candidate_id:</label>
            <input
              type="text"
              className="candidate-field"
              value={candidateId}
              onChange={(e) => setCandidateId(e.target.value)}
            />
          </div>
        </div>
      </nav>

      {/* Top Stats Overview Pills */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-info">
            <span className="stat-num">{stats.processed}</span>
            <span className="stat-title">Total Ingested</span>
          </div>
          <div className="stat-icon-wrapper bg-indigo-500/10 text-indigo-400">
            <Layers className="w-5 h-5" />
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-info">
            <span className="stat-num text-emerald-400">{stats.tasks_created}</span>
            <span className="stat-title">Tasks Created</span>
          </div>
          <div className="stat-icon-wrapper bg-emerald-500/10 text-emerald-400">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-info">
            <span className="stat-num text-blue-400">{stats.tasks_updated}</span>
            <span className="stat-title">Thread Updates</span>
          </div>
          <div className="stat-icon-wrapper bg-blue-500/10 text-blue-400">
            <RefreshCw className="w-5 h-5" />
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-info">
            <span className="stat-num text-amber-400">{stats.skipped}</span>
            <span className="stat-title">Noise Skipped</span>
          </div>
          <div className="stat-icon-wrapper bg-amber-500/10 text-amber-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </div>
      </div>

      <main className="section-flow">

        {/* Section 1: Raw JSON Batch Ingestion */}
        <section className="content-card">
          <div className="section-header">
            <h2 className="section-title">
              <Upload className="w-5 h-5 text-indigo-400" />
              Raw JSON Batch Ingestion
            </h2>
          </div>

          <div className="editor-wrapper">
            <textarea
              className="json-textarea-styled"
              placeholder='Paste raw JSON batch matching inbox.json schema (up to 100 emails per batch)...'
              value={rawJsonText}
              onChange={handleJsonInputChange}
            />
          </div>

          <div className="action-bar">
            <button
              className="btn-main btn-glow-primary"
              onClick={handleIngestBatch}
              disabled={isProcessing || parsedEmails.length === 0}
            >
              {isProcessing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Ingesting Batch...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" /> Process & Route Batch (/ingest)
                </>
              )}
            </button>

            <button
              className="btn-main btn-outline-glass"
              onClick={handleGenerateSampleBatch}
              disabled={isGenerating}
            >
              {isGenerating ? "Generating..." : "Generate 250 Sample Emails"}
            </button>
          </div>
        </section>

        {/* Section 2: Team Task Queues & Pre-Routing Data Table */}
        <section className="content-card table-card-wrapper">
          <div className="section-header">
            <h2 className="section-title">
              <Table className="w-5 h-5 text-emerald-400" />
              Team Task Queues & Data Table
            </h2>
          </div>

          {/* Team Queues Tabs */}
          <div className="team-queue-nav">
            <button
              className={`queue-tab-btn ${activeQueueTab === 'raw_table' ? 'active' : ''}`}
              onClick={() => setActiveQueueTab('raw_table')}
            >
              <Table className="w-4 h-4" /> All Processed Input
              <span className="queue-count-badge">{parsedEmails.length}</span>
            </button>

            {Object.keys(teamRosterMap).map((id) => {
              const info = teamRosterMap[id];
              const cnt = getQueueCount(id);
              return (
                <button
                  key={id}
                  className={`queue-tab-btn ${activeQueueTab === id ? 'active' : ''}`}
                  onClick={() => setActiveQueueTab(id)}
                >
                  <info.icon className={`w-3.5 h-3.5 ${info.color}`} /> {info.name}
                  <span className="queue-count-badge">{cnt}</span>
                </button>
              );
            })}
          </div>

          {/* Raw Data Table */}
          {activeQueueTab === 'raw_table' && (
            <div className="table-scroll-area">
              <table className="spec-table">
                <thead>
                  <tr>
                    <th>from_name</th>
                    <th>from_email</th>
                    <th>subject</th>
                    <th>received_at</th>
                    <th>thread_id</th>
                    <th>body (preview)</th>
                  </tr>
                </thead>
                <tbody>
                  {parsedEmails.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '2.5rem', color: '#64748b' }}>
                        No batch loaded. Paste JSON above or click "Generate 250 Sample Emails".
                      </td>
                    </tr>
                  ) : (
                    parsedEmails.slice(0, 100).map((em, idx) => (
                      <tr key={em.email_id || idx}>
                        <td className="sender-name">{em.from_name || "—"}</td>
                        <td className="sender-email">{em.from_email || "—"}</td>
                        <td className="subject-text">{em.subject || "—"}</td>
                        <td>{em.received_at ? em.received_at.split('T')[0] : "—"}</td>
                        <td><span className="thread-chip">{em.thread_id}</span></td>
                        <td className="body-preview">{em.body ? em.body.substring(0, 70) + "..." : "—"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Team Queue View */}
          {activeQueueTab !== 'raw_table' && (
            <div>
              {(() => {
                const member = teamRosterMap[activeQueueTab];
                const queueTasks = dbTasks.filter(t => t.assignee_id === activeQueueTab);
                const totalVal = queueTasks.reduce((sum, t) => sum + (t.deal_value_inr || 0), 0);

                return (
                  <div className="team-profile-card">
                    <div className="profile-info">
                      <div className="profile-avatar">
                        {member.name.split(' ')[0][0]}
                      </div>
                      <div className="profile-details">
                        <h3>{member.name} — Queue</h3>
                        <p>{member.dept}</p>
                        <p className="profile-scope">Scope: {member.scope}</p>
                      </div>
                    </div>

                    <div className="flex gap-4">
                      <div className="stat-info">
                        <span className="stat-num">{queueTasks.length}</span>
                        <span className="stat-title">Assigned Tasks</span>
                      </div>
                      {totalVal > 0 && (
                        <div className="stat-info">
                          <span className="stat-num text-emerald-400 font-mono">₹{totalVal.toLocaleString('en-IN')}</span>
                          <span className="stat-title">Total Pipeline Value</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })()}

              <div className="task-cards-grid">
                {dbTasks.filter(t => t.assignee_id === activeQueueTab).length === 0 ? (
                  <div style={{ color: '#64748b', padding: '2.5rem', textAlign: 'center', gridColumn: '1 / -1' }}>
                    No tasks currently assigned to {teamRosterMap[activeQueueTab].name}.
                  </div>
                ) : (
                  dbTasks.filter(t => t.assignee_id === activeQueueTab).map((t) => {
                    const conf = t.confidence || 0.85;
                    const confClass = conf >= 0.80 ? 'confidence-high' : conf >= 0.50 ? 'confidence-medium' : 'confidence-low';

                    return (
                      <div key={t.task_id} className="task-card-item">
                        <div className="task-card-header">
                          <span className="task-card-title">{t.title}</span>
                          <span className={`confidence-chip ${confClass}`}>
                            {(conf * 100).toFixed(0)}% Conf
                          </span>
                        </div>

                        <p className="task-card-body">{t.description || "No description provided."}</p>

                        <div className="task-card-meta">
                          <span className="meta-pill">Category: {t.category}</span>
                          <span className="meta-pill">Priority: {t.priority}</span>
                          {t.deal_value_inr && (
                            <span className="meta-pill text-emerald-400 font-mono">₹{t.deal_value_inr.toLocaleString('en-IN')}</span>
                          )}
                          {t.due_date && (
                            <span className="meta-pill text-blue-400">Due: {t.due_date}</span>
                          )}
                        </div>

                        <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/5">
                          <span className="text-xs text-slate-400 font-mono">{t.task_id}</span>
                          <select
                            className="reassign-select"
                            value={t.assignee_id}
                            onChange={(e) => handleReassignTask(t.task_id, e.target.value)}
                          >
                            <option value="u_aarti">Reassign: u_aarti</option>
                            <option value="u_rohit">Reassign: u_rohit</option>
                            <option value="u_meera">Reassign: u_meera</option>
                            <option value="u_karan">Reassign: u_karan</option>
                            <option value="u_divya">Reassign: u_divya</option>
                            <option value="u_triage">Reassign: u_triage</option>
                          </select>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </section>

        {/* Section 3: Operations Intelligence Assistant */}
        <section className="content-card">
          <div className="section-header">
            <h2 className="section-title">
              <MessageSquare className="w-5 h-5 text-indigo-400" />
              Operations Intelligence Assistant
            </h2>
          </div>

          <div className="chat-layout">
            <div className="chat-messages-container">
              <div className="chat-scroll">
                {chatMessages.map((msg, index) => (
                  <div
                    key={index}
                    className={`msg-bubble ${msg.sender === 'user' ? 'msg-user' : 'msg-assistant'}`}
                  >
                    <div className="msg-role">
                      {msg.sender === 'user' ? 'Ops Executive' : 'Task Router Assistant'}
                    </div>
                    <div className="msg-body">{msg.text}</div>

                    {msg.supportingData && Object.keys(msg.supportingData).length > 0 && (
                      <div className="data-chip-block">
                        <div className="data-chip-title">
                          <Database className="w-3.5 h-3.5 text-emerald-400" /> supporting_data (Grounded DB Metric):
                        </div>
                        <pre className="data-chip-code">
                          {JSON.stringify(msg.supportingData, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                ))}

                {isChatLoading && (
                  <div className="msg-bubble msg-assistant">
                    <div className="msg-role">Assistant</div>
                    <div className="msg-body flex items-center gap-2">
                      <RefreshCw className="w-4 h-4 animate-spin text-indigo-400" /> Querying MongoDB Atlas...
                    </div>
                  </div>
                )}
              </div>

              <div className="chat-input-row">
                <input
                  type="text"
                  className="input-chat-text"
                  placeholder="Ask a natural-language question about the processed batch..."
                  value={chatQuery}
                  onChange={(e) => setChatQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendChat()}
                />
                <button
                  className="btn-main btn-glow-primary"
                  onClick={() => handleSendChat()}
                  disabled={isChatLoading}
                >
                  <Send className="w-4 h-4" /> Ask
                </button>
              </div>
            </div>

            <div className="preset-queries-panel">
              <h3 className="preset-title">Evaluator Preset Questions</h3>
              {presetQueries.map((pq, i) => (
                <button
                  key={i}
                  className="preset-button"
                  onClick={() => handleSendChat(pq)}
                >
                  "{pq}"
                </button>
              ))}
            </div>

          </div>
        </section>

      </main>

    </div>
  );
}
