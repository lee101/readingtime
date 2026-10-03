package main

import (
	"database/sql"
	"os"
	"time"
)

func importLegacySQLite(pg *pgDB, path string) error {
	if _, err := os.Stat(path); err != nil {
		return nil
	}
	if _, err := newStoryStore(pg); err != nil {
		return err
	}
	var n int
	_ = pg.DB.QueryRow(`SELECT count(*) FROM stories`).Scan(&n)
	if n > 0 {
		return nil
	}
	// mattn/go-sqlite3 strips the query string unless the DSN is a file: URI,
	// which is what actually makes the open read-only.
	lite, err := sql.Open("sqlite3", "file:"+path+"?mode=ro&_busy_timeout=5000")
	if err != nil {
		return err
	}
	defer lite.Close()
	rows, err := lite.Query(`SELECT id,user_id,author_name,title,prompt,cover_url,text_model,image_model,public,pages_json,
		COALESCE(word_count,0),COALESCE(reading_minutes,0),created_at,updated_at FROM stories`)
	if err != nil {
		return err
	}
	defer rows.Close()
	tx, err := pg.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for rows.Next() {
		var id, uid, an, title, prompt, cover, tm, im, pages string
		var pub, wc, rm int
		var c, u time.Time
		if err := rows.Scan(&id, &uid, &an, &title, &prompt, &cover, &tm, &im, &pub, &pages, &wc, &rm, &c, &u); err != nil {
			return err
		}
		if _, err := tx.Exec(`INSERT INTO stories (id,user_id,author_name,title,prompt,cover_url,text_model,image_model,public,pages_json,word_count,reading_minutes,created_at,updated_at)
			VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING`, id, uid, an, title, prompt, cover, tm, im, pub, pages, wc, rm, c, u); err != nil {
			return err
		}
	}
	if err := rows.Err(); err != nil {
		return err
	}
	return tx.Commit()
}
