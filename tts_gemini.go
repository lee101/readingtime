package main

import (
	"bytes"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"unicode/utf8"
)

const geminiRate = 24000

func (n *narrator) geminiKey() string {
	if k := strings.TrimSpace(os.Getenv("READINGTIME_GEMINI_API_KEY")); k != "" {
		return k
	}
	return strings.TrimSpace(os.Getenv("GEMINI_API_KEY"))
}

func (n *narrator) synthesizeGemini(tokens []string) (*synthResult, error) {
	key := n.geminiKey()
	if key == "" {
		return nil, fmt.Errorf("gemini key unset")
	}
	text := strings.TrimSpace(strings.Join(tokens, ""))
	model := envOr("READINGTIME_GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
	voice := envOr("READINGTIME_GEMINI_VOICE", "Sulafat")
	prompt := "Read this children's picture book page aloud warmly, clearly and slowly, with gentle expression: " + text
	body, _ := json.Marshal(map[string]any{
		"contents": []any{map[string]any{"parts": []any{map[string]string{"text": prompt}}}},
		"generationConfig": map[string]any{
			"responseModalities": []string{"AUDIO"},
			"speechConfig": map[string]any{"voiceConfig": map[string]any{
				"prebuiltVoiceConfig": map[string]string{"voiceName": voice}}},
		},
	})
	req, _ := http.NewRequest("POST", "https://generativelanguage.googleapis.com/v1beta/models/"+model+":generateContent", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-goog-api-key", key)
	resp, err := n.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode/100 != 2 {
		return nil, fmt.Errorf("gemini tts %d: %s", resp.StatusCode, truncate(string(raw), 300))
	}
	var out struct {
		Candidates []struct {
			Content struct {
				Parts []struct {
					InlineData struct {
						Data string `json:"data"`
					} `json:"inlineData"`
				} `json:"parts"`
			} `json:"content"`
		} `json:"candidates"`
	}
	if err := json.Unmarshal(raw, &out); err != nil || len(out.Candidates) == 0 || len(out.Candidates[0].Content.Parts) == 0 {
		return nil, fmt.Errorf("gemini tts: empty response")
	}
	pcm, err := base64.StdEncoding.DecodeString(out.Candidates[0].Content.Parts[0].InlineData.Data)
	if err != nil || len(pcm) < 2000 {
		return nil, fmt.Errorf("gemini tts: bad audio")
	}
	mp3, err := pcmToMP3(pcm)
	if err != nil {
		return nil, err
	}
	words, dur := alignWords(pcm, tokens)
	return &synthResult{audio: mp3, words: words, dur: dur}, nil
}

func pcmToMP3(pcm []byte) ([]byte, error) {
	cmd := exec.Command("ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", "pipe:0",
		"-codec:a", "libmp3lame", "-b:a", "64k", "-f", "mp3", "pipe:1")
	cmd.Stdin = bytes.NewReader(pcm)
	var out, errb bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errb
	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("ffmpeg: %v %s", err, truncate(errb.String(), 200))
	}
	return out.Bytes(), nil
}

type span struct{ a, b int }

func speechSpans(pcm []byte) []span {
	n := len(pcm) / 2
	win := geminiRate / 100
	var voiced []bool
	for i := 0; i+win <= n; i += win {
		var sum float64
		for j := i; j < i+win; j++ {
			v := float64(int16(binary.LittleEndian.Uint16(pcm[j*2:])))
			sum += v * v
		}
		voiced = append(voiced, sum/float64(win) > 300*300)
	}
	const gap = 18
	var spans []span
	start, last := -1, -1
	for i, v := range voiced {
		if v {
			if start < 0 {
				start = i
			} else if i-last > gap {
				spans = append(spans, span{start, last + 1})
				start = i
			}
			last = i
		}
	}
	if start >= 0 {
		spans = append(spans, span{start, last + 1})
	}
	return spans
}

func tokenWeight(w string) float64 {
	c := float64(utf8.RuneCountInString(w))
	if c < 2 {
		c = 2
	}
	return c + 1.5
}

func pauseAfter(sep string) float64 {
	p := 0.0
	for _, r := range sep {
		switch r {
		case '.', '!', '?', '…':
			p += 6
		case ',', ';', ':', '-':
			p += 3
		case '\n':
			p += 3
		}
	}
	return p
}

func alignWords(pcm []byte, tokens []string) ([]wordTime, float64) {
	sp := speechSpans(pcm)
	total := float64(len(pcm)/2) / geminiRate
	if len(sp) == 0 {
		return nil, total
	}
	s0 := float64(sp[0].a) / 100
	s1 := float64(sp[len(sp)-1].b) / 100
	type wt struct {
		idx    int
		weight float64
		pause  float64
	}
	var ws []wt
	idx := 0
	for _, t := range tokens {
		if t == "" {
			continue
		}
		if isWordToken(t) {
			ws = append(ws, wt{idx: idx, weight: tokenWeight(t)})
			idx++
		} else if len(ws) > 0 {
			ws[len(ws)-1].pause += pauseAfter(t)
		}
	}
	if len(ws) == 0 {
		return nil, s1
	}
	var tw float64
	for _, w := range ws {
		tw += w.weight + w.pause
	}
	span := s1 - s0
	out := make([]wordTime, 0, len(ws))
	acc := 0.0
	for _, w := range ws {
		out = append(out, wordTime{I: w.idx, T: round3(s0 + span*acc/tw)})
		acc += w.weight + w.pause
	}
	return out, s1
}

func round3(f float64) float64 { return float64(int(f*1000+0.5)) / 1000 }
