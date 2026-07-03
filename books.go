package main

import (
	"encoding/json"
	"os"
	"sort"
)

// Page is one slide of a book: a chunk of text already split into reading-word
// tokens (words interleaved with their trailing whitespace/punctuation, exactly
// like the original app so the word-by-word highlight reader works unchanged).
type Page struct {
	Text      string   `json:"text"`
	Words     []string `json:"words"`
	ImagePath string   `json:"imagePath,omitempty"` // sample books: /static/bookdata/<book>/<imagePath>
	ImageURL  string   `json:"image_url,omitempty"` // AI stories: absolute/generated URL
	Layout    string   `json:"layout,omitempty"`
	DarkColor bool     `json:"dark_color,omitempty"`
	CSS       string   `json:"css,omitempty"`
}

// Book is a curated sample reader (loaded from books.json, converted from the
// original fixtures.py). User-authored AI stories live in the stories table.
type Book struct {
	Name          string `json:"name"`
	Title         string `json:"title,omitempty"`
	CoverImageURL string `json:"cover_image_url"`
	AudioLink     string `json:"audio_link,omitempty"`
	SubsLink      string `json:"subs_link,omitempty"`
	Pages         []Page `json:"pages"`
}

// loadBooks reads the curated sample books from books.json.
func loadBooks(path string) (map[string]*Book, []string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, nil, err
	}
	var books map[string]*Book
	if err := json.Unmarshal(raw, &books); err != nil {
		return nil, nil, err
	}
	order := make([]string, 0, len(books))
	for name, b := range books {
		b.Name = name
		if b.Title == "" {
			b.Title = humanizeName(name)
		}
		order = append(order, name)
	}
	sort.Strings(order)
	return books, order, nil
}
