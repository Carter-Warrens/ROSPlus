package server

import (
	"encoding/json"
	"errors"
	"os"
	"regexp"
	"strings"
)

var topicPattern = regexp.MustCompile(`^/[A-Za-z_][A-Za-z0-9_/]*$`)

// Generated Python nodes have one /chatter endpoint. Persisted edges map that
// endpoint at process start; disconnected nodes get a private topic.
func graphArgs(w *Workspace, n *Node) ([]string, error) {
	if n.Mode != "legacy" || !strings.HasSuffix(n.Target, ".py") {
		return nil, nil
	}
	path, e := safe(w, "rosplus.graph.json")
	if e != nil {
		return nil, e
	}
	data, e := os.ReadFile(path)
	if os.IsNotExist(e) {
		return nil, nil
	}
	if e != nil {
		return nil, e
	}
	var graph struct {
		Nodes []struct {
			ID      string `json:"id"`
			Managed bool   `json:"managed_topic"`
		} `json:"nodes"`
		Edges []struct{ Source, Target, Topic string } `json:"edges"`
	}
	if e = json.Unmarshal(data, &graph); e != nil {
		return nil, e
	}
	managed := false
	for _, node := range graph.Nodes {
		if node.ID == n.Name && node.Managed {
			managed = true
		}
	}
	if !managed {
		return nil, nil
	}
	topics := map[string]bool{}
	for _, edge := range graph.Edges {
		if edge.Source == n.Name || edge.Target == n.Name {
			if !topicPattern.MatchString(edge.Topic) || strings.Contains(edge.Topic, "//") {
				return nil, errors.New("graph topic must be an absolute ROS topic")
			}
			topics[edge.Topic] = true
		}
	}
	if len(topics) > 1 {
		return nil, errors.New("generated node has one endpoint; connect all its edges to the same topic")
	}
	topic := "/rosplus/unconnected/" + n.Name
	for t := range topics {
		topic = t
	}
	return []string{"--ros-args", "-r", "/chatter:=" + topic, "--"}, nil
}
