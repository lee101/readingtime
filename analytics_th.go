package main

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http"
	"time"
)

const thWriteKey = "thw_ZRAi6UhS8mYOgMn9imxjdb0vFeLCARdZ"

var thClient = &http.Client{Timeout: 5 * time.Second}

// thTrack sends a server-side twoHelixes event; eventID makes webhook retries idempotent.
func thTrack(event, userID, eventID string, props map[string]any) {
	if userID == "" {
		return
	}
	payload, err := json.Marshal(map[string]any{
		"site_id": thWriteKey,
		"events": []map[string]any{{
			"event": event, "client_id": "u_" + userID, "user_id": userID, "event_id": eventID,
			"page_location": "https://readingtime.app.nz/author?subscribed=1", "props": props,
		}},
	})
	if err != nil {
		return
	}
	go func() {
		req, err := http.NewRequest(http.MethodPost, "https://twohelixes.com/v1/collect", bytes.NewReader(payload))
		if err != nil {
			return
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("User-Agent", "readingtime-server/1.0")
		resp, err := thClient.Do(req)
		if err != nil {
			log.Printf("twohelixes %s: %v", event, err)
			return
		}
		resp.Body.Close()
	}()
}
