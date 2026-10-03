package main

import (
	"context"
	"database/sql"
	"strconv"
	"strings"

	_ "github.com/jackc/pgx/v5/stdlib"
)

type pgDB struct{ *sql.DB }

func rebind(q string) string {
	if !strings.Contains(q, "?") {
		return q
	}
	var b strings.Builder
	n := 0
	for i := 0; i < len(q); i++ {
		if q[i] == '?' {
			n++
			b.WriteString("$" + strconv.Itoa(n))
		} else {
			b.WriteByte(q[i])
		}
	}
	return b.String()
}

func (d *pgDB) Exec(q string, a ...any) (sql.Result, error) { return d.DB.Exec(rebind(q), a...) }
func (d *pgDB) Query(q string, a ...any) (*sql.Rows, error) { return d.DB.Query(rebind(q), a...) }
func (d *pgDB) QueryRow(q string, a ...any) *sql.Row        { return d.DB.QueryRow(rebind(q), a...) }
func (d *pgDB) ExecContext(c context.Context, q string, a ...any) (sql.Result, error) {
	return d.DB.ExecContext(c, rebind(q), a...)
}

func openPG(url string) (*pgDB, error) {
	db, err := sql.Open("pgx", url)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(16)
	db.SetMaxIdleConns(8)
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return &pgDB{db}, nil
}
