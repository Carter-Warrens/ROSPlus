package server

import (
	"github.com/gorilla/websocket"
	"net/http"
	"net/url"
	"time"
)

func (s *Server) stream(w http.ResponseWriter, r *http.Request, ws *Workspace) {
	up := websocket.Upgrader{CheckOrigin: func(r *http.Request) bool {
		o := r.Header.Get("Origin")
		if o == "" {
			return true
		}
		u, e := url.Parse(o)
		return e == nil && u.Host == r.Host
	}}
	c, e := up.Upgrade(w, r, nil)
	if e != nil {
		return
	}
	defer c.Close()
	c.SetReadLimit(4096)
	c.SetReadDeadline(time.Now().Add(5 * time.Second))
	var auth struct {
		Type      string `json:"type"`
		Token     string `json:"token"`
		Workspace string `json:"workspace_id"`
	}
	if e = c.ReadJSON(&auth); e != nil {
		return
	}
	if auth.Type != "subscribe" || auth.Workspace != ws.ID {
		return
	}
	if !s.authorized(r) {
		fake := r.Clone(r.Context())
		fake.Header = r.Header.Clone()
		fake.Header.Set("Authorization", "Bearer "+auth.Token)
		if !s.authorized(fake) {
			c.WriteControl(websocket.CloseMessage, websocket.FormatCloseMessage(1008, "authentication required"), time.Now().Add(time.Second))
			return
		}
	}
	done := make(chan struct{})
	go func() {
		defer close(done)
		c.SetReadDeadline(time.Now().Add(30 * time.Second))
		c.SetPongHandler(func(string) error { return c.SetReadDeadline(time.Now().Add(30 * time.Second)) })
		for {
			var msg Object
			if c.ReadJSON(&msg) != nil {
				return
			}
			if msg["type"] == "unsubscribe" {
				return
			}
		}
	}()
	tick := time.NewTicker(250 * time.Millisecond)
	defer tick.Stop()
	heartbeat := time.NewTicker(5 * time.Second)
	defer heartbeat.Stop()
	var sequence uint64
	for {
		select {
		case <-done:
			return
		case <-heartbeat.C:
			c.SetWriteDeadline(time.Now().Add(2 * time.Second))
			if c.WriteControl(websocket.PingMessage, nil, time.Now().Add(time.Second)) != nil {
				return
			}
			if c.WriteJSON(Object{"type": "heartbeat", "timestamp": now()}) != nil {
				return
			}
		case <-tick.C:
			s.mu.Lock()
			if s.closing || s.items[ws.ID] != ws {
				s.mu.Unlock()
				return
			}
			events := []Object{}
			for _, l := range ws.Logs {
				if l["sequence"].(uint64) > sequence {
					events = append(events, l)
					sequence = l["sequence"].(uint64)
				}
			}
			status := s.status(ws)
			graph := s.graph(ws)
			metrics := s.metrics(ws)
			s.mu.Unlock()
			events = append(events, Object{"type": "node_update", "workspace_id": ws.ID, "nodes": status["nodes"]}, Object{"type": "graph_update", "workspace_id": ws.ID, "nodes": graph["nodes"], "edges": graph["edges"]}, Object{"type": "metrics", "workspace_id": ws.ID, "data": metrics})
			for _, v := range events {
				c.SetWriteDeadline(time.Now().Add(2 * time.Second))
				if c.WriteJSON(v) != nil {
					return
				}
			}
		}
	}
}
