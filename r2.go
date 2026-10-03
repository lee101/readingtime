package main

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

type r2Client struct {
	endpoint   string
	bucket     string
	publicBase string
	key        string
	secret     string
	http       *http.Client
}

func newR2FromEnv() *r2Client {
	ep := strings.TrimRight(strings.TrimSpace(os.Getenv("READINGTIME_R2_ENDPOINT")), "/")
	bucket := strings.TrimSpace(os.Getenv("READINGTIME_R2_BUCKET"))
	key := strings.TrimSpace(os.Getenv("READINGTIME_R2_ACCESS_KEY_ID"))
	secret := strings.TrimSpace(os.Getenv("READINGTIME_R2_SECRET_ACCESS_KEY"))
	if ep == "" || bucket == "" || key == "" || secret == "" {
		return nil
	}
	pub := strings.TrimRight(strings.TrimSpace(os.Getenv("READINGTIME_R2_PUBLIC_BASE")), "/")
	return &r2Client{endpoint: ep, bucket: bucket, publicBase: pub, key: key, secret: secret,
		http: &http.Client{Timeout: 60 * time.Second}}
}

func (c *r2Client) publicURL(key string) string {
	if c.publicBase == "" {
		return ""
	}
	return c.publicBase + "/" + key
}

func hmacSHA256(key []byte, data string) []byte {
	m := hmac.New(sha256.New, key)
	m.Write([]byte(data))
	return m.Sum(nil)
}

func sha256Hex(b []byte) string {
	s := sha256.Sum256(b)
	return hex.EncodeToString(s[:])
}

func (c *r2Client) do(method, key string, body []byte, contentType, cacheControl string) (*http.Response, error) {
	u, err := url.Parse(c.endpoint)
	if err != nil {
		return nil, err
	}
	path := "/" + c.bucket + "/" + key
	escaped := (&url.URL{Path: path}).EscapedPath()
	now := time.Now().UTC()
	amzDate := now.Format("20060102T150405Z")
	date := now.Format("20060102")
	payloadHash := sha256Hex(body)

	hdrs := map[string]string{
		"host":                 u.Host,
		"x-amz-content-sha256": payloadHash,
		"x-amz-date":           amzDate,
	}
	names := []string{"host", "x-amz-content-sha256", "x-amz-date"}
	var canon strings.Builder
	for _, n := range names {
		canon.WriteString(n + ":" + hdrs[n] + "\n")
	}
	signed := strings.Join(names, ";")
	creq := strings.Join([]string{method, escaped, "", canon.String(), signed, payloadHash}, "\n")
	scope := date + "/auto/s3/aws4_request"
	sts := "AWS4-HMAC-SHA256\n" + amzDate + "\n" + scope + "\n" + sha256Hex([]byte(creq))
	k := hmacSHA256([]byte("AWS4"+c.secret), date)
	k = hmacSHA256(k, "auto")
	k = hmacSHA256(k, "s3")
	k = hmacSHA256(k, "aws4_request")
	sig := hex.EncodeToString(hmacSHA256(k, sts))

	req, err := http.NewRequest(method, c.endpoint+escaped, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("x-amz-content-sha256", payloadHash)
	req.Header.Set("x-amz-date", amzDate)
	req.Header.Set("Authorization", fmt.Sprintf("AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s", c.key, scope, signed, sig))
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	if cacheControl != "" {
		req.Header.Set("Cache-Control", cacheControl)
	}
	return c.http.Do(req)
}

func (c *r2Client) put(key string, body []byte, contentType, cacheControl string) error {
	resp, err := c.do("PUT", key, body, contentType, cacheControl)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode/100 != 2 {
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return fmt.Errorf("r2 put %s: %d %s", key, resp.StatusCode, b)
	}
	io.Copy(io.Discard, resp.Body)
	return nil
}

func (c *r2Client) get(key string) ([]byte, bool, error) {
	resp, err := c.do("GET", key, nil, "", "")
	if err != nil {
		return nil, false, err
	}
	defer resp.Body.Close()
	if resp.StatusCode == 404 {
		io.Copy(io.Discard, resp.Body)
		return nil, false, nil
	}
	if resp.StatusCode/100 != 2 {
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return nil, false, fmt.Errorf("r2 get %s: %d %s", key, resp.StatusCode, b)
	}
	b, err := io.ReadAll(resp.Body)
	return b, err == nil, err
}

func (c *r2Client) exists(key string) (bool, error) {
	resp, err := c.do("HEAD", key, nil, "", "")
	if err != nil {
		return false, err
	}
	resp.Body.Close()
	if resp.StatusCode == 404 {
		return false, nil
	}
	if resp.StatusCode/100 != 2 {
		return false, fmt.Errorf("r2 head %s: %d", key, resp.StatusCode)
	}
	return true, nil
}
